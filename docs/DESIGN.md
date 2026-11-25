# Jarvis hub design system: "Night HUD"

Huw Prosser's layout, palette, windows and orb with the films' HUD grammar: luminous lines on near-black
navy, square windows, mono kickers, a condensed display face, light added rather than painted. Night is the
default everywhere, ambient included. Daylight keeps the Earth HUD (Pen Reader's paper, sand and
terracotta) for bright rooms. The design and its reasons: `docs/design/JARVIS_DESIGN_HUD_V2.md` (§1 themes,
§2 palette, §3 windows, §7 motion, §8 type); trust rules and views stay in `JARVIS_DESIGN_HUB_TRUST.md` §1–§4.

## Where things live
- `ui/tokens.css`: every colour, radius, space, font and duration. **The only file with hex colours**
  (`python tools/hexlint.py`). `:root` is Daylight and holds every token (HUD ones included);
  `:root[data-theme="night"]` gives the same names Night values. `#rrggbbaa` is a colour with alpha.
- `ui/base.css`: the HUD background, `.jv-frame`, `.jv-kicker`, `.jv-meta`, `.jv-display`, `.jv-hero`, `.jv-pill`,
  `.jv-paper`, the focus ring, the reduced-motion rules, and the older shared classes (`.jv-btn`, `.jv-card`,
  `.jv-sheet`, `.jv-label`, `.jv-title`, `.jv-num`, `.jv-telemetry`, `.jv-guess`, `.jv-grid`, `.jv-sr`).
  See them side by side: `?scene=component:hud-base&theme=night` (and `&theme=day`).
- `ui/core/theme.js`: the theme choice, Saskatoon's sunset, motion and plants.
- `ui/fonts/`: Barlow Condensed 600, Lexend, Atkinson Hyperlegible Next, JetBrains Mono (self-hosted, OFL).

## Themes
`<html data-theme="night|day" data-motion="full|reduced|off" data-size="full|laptop|strip|phone|ambient">`.

| Choice in Controls › Look | Stored as | Shows |
|---|---|---|
| **Night** (default) | `night` | Night always |
| **Daylight** | `day` | Daylight always |
| **Sunset** | `sunset` | Daylight by day, Night from Saskatoon's real sunset to sunrise |

Retired values still load: `evening` → Night; `system` → Night when Windows is dark, Daylight when light.
`theme.js` exports `THEME_CHOICES` (for the Controls segment), `themeChoice()` (which segment is selected)
and `themeFor()`. `?theme=day` forces Daylight; `?theme=night` (or `evening`, or anything else) forces Night.

## Tokens
Existing names keep their jobs; Night sets their values, so every component switches with no renaming:
`--canvas` = base, `--card` = panel, `--muted` = text-2, `--accent` = cyan, `--leaf-ink` (done) = cyan-hi,
`--notice-*` = warn, `--error-*` = crit, `--line` = ice line, `--line-strong` = line-dim.

| Token | Night | Job |
|---|---|---|
| `--bg-0` / `--bg-1` / `--bg-2` | `#070c18` / `#0b1523` / `#101d33` | edges (vignette) / base / raised centre |
| `--grid-dot` | `#8cb4ff` at 18% | the dotted backdrop: 1 px dots every 24 px (`--grid-size`); structure only (`--grid`, a 7% line, is kept for in-panel rules) |
| `--panel` | `#03060c` at 86% | window fill |
| `--line` | `#a8e6ff` | HUD strokes, ticks, in-progress arcs (ice) |
| `--line-dim` | `#a8e6ff` at 50% (4.2:1) | inactive strokes, upcoming arcs, pill outlines |
| `--frame` / `--frame-on` | line-dim / line | a window's border at rest / when Jarvis means it |
| `--rule` | `#a8e6ff` at 18% | quiet dividers between rows inside a window (use it instead of `--line` there) |
| `--orb` | `#1670e8` | the orb's energy ring while speaking (HUD v3: deeper blue; the rings themselves are near-white `--orb-line`) |
| `--orb-edge` | `#3ea5f2` | the lighter highlight line on the energy ring's outer edge (Huw's glow) |
| `--orb-deep` | `#1458a9` | the shade toward the energy ring's inner edge (Huw's glow) |
| `--cyan` | `#38c8ff` | **Jarvis**: what he means right now, links |
| `--cyan-hi` | `#7ed8ff` | **done**, highlights |
| `--text` / `--text-2` / `--text-3` | `#e8f6ff` / `#9fc3d9` / `#7fa3bc` | text / secondary / kickers and metadata |
| `--warn` | `#ffc24a` | **needs you**: soon, your yes |
| `--crit` | `#ff4d5e` | critical, overdue |
| `--ok` | `#4ade9b` | system health only (Under the hood) |
| `--glow` / `--glow-on` | layered cyan box-shadows | static frame glow; brighter for the window Jarvis means |
| `--sheen` | ice at 22% | the 1 px top-edge sheen on a frame |
| `--text-glow` | cyan blur | big text only (`.jv-display`, `.jv-hero`); `none` in Daylight |
| `--dim-opacity` | 0.88 (Daylight 1) | windows Jarvis isn't talking about |

Daylight gives each HUD token its nearest Earth value (cyan = terracotta ink, cyan-hi and ok = leaf ink, warn =
notice ink, crit = error ink), so a component may use any token in either theme.

**The light reading sheet** (`.jv-paper`, `--paper` `#f5f8fc`, the same in both themes): long reading (PDFs,
notes) opens on it inside a HUD frame. `.jv-paper` swaps `--text`, `--muted`, `--warn`, `--ok`, `--cyan` and
`--crit` for its inks, so components inside it keep using the usual names: `--ink-text` `#14202e` (15.5:1),
`--ink-muted` `#46566a` (7.0), `--ink-warn` `#8a5300` (5.9), `--ink-ok` `#1d6b45` (6.1), `--ink-cyan` `#0b5fa5`
(6.2), `--ink-crit` `#b3261e` (6.1).

