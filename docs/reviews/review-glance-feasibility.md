# Review: HUD v2, glanceability, "nothing gets away", accessibility, feasibility

Fresh reviewer, 2026-11-14: design doc, both research files, repo v0.2.2, demo screenshots at 1440×900. No repo edits.

**Verdict:** right direction, but six code paths still lose things, it clashes with the overseer's checklist and tests, and N1–N7 collide on about eight files. All fixable before building.

## 1. Findings

### 1.1 Glance test (one second)
| Screen | A glance tells him | It still doesn't tell him |
|---|---|---|
| Ambient | Time, Jarvis's state, how full the day is, roughly what's next (dial) | Which arc is which (no labels); what's waiting or new (the Rail isn't on ambient) |
| Now with windows | Up to 6 windows with picture, number and shape; Rail counts | The dial on the docked orb (32 px today; "~40%" undefined). The Rail collides with the status line, caption and orb on the bottom edge |
| Today, Life, Activity | Nothing new: §4–5 cover only ambient and Now | Whether the Rail and marks show here; if not, things get away off Now |
| Phone | Not specified; the bottom tab bar is where the Rail would go | n/a |
| Laptop A strip | Orb colour, word, next up | Worst state and new count |

**Codes:**
- Five of seven shapes are rings (check, arc, reticle, open, dashed), not pre-attentively distinct; only diamond and triangle pop out.
- "In progress" uses the undefined `--hud` and lands on the same cyan as "Jarvis".
- Corner brackets mean three things: active window (`window.js`), Soon, Critical.
- Rail (24 marks) + dial + orb + 6 windows is too much at once; cap amber/red marks.

**Images:** "every item carries an image" has no source and no contract field, and the demo can't ship his real slides. Sources that exist:
- **PDFs:** PyMuPDF renders the question's page at file time (~10–30 ms).
- **PPTX:** `docProps/thumbnail.jpeg` from the zip, or the Windows shell thumbnail.
- **Courses:** the Canvas `course_image` (`image_download_url`, often empty), falling back to our own course monogram.
- **Videos:** the YouTube `mqdefault.jpg`, or the Panopto `ThumbnailUrl` (check his tenant).
- **Others:** plotter → its SVG; people → initials; homework → the attached PDF page or icon + monogram.
- **Buildings:** a big room code ("ENGR 1A10") tells them apart better than a photo.

### 1.2 Paths where things still get away
1. **The 6th window is deleted:** `events.py apply_event("window.push")` (`MAX_WINDOWS = 5`) and `windows-core.js placeWindow`.
2. **The 60 s lifetime deletes:** `presence.js` WindowClock → `bridge.act("close")`. The design never mentions it.
3. **Step-aside leaves no trace:** `windows.js arrange()` drops `left` windows.
4. **Moves look like closes:** `_reorder` sends close + push, so a dock-on-close Rail would flicker and set false "new" marks.
5. **Removed outright:** `close_all` / CLEAR VIEW, and expired approvals (`_resolve` → `window.close`).
6. **Timers erase things:** toasts and captions vanish after 6–8 s, so what Jarvis *said* is lost; finished jobs drop out of `jobs`.
7. **Silent edits in place:** `branch/nowcard/day.updated` overwrite data (a moved due date), the 64%-missed case.
8. **Design gaps:**
   - The Rail is client-side, so docking on one device loses it on the others.
   - No slot for approvals, learned facts or what Jarvis said; hovering clears marks too easily.
   - The Rail isn't on ambient, the other tabs, phone or strip.
   - Items leave only when done or archived, so the Rail becomes a pile.

