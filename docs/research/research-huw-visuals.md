# Huw Prosser's assistant UI: visual research for the Jarvis hub

Date: 2026-11-14. Method: built-in browser on De Wet's laptop. I removed Instagram's login modal, paused each reel at many timestamps, drew frames to a canvas (it was not CORS-blocked), zoomed in to crops of 2-4x, and sampled pixel colours from the decoded frames.

Sources: reels DYK2IWyoEWh (JARVIS, May 2026), DYEhKXXIW5Q (JARVIS speaking and standby), DYcGx6Do4rv (JARVIS gesture demo), DfGOQ5pIZqy and DfXwuL0izsO (his new assistant "ROSE", Oct-Nov 2026), Dfo8IADoLCj (Omarchy tablet, little UI), DZhpapYIOhH (3D gesture demo, not useful). Also huwprosser.com and his GitHub.

Caveat: every reel is a phone camera filming a monitor, so blacks are lifted and highlights clip. The hexes below are corrected estimates. The cleanest samples were the DYEhKXXIW5Q frame at 12.3 s and the ROSE card at 18.5 s.

**No orb code is public.** His GitHub (40 repos) has no `aiorb-react-component` or any other orb or UI repo. A GitHub search for "aiorb" found only unrelated projects. `jarvis-mlx` (538 stars, no licence file) is the old Python STT/LLM/TTS pipeline and has no UI. His blog post "Some thoughts on JARVIS" (12 May 2026) says he had to do "a lot of manual work on the UI". Everything below therefore comes from the videos.

---

## 1. Palette

| Role | Observed (camera) | Estimated true value | Notes |
|---|---|---|---|
| Background, centre | #0B1523 / #11182F | ~#0A1322 | Deep navy, never pure black |
| Background, edges | #142031 to #243152 | ~#101C30 | Soft radial vignette. The screen is a little lighter and bluer toward the top and edges, with a faint dark halo behind the orb |
| Grid | ~#202A3A | rgba(140,180,255,0.06-0.08) | 1 px square grid, about 1/30 of the screen width (~64 px cells on 1440p). Very low contrast |
| Orb ring (speaking) | #1385FF, #0E7CF1 | #1A86FF | Saturated electric blue, the strongest colour on screen |
| Orb glow | #164785, #33548D | blue at 25-40% alpha | Wide soft bloom, about 0.5 R past the ring |
| Core outline, wordmark | #FFFFFF | #F2F8FF | Thin, crisp, almost white |
| Window frame line | #B7FCFF core, #8ED6FF halo | #A8E6FF | Ice cyan with a 6-10 px outer glow (#2875AC to #084689) |
| Window fill | #05070B | rgba(3,6,12,0.85) | Near-opaque black-navy. Underlying content shows only faintly |
| Labels | #70A0B1 to #B5DEEE | ~#8FB8CC | Muted cyan-grey, uppercase mono |
| Status accent ("ACTIVE") | #FAF6C7 (clipped) | ~#FFD978 | Warm pale amber, the only warm colour in the JARVIS-blue system |
| ROSE accent | #AD2442 | ~#FF2D55 | The ROSE theme swaps blue for neon red-pink. Same layout |
| Map | navy land, lavender-blue roads, green park pins | — | Dark-styled map tinted toward the palette |

**Transparency and glow.** Light is added, never painted. Rings, frames and ticks are thin bright strokes, each with a blurred duplicate behind it (bloom). Fills are dark and close to opaque, which keeps text readable. Only the orb has a large, low-alpha radial glow. Brightness is graded: the orb is brightest, then active frame lines, then text, then the grid. That ordering is what makes it look like the film.

## 2. The orb

Geometry is measured from zoomed frames. R is the radius of the core circle (about 55 px on his 1440p screen).

