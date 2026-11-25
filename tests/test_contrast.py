"""The contrast gate: every token pair the hub uses passes in Night and Daylight (with alpha composited), and
the checker can fail."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import contrast

CSS = (contrast.ROOT / "ui" / "tokens.css").read_text(encoding="utf-8")


def test_all_token_pairs_pass_in_both_themes():
    assert contrast.check() == []


def test_two_themes_night_first():
    assert list(contrast.themes(CSS)) == ["Night", "Daylight"]


def test_known_ratios():
    assert round(contrast.ratio("#000000", "#ffffff"), 1) == 21.0
    assert contrast.ratio("#b4512a", "#ffffff") > 4.5  # white label on the terracotta button


def test_alpha_compositing():
    assert contrast.over("#ffffff80", "#000000") == "#808080"
    assert contrast.over("#123456", "#ffffff") == "#123456"
    night = contrast.themes(CSS)["Night"]
    # --line-dim is see-through (serious mode, v0.6.0): at least 3:1 on the base, and it must count as composited
    assert 3.0 <= contrast.worst(night, "line-dim", "bg-1") < 4.4
    assert contrast.worst(night, "line-dim", "bg-1") < contrast.ratio("#9aa7b4", night["bg-1"])


def test_sheet_inks_on_paper():
    day = contrast.themes(CSS)["Daylight"]
    for ink in contrast.INKS:
        assert contrast.ratio(day[ink], day["paper"]) >= 4.5, ink


def test_a_faint_pair_is_caught():
    css = CSS.replace("--muted: #6b6258;", "--muted: #c9c0b4;")
    assert any("Daylight: --muted" in line for line in contrast.check(css))


def test_a_faint_alpha_is_caught():
    # the 35% line-dim from the research draft fails where frames show bounds (review §1.3)
    css = CSS.replace("--line-dim: #9aa7b4a6;", "--line-dim: #9aa7b459;")
    assert any("Night: --line-dim" in line for line in contrast.check(css))


def test_a_too_dim_window_is_caught():
    # windows Jarvis isn't talking about are drawn at --dim-opacity; their text must still pass
    css = CSS.replace("--dim-opacity: 0.88;", "--dim-opacity: 0.5;")
    assert any("Night: --text-3 in a dimmed window" in line for line in contrast.check(css))


def test_a_dimmed_window_fades_its_outside_metadata_and_frame_too():
    # a11y review MUST 3: at 75% the metadata outside a set-aside window ("ADDED 3:40 PM", text-3 on the backdrop)
    # measured 4.19–4.39:1 and its frame 2.88:1, and the old checker missed both
    css = CSS.replace("--dim-opacity: 0.88;", "--dim-opacity: 0.75;")
    failures = contrast.check(css)
    assert any("Night: --text-3 outside a dimmed window's frame" in line for line in failures)
    assert any("Night: --line-dim as a dimmed window's frame" in line for line in failures)
    night = contrast.themes(CSS)["Night"]
    assert contrast.worst_dimmed_outside(night, "text-3") >= 4.5
    assert contrast.worst_dimmed_outside(night, "line-dim") >= 3.0
    day = contrast.themes(CSS)["Daylight"]  # Daylight keeps full strength; a set-aside window's edge still shows
    assert contrast.worst_dimmed_outside(day, "line-dim") >= 3.0


def test_glass_windows_are_measured_over_every_backdrop():
    # HUD v3 glass (§14 decision 3): every text tone and the blue kicker on both glass fills, the bright edge and
    # the title plate of the window Jarvis means are all in the gate, in both themes
    for theme in ("Night", "Daylight"):
        pairs = contrast.pairs_for(theme)
        for fg in ("text", "text-2", "text-3", "cyan"):
            assert (fg, "glass", 4.5) in pairs and (fg, "glass-strong", 4.5) in pairs
        assert ("glass-edge", "bg-2", 3.0) in pairs and ("on-title-plate", "title-plate", 4.5) in pairs
    night = contrast.themes(CSS)["Night"]
    # the glass is see-through: measured composited, never as its solid colour
    assert contrast.alpha(night["glass"]) < contrast.alpha(night["glass-strong"]) < 1
    assert contrast.worst(night, "text-3", "glass") >= 4.5


def test_a_light_glass_is_caught():
    css = CSS.replace("--glass: #121921d9;", "--glass: #7fa3bc99;")
    assert any("Night: --text-3 on --glass is" in line for line in contrast.check(css))


def test_a_dimmed_glass_window_over_a_white_page_is_measured():
    # a set-aside window lets through what is behind it; the brightest thing that can be there is a white page
    night = contrast.themes(CSS)["Night"]
    over_page = contrast.worst_dimmed_glass(night, "text-3", "glass")
    assert 4.5 <= over_page < contrast.worst(night, "text-3", "glass")
    css = CSS.replace("--dim-opacity: 0.88;", "--dim-opacity: 0.6;")
    assert any("Night: --text-3 on a dimmed --glass window" in line for line in contrast.check(css))


def test_a_faint_title_plate_is_caught():
    css = CSS.replace("--title-plate: #00000000;", "--title-plate: #a8dcf2;")
    assert any("Night: --on-title-plate on --title-plate" in line for line in contrast.check(css))