### 1.3 Accessibility (WCAG contrast; colour blindness simulated with Machado 2009)
- **Dark surfaces pass:** every text and state colour on `--bg-0/1/2` and the panel `#04080F` (text-3 7.5, crit 6.2, orb 5.0:1 on bg-2).
- **`--line-dim` at 35% fails:** 2.6:1 where frames show bounds; 50% gives 4.2:1.
- **The light sheet fails every state colour:** warn 1.5, ok 1.6, cyan 1.8, crit 3.0:1 on `#F5F8FC`, including the Q7 highlight.
- **Colour blindness:** deutan ok vs crit drops from ΔE 124 to **24**; protan crit drops to 4.1:1; tritan ok vs cyan is ΔE 12. Shapes must carry it, yet "Done" is one of five rings.
- **Focus:** a cyan ring on cyan frames looks like "active window".
- **Kickers:** 11 px caps mono reads slowly and breaks the shipped ≥ 12 px rule. Glow on small text hurts readers with astigmatism.
- **Motion:** keep the hash flicker (3–7 Hz now) at ≤ 3 changes/s.
- **Screen readers:** no text alternative yet for the dial, Rail or marks.

### 1.4 Feasibility
- **Animation cost (main risk).** WebView2 doesn't composite transforms on SVG *child* elements, so each rotating `<g>` repaints the whole orb and its blur on the main thread every frame. Fix: one `<svg>` per moving layer inside a `will-change: transform` `<div>`. The 30 fps cap only applies to the JS level loop.
- **The node budget is already broken:** `now-active` has 308 nodes and `now-crowded` 405, before v2. A 30-block bar must be 2 elements and 48 dots 1 element.
- **Laptop A:** the static strip meets C37 (≤ 3% CPU) easily. Plan §12 says ≤ ~1%; pick one.
- **PDF.js** (pdfjs-dist 6.5.438, Apache-2.0, measured): ≈ 6.2 MB vendored, ≈ +2.5 MB installer.

  | File | Size |
  |---|---|
  | `pdf.min.mjs` | 464 KB |
  | worker | 1.3 MB |
  | viewer `.mjs` / `.css` | 316 KB / 168 KB |
  | cmaps | 1.7 MB |
  | standard fonts | 820 KB |
  | wasm | 1.4 MB |

  - Offline with local `cMapUrl`, `standardFontDataUrl` and `wasmUrl`; `hexlint` already skips `vendor/`.
  - Open at page + y with `scrollPageIntoView({pageNumber, destArray:[null,{name:"XYZ"},null,y,null]})`; track with `pagechanging` and `updateviewarea`.
  - Laptop A streams from B via `/api/file/<id>` with HTTP Range (check Starlette, or set `disableRange`). Build the question index at filing time, because OneDrive's first open downloads the file.
  - It uses canvas: exempt the reader from "no canvas", and keep it off ambient and the strip.
- **Contracts:** new fields (`docked`/`slot` on windows, `window.dock`/`window.order` events, `marks`, `thread`, `thumb`, dial data) all touch `state.schema.json` and `state.json`. `day.schema` allows HH:MM times only, so a dial that crosses midnight needs ISO times.
- **Demo clock:** pinned to **Mon 2026-11-16 15:40**, so today it is two *days* wrong, not two hours. `scenario.py` hard-codes "Wednesday at 8", "3:20" and "at 4"; tests hard-code 2026-11-16 about 8 times.
- **Tests that will break:** `test_tokens.py`, `contrast.py` (2 themes, no alpha), the "one loop" test, `test_now_canvas` step-aside, `test_server` eviction and the `test_windows` lifetime.
- **Plan checklist:** plan §3 rules 2–6 (terracotta, warm only, no neon, round radii, one loop) would make the overseer reject every N package.
- **File collisions in N1–N7:** `events.py` (N4, N6, N7); contracts and `state.json` (N3, N4, N6, N7); `store.js` (N4, N6); `now.js` (N2, N3, N4, N6); component CSS (N1, N5); `server.py` (N5, N6). Phone, strip, Today, Life and Activity have no owner.

## 2. Changes, ranked

### MUST
1. **Tokens keep their names.**
   - Night = `:root[data-theme="night"]` setting existing names (`--canvas`=bg-1, `--card`=panel, `--muted`=text-2, `--accent`=cyan…); HUD-only tokens get Daylight values in `:root`.
   - Retire Evening (dark = Night; Sunset = Daylight by day, Night after dark), keeping 2 themes and 210 shots.
   - `--line-dim` = `#A8E6FF` at 50%; define or drop `--hud`; `contrast.py` gets a night block and alpha compositing.
