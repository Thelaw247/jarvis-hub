"""Design tokens: Night and Daylight define the same names, the HUD tokens exist in both, the Night palette
matches HUD v2 §2, and no colour literal lives outside tokens.css."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import hexlint

TOKENS = (ROOT / "ui" / "tokens.css").read_text(encoding="utf-8")
NIGHT = ':root[data-theme="night"]'
HUD = ["--bg-0", "--bg-1", "--bg-2", "--grid", "--panel", "--line", "--line-dim", "--frame", "--frame-on", "--rule", "--orb",
       "--cyan", "--cyan-hi", "--text", "--text-2", "--text-3", "--warn", "--crit", "--ok", "--glow", "--glow-on",
       "--sheen", "--text-glow", "--dim-opacity", "--hud-cell"]
INKS = ["--paper", "--ink-text", "--ink-muted", "--ink-warn", "--ink-ok", "--ink-cyan", "--ink-crit"]
TYPE = ["--font-display", "--kicker", "--kicker-track", "--display", "--display-track", "--hero"]


def block(selector: str) -> dict[str, str]:
    body = TOKENS.split(selector + " {", 1)[1].split("\n}", 1)[0]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", body))


def test_night_only_overrides_known_tokens_and_covers_every_colour():
    day, night = block(":root"), block(NIGHT)
    assert set(night) <= set(day), f"Night sets unknown tokens: {sorted(set(night) - set(day))}"
    # the reading sheet and its inks are the same in both themes (a light page is a light page)
    colour_tokens = {k for k, v in day.items() if v.startswith(("#", "rgba", "0 ", "none"))} - set(INKS)
    assert colour_tokens <= set(night), f"Night is missing: {sorted(colour_tokens - set(night))}"


def test_hud_tokens_exist_in_both_themes():
    day, night = block(":root"), block(NIGHT)
    for name in HUD + INKS + TYPE:
        assert name in day, f"{name} needs a Daylight value in :root"
    for name in HUD:
        if name != "--hud-cell":
            assert name in night, f"{name} needs a Night value"


def test_night_palette_matches_the_design():
    night = {k: v.lower() for k, v in block(NIGHT).items()}
    expected = {  # serious mode (v0.6.0, HUD_V2 §14.12): neutral surfaces, one muted accent, off-white text
        "--bg-0": "#0a0e14", "--bg-1": "#0e141c", "--bg-2": "#121a24", "--grid": "#ffffff09",
        "--panel": "#0e141cf2", "--line": "#b9d3e6", "--line-dim": "#9aa7b4a6", "--orb": "#1670e8",
        "--cyan": "#8fb3cf", "--cyan-hi": "#b9d3e6", "--text": "#e6ebf0", "--text-2": "#a9b4bf",
        "--text-3": "#8e9aa7", "--warn": "#d9a75b", "--crit": "#e5737d", "--ok": "#7fc4a0",
    }
    for name, value in expected.items():
        assert night[name] == value, f"{name} is {night[name]}, the design says {value}"
    # existing names take Night values, so components switch with no renaming
    assert night["--canvas"] == night["--bg-1"] and night["--card"] == night["--panel"]
    assert night["--muted"] == night["--text-2"] and night["--accent"] == night["--cyan"]
    assert night["--leaf-ink"] == night["--cyan-hi"]  # done is cyan-hi, not green
    assert night["--r-card"] == "8px"                  # v0.6.3: softly rounded everywhere (his pick)


def test_sheet_inks_match_the_design():
    day = {k: v.lower() for k, v in block(":root").items()}
    assert (day["--paper"], day["--ink-warn"], day["--ink-ok"], day["--ink-cyan"], day["--ink-crit"], day["--ink-text"]) == (
        "#f5f8fc", "#8a5300", "#1d6b45", "#0b5fa5", "#b3261e", "#14202e")


def test_line_dim_is_a_see_through_line():
    # serious mode (v0.6.0): a neutral grey hairline, see-through (contrast.py checks it still reaches 3:1)
    v = block(NIGHT)["--line-dim"].lower()
    assert len(v) == 9 and v[-2:] not in ("ff", "00")


def test_evening_is_retired():
    assert ':root[data-theme="evening"]' not in TOKENS


def test_pen_reader_palette_is_kept_for_daylight():
    day = block(":root")
    assert day["--canvas"] == "#f3ecdf" and day["--accent"] == "#b4512a" and day["--leaf-ink"] == "#2f6a4a"


def test_no_colour_literals_outside_tokens():
    assert hexlint.offenders() == []


def test_hexlint_catches_a_literal(tmp_path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "x.css").write_text(".a { color: #ff0000; }\n.b { fill: url(#grad); }\n")
    assert len(hexlint.offenders(tmp_path)) == 1


def test_fonts_exist_with_their_licences():
    for name in re.findall(r'url\("(fonts/[^"]+)"\)', TOKENS):
        assert (ROOT / "ui" / name).is_file(), name
    assert '"Barlow Condensed"' in block(":root")["--font-display"]
    assert (ROOT / "ui" / "fonts" / "LICENSE-barlow-condensed.txt").read_text(encoding="utf-8").count("SIL Open Font License") >= 1


def test_focus_ring_is_never_cyan():
    base = (ROOT / "ui" / "base.css").read_text(encoding="utf-8")
    ring = re.search(r":focus-visible[^{]*\{([^}]*)\}", base).group(1)
    assert "outline: 2px solid var(--text)" in ring and "outline-offset: 3px" in ring and "5px var(--bg-0)" in ring
    assert "cyan" not in ring and "accent" not in ring


def test_kicker_rule():
    base = (ROOT / "ui" / "base.css").read_text(encoding="utf-8")
    kicker = re.search(r"\.jv-kicker\s*\{([^}]*)\}", base).group(1)
    assert "var(--kicker)" in kicker and "var(--kicker-track)" in kicker and "var(--kicker-case)" in kicker and "var(--text-3)" in kicker
    day = block(":root")
    # serious mode (v0.6.0): small mono in normal case, light tracking
    assert day["--kicker"].startswith("500 12px") and "var(--font-mono)" in day["--kicker"] and day["--kicker-track"] == "0.03em" and day["--kicker-case"] == "none"


def test_three_theme_choices():
    theme_js = (ROOT / "ui" / "core" / "theme.js").read_text(encoding="utf-8")
    choices = re.search(r"THEME_CHOICES = (\[.*\]);", theme_js).group(1)
    assert re.findall(r'\["(\w+)", "[^"]+"\]', choices) == ["night", "day", "sunset"]
    # the two data-theme values the tokens define, and nothing for the retired Evening
    assert re.search(r'THEMES = \["night", "day"\]', theme_js)
    assert set(re.findall(r':root\[data-theme="(\w+)"\]', TOKENS)) == {"night"}
