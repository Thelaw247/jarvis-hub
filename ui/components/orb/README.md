# jv-orb: the Core (N2; HUD v3 look P1)

Jarvis's face, built from Huw Prosser's orb layer by layer (HUD v2 §4, §7, v3 §14; `docs/research/research-huw-visuals.md`
§2, §6). R = the core's radius; the orb's box is 220 units across with R = 36, so the motes at 2.95 R just fit.

**v3 look (§14):** the lines (core outline, arcs, dotted ring, ticks, hash marks, motes) are near-white
`--orb-line`. At rest (idle, thinking) there is only a faint, soft blue halo and no energy ring. The deep blue
`--orb` fills the energy ring only while listening or speaking, with Huw's glow, all static gradients baked into the ring's layer (no filter, nothing animated but its scale and
opacity): a wide faint bloom falling off over ~0.4 R outside the band, a lighter line on the band's outer edge
(`--orb-edge`), the saturated body, a shade toward its inner edge (`--orb-deep`), then the dark gap and the core's
near-white outline.
Docked (corner size, or a centre orb with `docked`): white rings only; listening and speaking show as a thin white
energy ring that follows the voice. Amber (waiting, warn), red (crit) and grey (muted, offline) are unchanged.

| Layer | Where | Moves |
|---|---|---|
| Halo | 0–1.7 R | breathes while listening; scales with the voice |
| Core + JARVIS | R | still, baked bloom (Night) |
| Inner arcs a (1.1 R), b (1.55 R, the bright thick one) | 1.1–1.55 R | counter-rotate 20°/s and 12°/s; 2.5× while thinking |
| Energy ring | 1.15–1.42 R (glow to ~1.84 R) | listening/speaking only; follows the voice level by scale + opacity (the loop), never a repaint |
| Outer arc | 1.7 R | 6°/s drift |
| Dotted ring | 1.9 R | 48 dots from one dashed circle, 8°/s the other way; tightens on a wake |
| Ticks | 2.0 R | still; four bare dashes (no readouts: latency and sync times are in Controls › Under the hood) |
| Hash marks | 2.2 R | step in order with the voice while speaking (≤ 3 changes/s) |
| Day dial slot | 2.5 R | the day dial mounts here; drawn only with the `dial` attribute |
| Motes | 2.75–2.95 R | twinkle (two groups) |

## Use
```html
<jv-orb state="listening" size="centre"></jv-orb>
```
- `state`: the orb_state contract (`idle listening thinking speaking waiting muted offline`) plus `standby`
  (the quiet ambient screen: the particle sphere, scaled to about the awake orb's hash ring, with the wordmark on
  it; the orb draws no clock, the host puts `<jv-clock live small>` under it) and `alert`.
  Unknown values draw as idle. `ORB_WORDS` (exported) are the words for the status line, strip and screen readers.
- `size`: `centre` (default), `corner` (the docked mini rings: 120 px; 64 px at laptop size), `strip` (16 px, one
  still SVG). The centre orb's box comes from the host: set `--jv-orb-size` on it or a parent. The default,
  `clamp(160px, min(22vw, 40vh), 480px)`, puts the outer ornaments (ticks, hash marks) at about 1/6 of the screen's
  width and the core's radius at about 1/28 of it, as in Huw's reels.
- `dial`: draw the day dial (a child with `slot="dial"`) at 2.5 R. Off by default since v3 (the home screen has
  nothing around the orb); the ticks are bare.
- `alert="warn|crit"`: amber or red ring, one 600 ms pulse, the word under the core; `crit` plays the low tone.
- `wake="full|tighten|none"`: the beat the next wake plays (idle, standby, muted or offline → listening).
  Default `tighten` (250 ms). Set `full` only for the first wake of the day or after ≥ 4 h away; `wakeKind(lastWake, now)`
  (exported) says which. Listening is drawn from the first frame either way; the full beat plays the wake earcon.
- `docked` (centre size): outer layers retract (200 ms), then the orb slides and scales to `#dock` (or the
  selector in `dock-to`) as mini rings (700 ms). Fires `jv-orb-docked`; removing it slides back and fires
  `jv-orb-undocked`. Docking again within 60 s of the last dock is instant. Reduced motion: instant.
- `openable`: the orb is a button ("Show the full view") that fires `jv-orb-open`.
- `.orb = orb_state` (level, countdown_s, window_s). `.level = 0.7` sets the level directly (a local meter).
- No readouts: the cardinal ticks are four bare dashes (Huw's). Latency and sync times live in Controls › Under the
  hood; the orb's state is still read out to screen readers (`aria-label`, the status line).
- No pulsing (v0.4.1): nothing scales with the voice. While Jarvis speaks the rings turn faster (a second, nested
  spinner runs or holds, so the angle never jumps) and only the opacity of the static glow follows the level. Every
  ring layer stays centred to within 1 px (`tests/e2e/test_orb.py`).
- Text in the core never drops under 12 px: "AWAITING" hides under 315 px (YES alone), JARVIS under 220 px, and
  the docked or corner orb shows none (the amber ring, the status line and the Rail carry the state). The state
  word sits on a small plate between the energy ring and the hash marks.
- `data-offstage` (set by a view that hides the orb, e.g. the Stage's centre orb while windows are up): no
  animations and no level loop, as when off screen.
- `.dialSlot`, or a child with `slot="dial"`: a square box whose inscribed circle is the 2.5 R ring.

## Motion and performance
- Each moving layer is its own `<div>` (composited) with its own small `<svg>`; no filters on moving layers.
- Animated properties: `transform` and `opacity` only, plus the waiting drain's `stroke-dashoffset` (48 steps
  over the answer window; no number, ever).
- One shared rAF loop at ≤ 30 fps, only for the voice level, only while listening or speaking and only while the
  level is still changing. Paused when the page is hidden, the orb is off screen (IntersectionObserver) or a game
  is on (`now_card.moment = game` or `settings.game_mode = on`); CSS motion pauses with it.
- On ambient: 6 running animations idle, 7 listening, 8 thinking, 6 speaking (plan limit 8).
- Reduced motion and the strip: a still pose per state, with the word under the core (dashed ring for thinking).
- Nodes: ~110 (centre), ~65 (corner). `tests/e2e/test_performance.py` and `tests/e2e/test_orb.py` check all this.

## Scenes
`?scene=orb-<standby|idle|listening|thinking|speaking|waiting|alert-warn|alert-crit|muted|offline>` (full or
`&size=laptop`), `orb-wake` (the full beat), `orb-tighten`, `orb-docked`, `orb-docked-listening` (white rings
only), `orb-dial` (with the day dial), `orb-strip` (strip size), and the gallery `component:orb`. Add `&motion=full&freeze=<ms>` to hold a moving beat for a screenshot.

## Sounds
`ui/sounds/earcons.js` (wake, tick, critical; see `ui/sounds/README.md`).