2. **Light-sheet inks** (contrast on `#F5F8FC`):

   | Token | Hex | Contrast |
   |---|---|---|
   | `--ink-warn` | `#8A5300` | 5.9:1 |
   | `--ink-ok` | `#1D6B45` | 6.1:1 |
   | `--ink-cyan` | `#0B5FA5` | 6.2:1 |
   | `--ink-crit` | `#B3261E` | 6.1:1 |
   | `--ink-text` | `#14202E` | 15.5:1 |

3. **Rewrite plan §3 rules 2–6 and the motion test before any worker starts.** New rule: ≤ 8 running animations on ambient, all on HTML elements, keyframes using only `transform` and `opacity`.
4. **The Rail tracks things, not windows.**
   - A window views a thing (approval, due item, thread, message, job). Close, lifetime, eviction, step-aside, CLEAR VIEW and an expired approval all set `docked:true` in that thing's slot.
   - Pure views (chart, next_up) just close. Dedupe by `ref`; anything idle 7 days folds into Parked's count.
   - `window.close` only for done or archive; add `window.dock` and `window.order` (no more close+push moves).
   - The Rail lives on the server, so every device agrees.
5. **Rail layout.**
   - Six fixed slots: Your yes · Today (classes, calendar, blocks) · Homework · Messages · Jarvis (jobs, learned facts, last 10 spoken lines) · Parked.
   - On every tab. On ambient it is static and shows only filled slots; tier 2 hides when others are present.
   - Phone: a 44 px row above the tabs. Strip: worst shape + "N new".
   - Bottom band: status line left, Rail centre (48 px), caption above, orb right; `maxRows()` leaves room.
6. **"Since you looked" marks on the server:** `marks {ref:{what, at}}`.
   - Made by field diffs ("Due moved Wed 8 pm → Thu 11:59 pm"), toasts, captions, finished jobs and expired approvals.
   - Cleared by opening, keyboard focus, ≥ 800 ms hover on the *item*, or "Mark all seen"; never by ambient display.
   - Screen readers: at most one polite announcement a minute.
7. **One meaning per mark.**
   - Corner brackets only mean "wants you" (Soon, Critical, Your yes).
   - The window Jarvis means: a 1.5 px `--line` frame and a reticle in its kicker (one reticle at most).
   - Done: a filled `--ok` disc with a dark check, ≥ 16 px.
   - In progress: an ice `--line` arc, so cyan always means Jarvis.
8. **Focus ring:** `outline: 2px solid var(--text); outline-offset: 3px; box-shadow: 0 0 0 5px var(--bg-0)`. Never cyan.
9. **Orb build.**
   - Composited layers (§1.4); no filter on rotating layers; bloom baked into static and scale-only layers.
   - One 30 fps rAF loop for `level` only, paused when hidden, off screen, in game mode and on the strip.
   - Hash flicker ≤ 3 changes/s, opacity 0.5↔1, off under reduced motion. Docked orb 120 px (64 px on laptop size).
10. **Node budgets:** decoration ≤ 250 nodes; the whole page ≤ 1,200, enforced by a test on `now-crowded`.
11. **Demo re-basing:** `demo/rebase.py` shifts every ISO time by `now − fixture_now`, in `app.py` demo mode only. Scenes and tests stay frozen at 2026-11-16, so today's tests pass. Captions are built from the shifted times, weekdays included.
12. **Contracts v2 first, with one owner (N0).**

### SHOULD
1. **Day dial as a 12-hour clock face** (now − 1 h to now + 11 h), so it reads like a watch with no am/pm overlap.
   - Ring at 2.5 R; 12 ticks (longer at 12/3/6/9); "now" hand 2 px `--text`.
   - 4 px arcs: classes `--line-dim`, next `--cyan`, done `--ok`, moved or missed dashed `--text-3`. Due: 9 px `--warn` diamond; overdue: `--crit` triangle.
   - Only the next item is labelled, 12 px ("4:00 · GE 122 · ENGR 1A10").
   - Updates once a minute; `role="img"` summary; the server supplies `day.dial[]` in ISO times.
