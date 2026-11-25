"""Checks the contrast of every token pair the hub uses, in both themes (WCAG 2: text ≥ 4.5:1, UI ≥ 3:1).

Night (the default) and Daylight are read from ui/tokens.css. Colours with alpha (#rrggbbaa, e.g. --line-dim
at 50% or the window panel at 86%) are composited before measuring: a see-through surface over every
backdrop it can sit on (base, edges, raised centre, and the raised centre under the grid), and a see-through
stroke or text over the surface it is drawn on. The worst case counts. A window that is set aside is drawn
whole at --dim-opacity, so its text, the metadata just outside its frame and the frame itself are measured
faded too.

HUD v3 glass windows (§14 decision 3): the window paints the page's own backdrop under its see-through tint
(--glass, --glass-strong under text), so text on glass is measured over every backdrop, and a window that is
set aside (drawn at --dim-opacity) is also measured over the brightest thing that can sit behind it: another
window's white page (--paper). The bright edge, the window Jarvis means, and its title plate are checked too.

Run:  python tools/contrast.py      (exit code 1 and the failing pairs when something is too faint)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT, UI = 4.5, 3.0
SURFACES = ["canvas", "sheet", "card", "sunken"]
HUD_SURFACES = ["bg-0", "bg-1", "bg-2", "panel"]
GLASS = ["glass", "glass-strong"]
STATES = ["cyan", "cyan-hi", "warn", "crit", "ok"]
INKS = ["ink-text", "ink-muted", "ink-warn", "ink-ok", "ink-cyan", "ink-crit"]

PAIRS: list[tuple[str, str, float]] = (
    [("text", s, TEXT) for s in SURFACES]
    + [("muted", s, TEXT) for s in SURFACES]
    + [("accent-ink", s, TEXT) for s in ["canvas", "sheet", "card", "accent-soft"]]
    + [("leaf-ink", s, TEXT) for s in ["canvas", "sheet", "card", "growth-soft"]]
    + [("on-accent", "accent", TEXT), ("on-accent", "accent-hover", TEXT),
       ("notice-ink", "notice-bg", TEXT), ("error-ink", "error-bg", TEXT), ("honey-ink", "honey", TEXT),
       ("text", "accent-soft", TEXT), ("text", "growth-soft", TEXT), ("text", "notice-bg", TEXT)]
    # due-soon countdowns and the status line's notes use the notice ink straight on a surface
    + [("notice-ink", s, TEXT) for s in ["canvas", "sheet", "card"]]
    # UI parts that carry meaning: the accent button, the orb ring, control outlines, brackets
    + [("accent", s, UI) for s in SURFACES]
    + [("control", s, UI) for s in ["canvas", "sheet", "card"]]
    + [("orb-ring", "canvas", UI), ("orb-muted", "canvas", UI), ("bracket", "canvas", UI), ("bracket", "card", UI),
       ("negative", "card", UI), ("leaf-deep", "canvas", UI), ("stem", "canvas", UI)]
    # HUD text: every text tone and every state colour on every HUD surface (a state word is text)
    + [(fg, s, TEXT) for fg in ["text", "text-2", "text-3", *STATES] for s in HUD_SURFACES]
    # HUD strokes that carry meaning: inactive frames and upcoming arcs, the orb ring, the window Jarvis means
    + [(fg, s, UI) for fg in ["line-dim", "orb", "orb-band", "frame-on"] for s in HUD_SURFACES]
    # the focus ring (--text) against the dark gap behind it
    + [("text", "bg-0", UI)]
    # the light reading sheet and its inks
    + [(ink, "paper", TEXT) for ink in INKS]
    # HUD v3 glass: every text tone and state colour (the blue kicker is --cyan) on both glass fills; the bright
    # edge as a boundary; the title plate of the window Jarvis means
    + [(fg, s, TEXT) for fg in ["text", "text-2", "text-3", *STATES] for s in GLASS]
    + [(edge, s, UI) for edge in ["glass-edge", "glass-edge-rest"] for s in HUD_SURFACES[:3]]
    + [("on-title-plate", "title-plate", TEXT)]
    # clean windows (§14.2): the flat chart bars on glass, and the "Why?" drawer's text on its solid fill
    + [("chart-bar", s, UI) for s in GLASS]
)
# Night only: there the frame is the only thing that shows a window's edge (the panel is nearly the colour of
# the base), and --line is the bright HUD stroke. In Daylight the card fill and shadow show the edge.
NIGHT_PAIRS: list[tuple[str, str, float]] = (
    [("frame", s, UI) for s in ["canvas", "bg-0", "bg-1", "bg-2"]] + [("line", s, UI) for s in HUD_SURFACES]
)

COLOUR = re.compile(r"--([\w-]+):\s*(#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?)\s*;")
OPACITY = re.compile(r"--(dim-opacity):\s*([\d.]+)\s*;")
# A window that is set aside (.jv-frame--dim, or a window Jarvis isn't talking about) is drawn whole at
# --dim-opacity: its text inside on the panel, the metadata that hangs just outside its frame ("ADDED 3:40 PM",
# straight on the backdrop), and its frame (window.css: --line-dim) all fade with it.
DIMMED = ["text", "text-2", "text-3"]          # inside, on the panel
DIMMED_OUTSIDE = ["text-2", "text-3"]          # the metadata outside the frame, on the backdrop
DIMMED_EDGE = "line-dim"                       # a set-aside window's frame (both themes), a meaningful edge
DIMMED_GLASS = ["text", "text-2", "text-3", "cyan"]  # on a set-aside glass window (the kicker is --cyan)


def themes(css: str) -> dict[str, dict[str, str]]:
    def block(selector: str) -> dict[str, str]:
        body = css.split(selector + " {", 1)[1].split("\n}", 1)[0]
        return {k: v.lower() for k, v in COLOUR.findall(body) + OPACITY.findall(body)}
    day = block(":root")
    return {"Night": {**day, **block(':root[data-theme="night"]')}, "Daylight": day}


def luminance(hex_colour: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def alpha(colour: str) -> float:
    return int(colour[7:9], 16) / 255 if len(colour) == 9 else 1.0


def over(colour: str, backdrop: str) -> str:
    """`colour` (maybe with alpha) composited over an opaque `backdrop`; returns an opaque #rrggbb."""
    a = alpha(colour)
    mixed = (round(int(colour[i:i + 2], 16) * a + int(backdrop[i:i + 2], 16) * (1 - a)) for i in (1, 3, 5))
    return "#" + "".join(f"{v:02x}" for v in mixed)


