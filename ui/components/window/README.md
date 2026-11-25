# jv-window (C06, Night pass N5a, HUD v3 glass P3, clean windows v0.4.1)

The Night HUD window (HUD v2 §3). `<jv-window heading="PPS 7" status="Due" index="01 / 03" meta="Syllabus p.3"
glance="soon" working="0.6" window-id="w-1" active pinned named dim docked>content</jv-window>`

- **Glass (HUD v3 §14 decision 3):** the element carries `.jv-frame` and becomes a slab of glass: square corners
  in both themes, a see-through fill (`--glass-strong`; `--glass` with `sheer` or `media`), a bright thin edge
  (`--glass-edge-rest`, near-white at about 70%; `--glass-edge` on the window Jarvis means) and two ghost edges behind it, 4 and 8 px down-right (`--glass-ghost`, `--glass-ghost-2`;
  only their right and bottom edges, which fall outside the panel). No backdrop blur: the panel paints the
  page's own grid and vignette (fixed to the screen, so they line up) under its tint, so the grid shows through
  but another window never does, and text always sits on measured colours (`tools/contrast.py`). The metadata
  hangs 12 px under the frame, below the ghosts.
- **The one anatomy (HUD v2 §14.2, attribute `clean`; the canvases set it on every window):**
  1. the **kicker row**: `heading` // `status` in small mono caps in the one accent (`--cyan`), SOURCE // TOPIC
     ("GE 122 // PPS 7"); one `index` or time on the right in grey (`--text-3`; "Pinned" when it is pinned and
     has no other). No icon glyphs: only a "wants you" mark (diamond, square, triangle) may lead the kicker, and
     it is the one amber or red thing on the window.
  2. **one hero**: media edge to edge (`.jv-pane--media`, under the static `--media-tint` so a white page never
     outshines text), a big number (`<jv-big-number bare>`, near-white, never amber), a flat chart
     (`<jv-mini-chart bare>`: near-white bars, tiny grey labels) or a title in condensed caps, two lines at most
     (`.jv-pane__title`).
  3. **at most one line** of supporting text (`.jv-pane__line`: one line, cut with an ellipsis).
  4. **one footer item** under the frame (`meta`: "Added 3:41 pm").
  `views/now/widgets.js` builds it (`pane()`, `windowKicker()`). Colour budget: accent, near-white, grey, the
  media's own colours and that one mark. The cyan title plate (`--title-plate`) is only on the hero title of
  the window Jarvis means (`active` or `named`), wrapping line by line.
- **The "Why?" drawer:** a `.jv-more` block in the content holds everything else: sources, details and controls
  (a question's Yes / No / Change it, a fact's actions, the chart's numbers, "Open it"). It is real content,
  always in the Tab order and read by screen readers; it is drawn under the window (over it when there is no
  room: `why-up`) only while the pointer rests on the window (350 ms) or keyboard focus is inside (at once).
  Where nothing can hover (touch, the phone) it is simply open. Voice does everything as before.
- **No buttons on the cards:** with a mouse, pin and close show only on hover or keyboard focus (opacity, over
  the top-right corner; still real, labelled buttons in the Tab order). Touch and the phone keep them showing.
- **On a canvas's cluster** (stage/canvas.js): `opens` = the panel is its own "Open it" (the content's
  `[data-key="open"]` stays a real button for keyboard and screen readers but isn't drawn; a click on the panel
  that isn't on another control presses it; focus on it rings the whole panel). Clicking a question's window
  opens it in Activity; it never answers it. `media` = a picture leads; `sheer` = one big number.
- **One meaning per mark:** `active` (the window Jarvis means) = a brighter frame (and the title plate), CSS
  only. Corner brackets, in the frame's own ice, only for `glance="soon|yes|critical"` ("wants you"; critical
  moves ±2 px for 5 s, then holds) and while `named` (Jarvis is naming it as he speaks: set it from `ui.focus`;
  the brackets snap on in 250 ms in the accent). `marked="<what changed>"` draws the static cyan "since you
  looked" notch on the top edge, with the change read to screen readers. The canvas sets all of these.
- **Depth:** when one window is `active`, its siblings sit back (88% opacity in Night; in the aligned cluster they
  never scale, which would break the shared edges); `dim` forces it.
- **Working:** `working="0.6"` (or empty for "can't tell"): a segmented scan bar (~30 blocks, 2 elements) with a
  sweeping cyan chunk; reduced motion shows "Working · 60%".
- **Assembly:** pushed windows (with `window-id`) assemble mechanically on first appearance, ≤ 300 ms (brackets
  snap 80 ms → frame draws 120 ms → kicker resolves 100 ms → lock 80 ms, `cubic-bezier(.2,.9,.1,1)`). It is an
  overlay: content is usable from 0 ms. `assemble({ from: rect })` replays it growing out of a rect (a recalled
  window leaving its Rail slot). Nothing plays when nothing may move.
- **Fitting its area** (set by the window canvas, stage/canvas.js `fit()`): `data-fit="compact"` makes
  the hero number smaller. `data-clipped`: it still
  can't fit and nothing could step aside, so a fade and "More ↓" show at its foot (never a silent cut).
- `docked` windows are never drawn. Pin and close emit `jv-act` `pin` / `unpin` / `close` (the hub docks on close).
- `setContent(...nodes)` swaps the body; `firstTool` is the first pin/close button; add `leaving` to fade out.

Scene: `?scene=component:window` (resting, active, pinned, kicker/index/meta, the three "wants you", working,
named, focused and unfocused, assembling frozen mid-way, docked, inside a page, and on the board: media edge to
edge, a big number, the one Jarvis means with its title plate, pin and close shown as on hover).