2. **Kickers:** 12 px, tracking 0.12em, ≤ 4 words in caps. No text-shadow below 18 px. Metadata outside the frame is never the only copy of a fact.
3. **"≤ 4 compete"** means at most 4 amber or red marks outside the Rail; the rest only raise their slot's count.
4. **`thumb {src, kind, alt}`**, served as `/api/thumb/<key>.webp` (320 px, ~10 KB), cached in Jarvis's memory folder, never git. Demo thumbnails are made-up slides drawn by a tool.
5. **PDF reader** as in §1.4; target ≤ 400 ms warm to open at Q7, measured on both laptops.
6. **Reduced motion:** wake and dock are instant, critical brackets become static 3 px, and the scan bar becomes "Working · 60%".
7. **After game mode:** "While you played: Homework 1, Messages 2".

### NICE
A hollow reticle vs a filled disc (tritan safety) · a building photo only when the building changes · `Alt+1–6` focuses a Rail slot.

## 3. Work packages (≤ 6 at once; no file in two rows)

| ID | What | Owned paths | Depends on |
|---|---|---|---|
| N0 | Contracts v2 (overseer, serial): schemas, reducers, `apply_event` hooks, route stubs, Rail/dock regions, `ambient.js` split, plan §3 | `contracts/`, `docs/contracts.md`, `tests/test_contracts.py`, `ui/core/store.js`, `jarvis_hub/events.py`, `jarvis_hub/server.py`, `ui/index.html`, `ui/core/shell.css`, `docs/hub-build-plan.md` | — |
| N1 | Night tokens, sheet inks, focus ring, base kicker/frame/pill classes, theme choices | `ui/tokens.css`, `ui/base.css`, `ui/core/theme.js`, `tools/contrast.py`, `tests/test_tokens.py`, `tests/test_contrast.py`, `docs/DESIGN.md` | — |
| N2 | Core orb | `ui/components/orb/`, `tests/e2e/test_performance.py` | N1 |
| N4 | Rail, docking instead of deleting, marks | `ui/components/rail/`, `ui/core/windows.js`, `ui/core/windows-core.js`, `ui/core/presence.js`, `ui/views/now/now.{js,css}`, `jarvis_hub/rail.py`, `tests/e2e/test_windows.py`, `tests/e2e/test_now_canvas.py`, `tests/test_rail.py` | N0, N1 |
| N5a | Glance and thumb components, domain icons, thumbnail cache, Night pass on the Now-side components | `ui/components/{glance,thumb,window,big-number,file-tile,now-card,working-on,caption,branch-card}/`, `ui/core/dom.js` (ICONS only), `jarvis_hub/thumbs.py`, `tools/make_demo_thumbs.py` | N0, N1 |
| N5b | Night pass on the other tabs | `ui/components/{timeline,action-row,approval-card,fact-card,source-chip,notice,mini-chart,tabs,status-line,command-bar,clock,plant}/`, `ui/views/{today,life,activity,memory,branch,controls,hood}/`, `ui/views/views.css` | N0, N1 |
| N6 | Work threads, question index, resume card, PDF reader | `jarvis_hub/threads.py`, `jarvis_hub/pdfindex.py`, `ui/vendor/pdfjs/`, `ui/views/reader/`, `ui/components/resume-card/`, `tests/test_threads.py`, `tests/e2e/test_reader.py` | N0, N1 |
| N7 | Demo re-based to real time, richer fixture, character captions | `jarvis_hub/demo/`, `contracts/examples/state.json` (after N0), `app.py` (demo flag), `tests/test_demo.py` | N0, N5a (thumb keys) |
| N3 | Day dial and the ambient screen | `ui/components/day-dial/`, `ui/views/now/ambient.js` | N2, N4 |
| N8 | Phone and strip: Rail row, worst state, game-mode recap | `ui/views/phone/`, `ui/views/strip/` | N4 |

**Waves:**
- Wave 0: N0 and N1 together.
- Wave 1: N2, N4, N5a, N5b, N6, N7 (six agents).
- Wave 2: N3 and N8, then the fresh design, accessibility and walkthrough review, then the release.

Every package registers its scenes in its own files, as `registerScene` already allows.