def backdrops(tokens: dict[str, str]) -> list[str]:
    """What a see-through surface can sit on: the base, the edges, the raised centre, the centre under the grid."""
    return [tokens[k] for k in ("canvas", "bg-0", "bg-1", "bg-2")] + [over(tokens["grid"], tokens["bg-2"])]


def worst(tokens: dict[str, str], fg: str, bg: str) -> float:
    """The lowest contrast of `fg` drawn on `bg`, over every backdrop a see-through `bg` can show."""
    under = [over(tokens[bg], b) for b in backdrops(tokens)] if alpha(tokens[bg]) < 1 else [tokens[bg]]
    return min(ratio(over(tokens[fg], u), u) for u in under)


def worst_dimmed(tokens: dict[str, str], fg: str) -> float:
    """`fg` on the panel, with the whole window drawn at --dim-opacity over each backdrop."""
    opacity = f"{round(float(tokens['dim-opacity']) * 255):02x}"
    results = []
    for b in backdrops(tokens):
        panel = over(tokens["panel"], b)
        results.append(ratio(over(over(tokens[fg], panel) + opacity, b), over(panel + opacity, b)))
    return min(results)


def worst_dimmed_outside(tokens: dict[str, str], fg: str) -> float:
    """`fg` drawn straight on each backdrop (no panel), faded with its window to --dim-opacity."""
    opacity = f"{round(float(tokens['dim-opacity']) * 255):02x}"
    return min(ratio(over(over(tokens[fg], b) + opacity, b), b) for b in backdrops(tokens))


def worst_dimmed_glass(tokens: dict[str, str], fg: str, glass: str) -> float:
    """`fg` on a glass window drawn at --dim-opacity: the window paints the backdrop under its tint (so `fg` sits
    on glass over each backdrop), and the faded window then lets through what is behind it, which can be another
    window's white page (--paper) as well as the backdrop."""
    opacity = f"{round(float(tokens['dim-opacity']) * 255):02x}"
    behind = backdrops(tokens) + [tokens["paper"]]
    results = []
    for b in backdrops(tokens):
        fill = over(tokens[glass], b)
        ink = over(tokens[fg], fill)
        for under in behind:
            results.append(ratio(over(ink + opacity, under), over(fill + opacity, under)))
    return min(results)


def dimmed_checks(tokens: dict[str, str]) -> list[tuple[str, float, float]]:
    """(what, contrast, needed) for everything a set-aside window draws."""
    return ([(f"--{fg} in a dimmed window", worst_dimmed(tokens, fg), TEXT) for fg in DIMMED]
            + [(f"--{fg} outside a dimmed window's frame", worst_dimmed_outside(tokens, fg), TEXT) for fg in DIMMED_OUTSIDE]
            + [(f"--{DIMMED_EDGE} as a dimmed window's frame", worst_dimmed_outside(tokens, DIMMED_EDGE), UI)]
            + [(f"--{fg} on a dimmed --{g} window", worst_dimmed_glass(tokens, fg, g), TEXT) for fg in DIMMED_GLASS for g in GLASS])


def pairs_for(theme: str) -> list[tuple[str, str, float]]:
    return PAIRS + (NIGHT_PAIRS if theme == "Night" else [])


def check(css: str | None = None) -> list[str]:
    css = css if css is not None else (ROOT / "ui" / "tokens.css").read_text(encoding="utf-8")
    failures = []
    for theme, tokens in themes(css).items():
        for fg, bg, need in pairs_for(theme):
            got = worst(tokens, fg, bg)
            if got < need:
                failures.append(f"{theme}: --{fg} on --{bg} is {got:.2f}:1 (needs {need}:1)")
        for what, got, need in dimmed_checks(tokens):
            if got < need:
                failures.append(f"{theme}: {what} is {got:.2f}:1 (needs {need}:1)")
    return failures


def main() -> int:
    failures = check()
    for line in failures:
        print(line)
    total = sum(len(pairs_for(t)) + len(DIMMED) + len(DIMMED_OUTSIDE) + 1 + len(DIMMED_GLASS) * len(GLASS) for t in ("Night", "Daylight"))
    print(f"contrast: {total - len(failures)} of {total} pairs pass" + ("" if failures else " (all)"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