| Layer | Radius | Weight / style | Motion |
|---|---|---|---|
| Core disc | 0-R | Fill slightly darker than the background (#0A1323). Covers the grid | Static |
| Core outline | R | 1.5-2 px, white at ~85% | Static. Wobbles a little in 3D when he speaks |
| Wordmark | centre | Geometric sans, caps, tracking ~0.25 em, cap height ~0.28 R | Static. Motion-blurs when the orb tilts |
| Inner arc segments | 1.12-1.2 R | Two or three white arcs, 2-3 px, 30-80° each. One brighter and thicker arc at about 7 o'clock | Rotate slowly, opposite to each other. Estimated 15-30°/s |
| Blue energy ring | 1.15-1.4 R | Idle: soft blue halo only. Speaking: solid #1A86FF ring 0.15-0.3 R wide with a bright inner edge | Width and brightness follow voice amplitude. Whole orb scales ±3-5% |
| Outer thin arc | ~1.45 R | 1 px, blue-white, ~60-90° | Slow drift |
| Dotted ring | ~1.9 R | ~40-48 dots, 1.5-2 px, white at 50-70% | Slow rotation, about 6-10°/s |
| Cardinal ticks | ~2.0 R | Short 1.5 px dashes at 12, 3, 6 and 9 o'clock | Static or slow |
| Diagonal hash marks | ~2.2-2.3 R | Groups of 2-4 parallel bars ("=" or "////"), 1.5 px, near 45° | Idle: still. Speaking: flicker and re-randomise bar count and angle every ~150-300 ms (glitch feel) |
| Loose particles | 2.2-2.7 R | 6-10 single bright dots, 2-3 px | Drift slowly, twinkle |

**States seen in the videos:**
- **Idle** (DYK2 8-12 s). The core outline and arcs are white, and the blue appears only as a soft halo. The ornaments are fully out. Calm, slow rotation.
- **Speaking** (DYEhK 12-16 s, DYcG 0.6-2.2 s). A thick, saturated blue ring with strong bloom. Ring width and orb scale pulse with the voice. The hash marks flicker. Sometimes the rings briefly separate in 3D (rotateX/Y ~10-15°) and snap back.
- **Wake / transition** (ROSE 0.5-2.5 s and 20-33 s). The rings are tilted about 70° in 3D and strung along a diagonal line that runs through them like an axle. They rotate face-on and collapse into concentric order in about 1.5-2 s. The same "exploded" tilt plays while the orb flies to the dock.
- **Standby** (DYEhK 20-23 s). The orb becomes a translucent blue sphere filled with a 3D field of twinkling particle dots, with a soft, slightly irregular edge and a few stray particles outside it. Under it sits a large monospace clock (22:03) and a tiny letter-spaced date (THURSDAY 7 MAY).
- **Docking** (DYK2 12-13.4 s). The outer ornaments retract inward first, leaving core plus ring. The orb then slides to the bottom-right corner in about 0.8-1 s and sits partly clipped by the screen edge. Content (here a full-screen dark map) fills the space behind it. In ROSE the docked orb keeps a mini version of all its rings.
- **Thinking.** Not clearly shown. The closest is the ROSE research card's scanning bar (section 3). The film convention would be faster arc spin plus a segment chase.

## 3. Widgets and windows

From the ROSE board (DfGOQ 37-45 s, DfXw 29-66 s). These reels use the red theme, but the structure is theme-independent.

- **Frame.** A 1-1.5 px ice-cyan rectangle with an outer glow, square corners and a near-opaque dark fill. No rounded corners.
- **Header, inside the frame.** A tiny uppercase letter-spaced mono kicker on the left ("RESEARCH // ACTIVE", "FIGURE // 2023", "NOTES // 1 / 4"), with a status word in the accent colour. On the right sit a type tag ("FACT"), a timer ("00:04") or an index ("01 / 02").
- **Footer, outside the frame.** Tiny mono metadata hangs just below the frame: "ADDED JUST NOW" on the left, and a hex ID plus number ("0x6EED · 20.5") on the right. It reads as instrumentation.
- **Content types:**
  - Big numbers ("≈20m", "$199 USD", "81 endpoints") in bold condensed caps, roughly 3x the title size
  - Bold uppercase titles of two lines at most
  - Short mono body text
  - Flat white bar charts with no axes and tiny labels
  - Segmented progress bars: about 30 blocks, with a bright 6-block chunk sweeping across as an indeterminate scan
  - Videos with minimal controls
  - Product images on white backgrounds
  - A tall phone-shaped social card
  - Red tag pills ("15% IN SALE")
  - Highlighted headline boxes
- **Glanceability.** Every card leads with one big thing: a number, an image or a two-line title. Images do the work of explaining. A product photo or video frame tells you the topic before you read anything, and the text then confirms it.
- **Density and arrangement.** The board is loose and slightly overlapping, with mixed card sizes: tall text columns at the edges and large media near the centre. It runs 12-18 cards deep over a dimmed live camera feed, which gives it the feel of a hologram on the desk. Small square accent markers are scattered across it.
- **Entry motion.** Cards arrive one at a time over ~0.5 s intervals. Each appears in place (scale and opacity) rather than flying in. The research card's timer and scan bar animate while it works. Exits were not clearly visible; "TIDY" and "CLEAR VIEW" buttons re-arrange or clear the board.

## 4. Chrome

- **Top edge.** A dotted ruler of evenly spaced tiny dots across the full width, with a thin outlined "notch" bracket at top centre (a line that steps down and back up, like a tab).
- **Bottom centre** (JARVIS). A small row of about 6 tiny monochrome icon buttons.
- **Top right** (ROSE). Outlined pill buttons in tiny mono caps: HISTORY, TIDY, CLEAR VIEW, CAMERA OFF (filled with the accent colour when active), a "CAMERA SOURCE" label and a "DEFAULT CAMERA" dropdown.
- **Bottom left** (ROSE). A status line in tiny mono with a thin progress line.
- **Clock.** Large monospace digits with a tiny tracked uppercase date underneath.
- **Page dots.** Small dot rows sit in card footers for multi-page cards.

## 5. What makes it feel alive and glanceable

1. Several layers rotate at different slow speeds and in different directions. Nothing is perfectly still and nothing is fast.
2. Audio-reactive width and brightness on a single saturated ring. Voice is instantly visible.
3. A small amount of digital noise: flickering hash marks, twinkling particles, a scan bar. It reads as "computing" without becoming busy.
4. A strict brightness hierarchy on a near-black navy field, with thin strokes and real bloom.
5. 3D moments: tilted rings at wake and while travelling. These are rare, which gives them a cinematic payoff.
6. Instrument-style metadata (kickers, hex IDs, timers) makes cards feel like system readouts.
7. One focal object at a time. The orb owns the screen until content arrives, then docks and gets out of the way.

---

## 6. Recommendations: Jarvis orb and HUD spec (SVG/CSS)

### Palette tokens (for `ui/tokens.css`)

Contrast is measured against #0B1523.

| Token | Hex | Use | Contrast |
|---|---|---|---|
| --bg-0 | #070C18 | Screen edges, vignette | — |
| --bg-1 | #0B1523 | Base | — |
| --bg-2 | #101D33 | Raised / centre lift | — |
| --grid | #8CB4FF at 7% | 1 px grid, 64 px cells | — |
| --panel | #03060C at 86% | Window fill | — |
| --line | #A8E6FF | Window frames, ticks | — |
| --line-dim | #A8E6FF at 35% | Inactive frames | — |
| --orb | #1E8BFF | Energy ring | 5.4:1 |
| --cyan | #38C8FF | Primary accent, links, active | 9.5:1 |
| --cyan-hi | #7ED8FF | Highlights | 11.5:1 |
| --text | #E8F6FF | Primary text | 16.6:1 |
| --text-2 | #9FC3D9 | Secondary text | 9.9:1 |
| --text-3 | #7FA3BC | Kickers, metadata | 6.9:1 |
| --ok | #4ADE9B | Success | 10.7:1 |
| --warn | #FFC24A | Warning, "ACTIVE" status (echoes his amber) | 11.4:1 |
| --crit | #FF4D5E | Critical | 5.7:1 |

All text pairs pass 4.5:1. For readable text, use --text-2 or --text-3, never the 35% dims.

### Orb SVG structure

Use `viewBox="-100 -100 200 200"` with R = 36 (scaled up, this is about 128 px of core diameter in a 360 px orb). Each layer is a `<g>` that gets its own `transform: rotate()`, with `transform-box: fill-box; transform-origin: center`.

1. `halo`: a `<circle r=60>` filled with a radial gradient from --orb at 35% to 0. Animate opacity and scale only.
2. `core`: a `<circle r=36>` with fill --bg-1 at 95% and stroke #F2F8FF at 85%, 1.5 px. Your own wordmark or initials go in the centre; do not copy his JARVIS lettering.
3. `energy`: a `<circle r=46>` stroked with --orb at a base width of 3 px. Its width is driven by an amplitude level that is pre-bucketed to steps. Changing stroke-width costs paint at this tiny size, so either keep it here or animate a `scale` on a second, thicker ring for zero-paint updates. Add a duplicate under it with `filter: blur(4px)` (one static SVG filter, never animated) for bloom.
4. `arcs-a`: two arcs at r=41, 2 px, `stroke-dasharray` making 70° and 40° segments. Rotate clockwise at 20°/s.
5. `arcs-b`: one 3 px bright arc at r=43 near 210°. Rotate anticlockwise at 12°/s.
6. `outer-arc`: one 1 px arc at r=52, 80°, --cyan-hi at 60%. Rotate clockwise at 6°/s.
7. `dots`: a `<circle r=68>` with stroke-dasharray `0 8.9` and round caps, which gives 48 dots from a single element. 1.8 px, white at 60%. Rotate anticlockwise at 8°/s.
8. `ticks`: 4 cardinal dashes at r=72.
9. `hash`: 4 groups of 2-4 bars at r=80, on the diagonals. They flicker (opacity toggles and a re-chosen bar count) every 200 ms, while speaking only.
10. `motes`: 8 dots of 2-3 px at r=78-95. They twinkle via opacity with staggered 2-4 s durations.

### States

Each state sets a class on the orb root. Transitions take 250-400 ms ease-out.

- **idle**: energy ring at 1.5 px and 40% opacity, halo at 30%, all rotations at base speed.
- **listening**: energy at 3 px and 80%, a halo that breathes (scale 1.00 to 1.04 over 1.6 s), dots brightened to 80%.
- **thinking**: arcs at 2.5x speed, a segment chase on the dotted ring (stroke-dashoffset animation), hash marks shown at 50%. Cards in progress get his 30-block scan bar.
- **speaking**: the energy ring follows amplitude (width 3-10 px or scale 1.00-1.06), halo at 70%, hash marks flicker.
- **alert**: the energy stroke changes to --warn or --crit and there is a single 600 ms pulse. Never strobe.
- **standby**: fade the rings out and show a particle sphere (about 40 SVG dots inside r=40, each drifting with a slow translate, plus a feTurbulence-free wobble from scale on 2 nested circles), with a large mono clock below.
- **wake**: a one-off 1.2 s sequence. Rings start at `rotateY(70deg)`, offset along a diagonal by CSS translate, then return to 0. Use CSS 3D transforms on HTML-wrapped SVG layers. This is the cinematic beat; play it only on wake.

### Dock

Retract layers 6-10 first (scale 0.6 and opacity 0, 200 ms). Then translate the whole orb to bottom-right at 40% scale with a 700 ms cubic-bezier(.2,.8,.2,1). Let it clip slightly at the screen edge as he does, or keep it fully inside on Laptop A. Content fades and scales in from 0.98 behind it.

### HUD

- Background: --bg-1 plus a radial vignette to --bg-0, the 64 px grid at 7%, a dotted ruler along the top edge, and a notch bracket at top centre. All static.
- Cards: a 1 px --line border, an outer `box-shadow: 0 0 8px` of --cyan at 35% (static) and a --panel fill.
  - Kicker: 11 px mono, uppercase, letter-spacing 0.18 em, --text-3.
  - Title: 600-700 weight condensed caps.
  - Hero number: about 3x the title size.
  - Footer metadata sits outside the frame in 10 px mono.
  - Lead every card with one image or one number.
- Card entry: opacity 0 to 1, scale 0.97 to 1 and a 1 px border "draw" (stroke-dashoffset on an SVG rect), 220 ms, staggered 60-80 ms.
- Card exit: opacity only, 150 ms.

### Performance and accessibility

- Animate only transform, opacity and stroke-dashoffset.
- Drive everything from CSS animations. Use one rAF loop capped to 30 fps (skip frames by timestamp), only for the amplitude and hash flicker.
- Pause everything with `animation-play-state: paused` on `document.hidden` (visibilitychange) and when the orb is off-screen (IntersectionObserver).
- Blur filters are static; never animate a filter.
- `prefers-reduced-motion`: stop all rotation, flicker and twinkle, and skip the wake and dock tweens (snap or 150 ms crossfade). Show state only through ring colour and opacity, with a text status label for each state.
- Laptop A strip: a static orb only, with state shown by colour and opacity, and no motion (per the CLAUDE.md rule).