**Type tokens:** `--font-display` (Barlow Condensed 600), `--display` (window title, 24/26), `--hero` (hero
number, 72/72, ~3× the title), `--kicker` (JetBrains Mono 12/16) with `--kicker-track` 0.12em, `--display-track`.
**Motion tokens:** `--t-snap` 80 ms (brackets snap, lock), `--t-draw` 120 ms (frame draws), `--ease-mech` `cubic-bezier(0.2, 0.9, 0.1, 1)`
(hard stop, no springs), plus `--t-fast`, `--t-move`, `--t-fly`.
**Shape:** Night sets `--r-card` and `--r-sheet` to 0 (square windows) and `--r-control` to 2 px; pills stay pills.

## Classes
| Class | What it is |
|---|---|
| body (automatic) | The HUD background, all static: base + radial vignette (`--bg-2` → `--bg-1` → `--bg-0`) + a faint dot grid (24 px) + a dotted ruler along the top edge + a small notch at top centre. No ruler or notch on the strip or phone. |
| `.jv-frame` | A window: square corners (Night), 1 px `--frame`, static `--glow`, `--panel` fill, faint top sheen, `--pad` inside. |
| `.jv-frame--on` | The window Jarvis means: a brighter 1.5 px frame (`--frame-on`) and `--glow-on`. One at a time. |
| `.jv-frame--dim` | A window he isn't talking about: `--dim-opacity`, 0.98 scale (no scale under reduced motion). |
| `.jv-kicker`, `.jv-kicker-row` | Inside a window, top-left: 12 px mono caps, tracking 0.12em, `--text-3`, ≤ 4 words, status word last ("GE 122 // DUE"). The row puts a timer, index or type on the right ("00:04", "01 / 03"). |
| `.jv-meta` | Metadata hanging just outside the frame ("ADDED 2 MIN AGO", "SYLLABUS P.3"), same type as the kicker. As a child of `.jv-frame` it sits under the bottom-left corner (the frame gets 24 px of room); `--above` and `--end` move it. Never the only copy of a fact. |
| `.jv-display` | Window title: condensed caps, two lines at most, glow allowed. |
| `.jv-hero` | Hero number: condensed, tabular figures, ~3× the title. Every window leads with one big thing. |
| `.jv-pill` | Small outlined mono pill button (TIDY · CLEAR VIEW · the views). Chosen (`aria-pressed`, `aria-current`, `aria-checked`): brighter frame and text, never cyan. |
| `.jv-paper` | The light reading sheet with its inks. |

## Rules (each is a review check)
| Thing | Rule |
|---|---|
| Colour | Tokens only. Light is added, never painted: thin bright strokes with static glow, dark nearly opaque fills; brightness order orb → active frames → text → grid. Cyan means Jarvis (what he means, links); done is cyan-hi, not green; warn means needs you; crit is critical; ok is system health only. Kind of thing is shown by icon and position, never colour. Never colour alone: every state has a shape and a word too (HUD v2 §5). |
| Lines | Meaningful lines ≥ 1.5 px. Frames and upcoming arcs ≥ 3:1 (`--line-dim` at 50%, not 35%). Dividers inside a window use `--rule`. |
| Glow | Static only (box-shadow, baked blur), never animated. No text-shadow under 18 px. |
| Shape | Night: square windows, near-square controls, pill buttons and tabs. Daylight: the Earth radii (12 / 18 / 24 px). |
| Type | Kickers and metadata: JetBrains Mono 12 px caps, tracking 0.12em, `--text-3`, ≤ 4 words, real data only. Titles and hero numbers: Barlow Condensed 600, caps for titles, tabular figures. Clock: JetBrains Mono. Reading text: Atkinson Hyperlegible Next 15/23, sentence case. Lexend for headings and buttons. No fake micro-text. |
| Reading | Long reading on the light sheet (`.jv-paper`), body at least 15 px, at most `--measure` (66 characters) per line, line height at least 1.5, no italics or capitals for emphasis. |
| Page header | `.jv-view__head`: crumb (`.jv-crumbs`, sentence case, Lexend 14 px, no underline; left out on top-level views) → h1 → subtitle (`.jv-view__sub`), on one left edge. |
| Controls | Chosen segments, switches and pills: a brighter frame (`--frame-on` / `--control`) and full-strength text. Never cyan, never terracotta. |
| Focus | 2 px `--text` outline, 3 px offset, a 5 px `--bg-0` gap behind it. Never cyan. Always visible for keyboard users. |
| Motion | Only for a state change. Feedback ≤ 100 ms; window assembly ≤ 300 ms (mechanical, hard stops); named exceptions: the wake beat (1.2 s) and the dock slide (700 ms). Ambient ≤ 8 running animations, `transform` and `opacity` only. Nothing waits for an animation. Everything stops under reduced motion, in the strip and when hidden. |
| Trust | Every claim carries a source chip. Confidence in words: Sure, Likely, Guess (`.jv-guess`). Every action has a receipt and an undo. |
| Calm | At most 4 amber or red marks outside the Rail. No streaks, points or confetti. |
| Copy | Sentence case in reading text, short. Errors say what to do next and never blame. |
| Accessibility | Text ≥ 4.5:1, meaningful UI ≥ 3:1 in both themes, with alpha composited (`python tools/contrast.py`), including text inside a dimmed window. Real buttons, labels, visible focus ring, full keyboard path. |

## Sizes
`full` (1080p and up), `laptop`, `strip` (Laptop A, static, nothing animates), `phone`, `ambient` (Laptop B idle).
