# Jarvis — Hub Build Plan (parallel agents, Fable 5.2 overseeing)

Last updated: 2026-11-14 (evening: design checklist rewritten for the Night HUD; phase N for hub v0.3.0 added)
Status: **approved to start.** The step-by-step plan for building the Jarvis hub as a launchable Windows desktop app in the private GitHub repo `Thelaw247/jarvis`, built by parallel agents under a Claude Fable 5.2 overseer. Part of the design set in Jarvis/. Covers milestone M1.7 (Hub v1) of JARVIS_BUILD_PLAN.md, pulled forward: the hub is built first against a **demo backend**, so it doesn't wait for `jarvis-core`.

**Built from:** JARVIS_DESIGN_HUB_TRUST.md (views, trust, Earth HUD, widget push), JARVIS_DESIGN_LIFE_TREE.md (Life Map, branch cards), JARVIS_DESIGN_WINDOWS_RESEARCH.md (windows, research on screen), JARVIS_DESIGN_MEMORY.md (now card, facts, audit), JARVIS_DESIGN_RUNTIME.md (approvals, undo, SSE), JARVIS_PSYCHOLOGY.md (A1–A11, E3–E5, K1–K7, code of conduct), JARVIS_BUILD_AND_CONSISTENCY.md (definition of done, skills), JARVIS_CONSTRAINTS.md (C7–C10 latency, C37 Laptop A), and the real Pen Reader repo (`Thelaw247/Pen-Reader`: CSS tokens, plants, mock bridge, pywebview launcher, Inno Setup installer, release workflow).

---

## 1. What we're building

**Jarvis Hub**: one desktop app, `JarvisHub.exe`, installed on Laptop A and Laptop B.
- Opens a native window (pywebview/WebView2, like Pen Reader) showing the hub UI.
- **Demo mode** (default until `jarvis-core` exists): a built-in demo backend plays realistic data and a scripted day (arrival → debrief → "pull up PPS 7" → "what's going on with GE 122?" → "plan my week" approval), so every screen can be used and checked now.
- **Live mode** (later, P1 M1.7/H5): the same window points at the hub on Laptop B over Tailscale; nothing in the UI changes because both modes speak the same **contracts** (§5).
- **Ambient mode** on Laptop B's screen: full-screen idle orb + clock.
- **Strip mode** on Laptop A: small, static, always-on-top.

**Look (from v0.3.0):** the **Night HUD** (`docs/design/JARVIS_DESIGN_HUD_V2.md`): Huw's layout, palette, windows and orb, with the films' HUD grammar. It replaces the "Earth HUD" look of HUB_TRUST §5; the trust rules, views and widget push in HUB_TRUST §1–§4 stay. Themes: **Night** (default everywhere), **Daylight** (the Earth HUD tokens, for bright rooms) and **Sunset** (Daylight by day, Night from Saskatoon's real sunset). The old Evening theme is retired.

---

## 2. Navigation (easy to get around)

Rules from the psychology research, made concrete:

| Rule | Hub behaviour |
|---|---|
| **≤ ~4–5 choices at a time** (Cowan E5, Hick K3) | **Five tabs**, top-right pills like Huw's tabs: **Now · Today · Life · Activity · Controls**. Memory lives inside Life (the facts behind each branch, plus "Everything Jarvis knows" at the root). Under the hood lives inside Controls. All seven designed views stay; only five are top level. |
| **Familiar patterns** (Jakob K4) | A **command bar** (Ctrl+K or "/"), like Spotlight, Raycast and Linear: type to go anywhere (a view, a branch, a fact, a setting) or just type to Jarvis. Number keys 1–5 switch tabs. Esc always goes back. |
| **Everything is two steps away** | Any item: tab → item, or command bar → item, or one spoken command ("open GE 122"). Nothing deeper than branch → detail. |
| **One obvious next action** (Hick K3, Von Restorff K5) | One accent button per panel at most (the `--accent` token: cyan on Night). Everything else is quiet. |
| **Always know where you are** | Tabs show the current view; Life shows breadcrumbs (`Life › School › Fall 2026 › GE 122`); the orb's corner position means "Jarvis is showing you something". |
| **Back is always safe** | Esc / Back / "go back" returns to the previous view and scroll position; closing a window never loses anything: it docks into its Rail slot (contracts v2). |
| **Calm periphery** (E3, K1) | After 2 min idle the hub returns to the ambient screen. Any key, click or "hey Jarvis" wakes it. |
| **Badges that mean something** | Only two: **Waiting for your yes** (count on Activity) and **Due soon** (on Life nodes). No red dots for anything else. From v0.3.0 the **Rail** (bottom band, every tab) carries everything set aside, with a static cyan "since you looked" notch, never a red count. |
| **Voice = keyboard = mouse** | Every voice command has a visible equivalent; nothing is voice-only (HUB_TRUST §2a). |

**Aesthetic references** (what we borrow, not copy):
- **Pen Reader** (palette, plants, sheets, dock).
- **Huw's HUD** (orb, ambient clock, windows popping up, page dots).
- **Things 3** (calm lists, generous spacing, one accent).
- **Linear** (speed, keyboard-first, command bar).
- **Raycast / Spotlight** (the command bar).
- **Apple Weather and Home widgets** (glanceable cards with one big number).
- **Headspace** (warmth, friendly empty states).
- **Readwise Reader** (comfortable reading sheets).

---

## 3. Design rules as build checks (Night HUD)

Every work package (WP) is reviewed against this list (the overseer's checklist). Rewritten on 2026-11-14 for the Night HUD: the reasons are in `docs/design/JARVIS_DESIGN_HUD_V2.md` (§ numbers below) and JARVIS_PSYCHOLOGY.md. The old rules about terracotta, warm-only colours, the rounded 12/18/24 scale, cream sheets and "the idle orb breathing is the only loop" no longer apply.

1. **≤ 4 items per panel, ≤ 6 windows on screen** (E5, K2), and **at most 4 amber or red marks outside the Rail** at once; the rest only raise their Rail slot's count (§5).
2. **One accent action per panel, and one job per colour** (§2): cyan = Jarvis (what he's working on, what he means right now, links) · cyan-hi = done · amber (`warn`) = needs you (soon, your yes) · red (`crit`) = critical or overdue · green (`ok`) = system health only, in Under the hood. In progress is the ice `line` colour, so cyan always means Jarvis. The **kind** of thing (class, homework, message…) is told by icon and position, never by colour.
3. **Colours only from tokens**, and the token names stay the same (`--canvas`, `--card`, `--text`, `--muted`, `--accent`…); Night sets their values. **Light is added, never painted**: thin bright strokes, each with a static blurred copy behind it; dark, nearly opaque fills; never pure black. Brightness order: orb → active frames → text → grid. Meaningful lines ≥ 1.5 px. No glow on text under 18 px.
4. **Windows** (§3): square corners, a 1 px ice-cyan frame with a soft static glow, near-opaque fill. A **kicker** top-left (12 px mono caps, ≤ 4 words, status word last); metadata may hang outside the frame but is never the only copy of a fact. Every window **leads with one big thing**: a number, a picture, a video frame or a two-line title.
5. **Type and reading** (§8): kickers and metadata in mono, ≥ 12 px, caps; titles in the condensed face, caps, two lines at most; hero numbers about 3× the title, tabular. Reading text ≥ 15 px (15/23), sentence case, 60–70 characters per line, no italics or capitals for emphasis. Long reading (PDFs, notes) opens on the **light sheet inside a HUD frame**, using the darker sheet inks. No fake micro-text: every string on screen is real data.
6. **Motion marks a state change only** (§7). Window assembly ≤ 300 ms, mechanical (hard stops, no springs), and content is usable from 0 ms: nothing waits for an animation. Named exceptions: the wake beat (1.2 s, rare) and the orb's dock slide (700 ms). Critical brackets move ±2 px at about 1 Hz for at most 5 s, then hold still. **On the ambient screen: ≤ 8 running animations, all on HTML elements, with keyframes that use only `transform` and `opacity`.** Continuous loops ≤ 30 fps and paused when hidden; one JS loop at most (the orb's voice level). No video, canvas or WebGL on the HUD (the PDF reader's canvas is the one exception, never on ambient or the strip). Under reduced motion every transition is an instant swap. Laptop A's strip never animates (C37).
7. **Feedback within 0.1 s** for every click or key (Doherty).
8. **Sources on every claim** (chip), confidence in words (Sure, Likely, Guess), guesses dotted-underlined (HUB_TRUST §1, §3). Numbers for facts, words for confidence.
9. **Every action has a receipt and an undo** with its window shown (§1.5).
10. **Progress before problems**: what got done shows first (I1, K6, S2).
11. **No hooks**: no streaks, points, confetti, guilt or red badge counts (A7, C40). A "since you looked" mark is a static cyan notch.
12. **Copy**: short, plain, errors say what to do next, never blame (A8). No system-speak ("Task resumed", "Processing your request"), no exclamation marks. Reading text is sentence case; only kickers and titles are caps.
13. **Accessibility**: contrast ≥ 4.5:1 text and ≥ 3:1 UI, on Night and on the light sheet; full keyboard; screen-reader text for the day dial, the Rail and marks (at most one polite announcement a minute); the **focus ring is a 2 px `--text` outline with a 3 px offset and a dark gap, never cyan**.
14. **Glance codes** (§5): every state is a **shape + a colour + one word**, never colour alone: done (filled disc with a dark check, ≥ 16 px) · in progress (open ring with an arc) · Jarvis (reticle; one at most) · soon (diamond in corner brackets) · your yes (hollow square in corner brackets) · critical (triangle in corner brackets) · parked (dashed ring). **One meaning per mark:** corner brackets mean only "wants you".
15. **Nothing gets away** (§6, contracts v2): closing, expiring, evicting, stepping aside, the 60 s lifetime and CLEAR VIEW **dock** a thing into its Rail slot; only done or archive removes it. Moves are a real reorder (`window.order`), never close + push. Changes show as the change ("Due moved Wed 8 pm → Thu 11:59 pm"). Marks clear only when he has seen the thing (opened it, keyboard focus, a hover of ≥ 800 ms, or "mark all seen"), never by being shown.
16. **Pictures with big labels** (§5): a thing's `thumb` always comes with its label and alt text; thumbnails are never in git; rooms show as a big room code.
17. **Node budgets** (§4): decoration ≤ 250 nodes; the whole page ≤ 1,200 (a test enforces it).

---

## 4. Tech choices (reusing Pen Reader)

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.12 (uv) + plain HTML/CSS/JS | Same as Pen Reader and `jarvis-core`; one maintainer |
| UI structure | **ES modules + Web Components** (one custom element per folder), **no build step** | Each component is an isolated folder, ideal for parallel agents; runs in WebView2 and any browser |
| Libraries | Vendored **d3-hierarchy + d3-zoom** (Life Map) only | Small (~30 KB); no framework lock-in |
| Hub server | **FastAPI** + SSE (`/api/events`), static UI | Same server family as `jarvis-core` |
| Demo backend | Python module playing fixtures + a scripted timeline over SSE | The whole UI is usable and testable now |
| Desktop shell | **pywebview** (WebView2) + Edge app-window fallback, like Pen Reader's `app.py` | Proven on his machines |
| Installer | **PyInstaller + Inno Setup** → `JarvisHub-Setup.exe`, per-user install, Start menu + optional desktop shortcut | Same as Pen Reader |
| Releases | GitHub Actions on `windows-latest`: tests → build → installer → GitHub Release `vX.Y.Z` when `VERSION` changes | Same as Pen Reader's `build.yml` |
| Tests | pytest (server, contracts, tokens) + Playwright (every `?scene=`, both themes, sizes) + contrast checker | Pen Reader's quality bar |

---

## 5. Contracts first (what lets agents work in parallel)

Nothing in the UI talks to anything except through these. **Frozen at gate G0**; changing one needs the overseer's approval and a contract version bump. **They are at v2 since package N0** (hub v0.3.0): docked windows, `window.dock` / `window.order`, the Rail, marks, work threads, `thumb`, the day dial, `moment`, the focus cue. `docs/contracts.md` lists every change; the lists below are the v1 core.
- `contracts/*.schema.json` (JSON Schema) with example fixtures in `contracts/examples/`:
  - `now_card`, `branch` (tree node), `branch_card`, `fact`, `action` (receipt + undo window), `approval` (proposal + consequences + expiry), `window` (widget push: type, ref, data, pinned), `orb_state`, `job` (working-on), `caption`, `toast`, `settings`, `metrics`.
- **Event envelope over SSE:** `{ "v": 1, "type": "<name>", "ts": "<iso>", "data": {…} }`. Types: `orb.state`, `nowcard.updated`, `branch.updated`, `window.push`, `window.close`, `caption.show`, `approval.pending`, `approval.resolved`, `activity.added`, `job.progress`, `toast`, `presence.changed`.
- **UI actions** (POST `/api/act`): `{ "action": "approve|decline|undo|pin|close|move|forget|confirm|edit|…", "target": "<id>", "args": {…} }`. Demo mode answers them; live mode forwards them to `jarvis-core` (which applies the approval rules in RUNTIME §9).
- **Static scenes:** `?scene=<name>&theme=day|evening&size=full|laptop|strip|phone|ambient` loads a fixture set, so every state can be opened and screenshotted (Pen Reader's mock-bridge pattern).

---

## 6. Repository layout (`Thelaw247/jarvis`, private)

```
jarvis/
  VERSION  CHANGELOG.md  README.md  pyproject.toml  app.py (desktop launcher)
  jarvis_hub/            server.py, events.py, demo/ (fixtures.py, scenario.py), settings.py
  contracts/             *.schema.json, examples/*.json
  ui/
    index.html  tokens.css  base.css  fonts/  icons/  vendor/ (d3)
    core/                store.js, events.js, router.js, bridge.js, scenes.js, windows.js, keys.js, theme.js
    components/<name>/   <name>.js, <name>.css, README.md   (one folder per component)
    components/index.js  (imports; only the overseer edits it)
    views/<name>/        <name>.js, <name>.css
  tests/                 test_*.py, e2e/
  tools/                 make_plants.py, screenshots.py, contrast.py, hexlint.py
  installer/             JarvisHub.iss
  changes/               one fragment per work package (compiled into CHANGELOG at release)
  docs/                  DESIGN.md, PRODUCT.md, hub-build-plan.md (this file), contracts.md, work/STATUS.md
  .github/workflows/     ci.yml (every push), release.yml (VERSION change → installer + GitHub Release)
  .claude/skills/        jarvis-release/ (commits and releases), jarvis-build/ (how to build a WP)
```
**Ownership rule:** every WP owns specific paths. Two WPs never edit the same file. Shared files (`ui/components/index.js`, `ui/index.html`, `CHANGELOG.md`, `VERSION`, `docs/work/STATUS.md`) are edited **only by the overseer** at merge time.

---

## 7. Phases and work packages

Sizes: **S** ≈ ≤ 150 lines, **M** ≈ 150–400 lines. Every WP must ship: its code, its `?scene=` states, tests, screenshots in both themes, a `changes/<WP>.md` fragment, and a short README in its folder.

### H0 — Foundation (contracts and plumbing; mostly parallel after H0.1)
| WP | What | Owns | Needs | Size |
|---|---|---|---|---|
| H0.1 | Repo skeleton: layout above, pyproject/uv, ruff, pytest, README, VERSION 0.0.1, CHANGELOG, changes/, docs/work/STATUS.md, skills | root files | — | S (done at setup) |
| H0.2 | **Design tokens**: `ui/tokens.css` (Daylight + Evening from Pen Reader + HUD touches), `ui/base.css` (type, focus ring, reduced motion), fonts copied from Pen Reader, `docs/DESIGN.md`, hex-lint test (hex only in tokens.css) | ui/tokens.css, ui/base.css, ui/fonts/, docs/DESIGN.md, tools/hexlint.py | H0.1 | M |
| H0.3 | **Contracts v1**: all schemas + example fixtures + validation tests + docs/contracts.md | contracts/, tests/test_contracts.py, docs/contracts.md | H0.1 | M |
| H0.4 | **Hub server + demo backend**: FastAPI static + `/api/state` + `/api/events` (SSE) + `/api/act`; demo fixtures and the scripted day | jarvis_hub/, tests/test_server.py | H0.3 | M |
| H0.5 | **UI shell**: index.html regions (stage, tabs, orb dock, toasts), store, SSE client, router (tabs, back stack, Esc), bridge (live/demo), scenes loader, component registry | ui/index.html, ui/core/{store,events,router,bridge,scenes}.js | H0.2, H0.3 | M |
| H0.6 | **Desktop launcher + packaging**: app.py (pywebview, Edge fallback, logging, icon, `--demo`, `--hub URL`, `--ambient`, `--strip`), app icon, installer/JarvisHub.iss, build.ps1, ci.yml, release.yml | app.py, installer/, .github/, ui/icons/app.* | H0.4 | M |
| H0.7 | **Gate harness**: Playwright e2e smoke, tools/screenshots.py (scene × theme × size), tools/contrast.py (all token pairs), CI wiring | tests/e2e/, tools/screenshots.py, tools/contrast.py | H0.5 | M |
**Gate G0:** contracts frozen v1 · the shell opens in demo mode and shows events arriving · CI green · `v0.1.0` installer builds and installs.

### H1 — Components (fully parallel; each owns `ui/components/<name>/`)
| WP | Component | Notes | Size |
|---|---|---|---|
| C01 | **Orb** | SVG; states idle, listening, thinking (gyroscope), speaking, waiting-for-yes countdown, muted, offline; centre/corner/strip sizes; reduced-motion versions (HUB_TRUST §5.4) | M |
| C02 | **Ambient clock** | Big thin Lexend clock + date + one "next up" line | S |
| C03 | **Status line + mic dot** | "Listening · Balanced", quiet, game mode; always shows mic state | S |
| C04 | **Tabs + page dots** | Five pill tabs, keyboard 1–5, Activity badge; page dots on ambient | S |
| C05 | **Command bar** | Ctrl+K, fuzzy search over views/branches/facts/settings, "ask Jarvis" fallback, keyboard only usable | M |
| C06 | **Window frame** | The HUD panel: title, corner brackets when active, pin/close, sizes (1×1…3×2), enter/leave motion | S |
| C07 | **Source chip + confidence label** | Icon + word; unexpected-source marker; Sure/Likely/Guess | S |
| C08 | **Fact card** | Statement, source, confidence, history, Confirm/Edit/Pin/Move/Forget; dotted underline for guesses | M |
| C09 | **Big-number / countdown widget** | "2d 04h" due countdowns, stats | S |
| C10 | **Mini chart** | Bars/line in token colours, accessible table fallback (dataviz rules) | M |
| C11 | **Action-log row** | What · why · sources · result · Undo with window | S |
| C12 | **Approval card** | Consequences first, read-back text, Yes/No/Change, answer-window countdown, expiry | M |
| C13 | **Now card** | Next up, one flag, working-on, ready to offer, gaps | M |
| C14 | **Branch card** | Status, next, due, open loops, key facts, people, files, recent, gaps, story | M |
| C15 | **Notice, toast, error, empty states** | Friendly empties (Headspace-warm), errors say what to do | S |
| C16 | **Voice caption** | One line + source chip near the orb, fades in/out | S |
| C17 | **Plants** | Port Pen Reader's `make_plants.py`: day plant (grows with done items), leaf nodes and stems for the Life Map | M |
| C18 | **Day timeline** | Classes, blocks, his events, source chips, "why this time" | M |
| C19 | **File preview tile** | PDF page / slide thumbnail, "open it" | S |
| C20 | **Working-on chip** | Background jobs with real progress, no fake delays | S |
| W01 | **Window manager** (`ui/core/windows.js`) | Placement on a 12-column grid, max 6, lifetime 60 s unless pinned, voice/keyboard commands, save/restore layout | M |
**Gate G1:** every component renders all its states in both themes; contrast passes; each has a demo page (`?scene=component:<name>`).

### H2 — Views (parallel; each owns `ui/views/<name>/`)
| WP | View | Built from | Size |
|---|---|---|---|
| V01 | **Now**: ambient (orb, clock, day plant, page dots) ↔ active (orb to corner, windows) | C01–C06, C09, C13, C16, C17, C20, W01 | M |
| V02 | **Today**: timeline, proposed changes (Apply · Tweak · Skip), missed/moved lane | C07, C11, C18 | M |
| V03a | **Life Map engine**: radial tree layout, semantic zoom fly-in/out, ≤ 7 children + "+n more", search jump | d3, C17 | M |
| V03b | **Life Map nodes**: leaf nodes, size by activity, due ring, needs-your-yes dot, proposed (dotted), archived (dim), tier-2 lock | C17 | M |
| V03c | **Life outline view** (keyboard, screen reader, phone) | contracts | M |
| V03d | **Branch page**: panels + children strip + controls | C08, C09, C14 | M |
| V03e | **Unsorted tray** + "Everything Jarvis knows" (Memory) with filters, guesses to review, conflicts, recently learned, pause, off the record | C07, C08 | M |
| V04 | **Activity**: Waiting for you (top), timeline with undo, Held back, filters | C11, C12 | M |
| V05 | **Controls**: interruption dial, quiet hours, focus/game mode, approvals + standing permissions, look, data sources, privacy tiers | C15 | M |
| V06 | **Under the hood**: latency per stage, connectors, spend, credits, eval trend, backups | C09, C10 | M |
| V07 | **Strip** (Laptop A): static orb, status, next up; zero animation | C01, C03 | S |
| V08 | **Phone layout** pass: Now, Waiting for you, Life outline, quick controls | views | S |
**Gate G2:** every view passes the full definition of done (BUILD_AND_CONSISTENCY §4) in both themes and all sizes.

### H3 — Behaviour (parallel; each owns one core module)
| WP | What | Owns | Size |
|---|---|---|---|
| B01 | Keyboard and focus system, shortcuts sheet ("?") | ui/core/keys.js | S |
| B02 | Theme and motion: Daylight/Evening/follow Windows/after sunset, reduced motion, plants on/off | ui/core/theme.js | S |
| B03 | Idle ↔ ambient transitions, presence events, wake on key/voice | ui/core/presence.js | S |
| B04 | Demo tour: plays the scripted day with a small "Demo" chip; restart from Controls | jarvis_hub/demo/scenario.py (extends H0.4) | M |
| B05 | Screen-reader live regions for captions, toasts and approvals | ui/core/a11y.js | S |

### H4 — Integration, review and first release
| WP | What |
|---|---|
| I01 | Wire every view into tabs, command-bar index, back stack and deep links (overseer) |
| I02 | **Independent reviews**, by agents that didn't build the parts: design critique, accessibility review, hands-on walkthrough of the demo day, visual-verdict against Pen Reader screenshots (palette and feel); Huw's layout is checked against the written description in HUB_TRUST §5.1 (no copies of his video frames are kept in the repo) |
| I03 | Performance: first paint < 300 ms, branch page < 100 ms, SSE event to pixel ≤ 100 ms, strip ≤ ~1% CPU on Laptop A, ambient screen ≤ 30 fps and paused when hidden |
| I04 | Release **v0.2.0** (first full hub) with the jarvis-release skill; installer tested on Laptop A and B |
**Gate G4:** all reviews' must-fix items done; release published; he can install it and click through the demo day.

### N — Night HUD (hub v0.3.0)
The redesign in `docs/design/JARVIS_DESIGN_HUD_V2.md` (§13 is the source for this table). No file is owned by two packages. Waves of ≤ 6 parallel agents; the Fable 5.2 overseer merges, does cross-package fixes, and releases with `jarvis-release`; fresh reviewers check the result. Every package registers its own scenes.

| ID | What | Owns | Needs |
|---|---|---|---|
| N0 | Contracts v2 and wiring (overseer, first): windows `docked`/`slot`, `window.dock`/`window.order`, Rail, marks, threads, `thumb`, day dial (ISO times), `moment`; reducers, server hooks, route stubs, Rail/dock regions; rewrite the hub plan's design checklist for Night HUD | `contracts/`, `docs/contracts.md`, `tests/test_contracts.py`, `ui/core/store.js`, `jarvis_hub/events.py`, `jarvis_hub/server.py`, `ui/index.html`, `ui/core/shell.css`, `docs/hub-build-plan.md` | — |
| N1 | Night tokens, sheet inks, focus ring, base kicker/frame/pill classes, theme choices (Night / Daylight / Sunset), contrast tool with alpha, condensed font | `ui/tokens.css`, `ui/base.css`, `ui/core/theme.js`, `ui/fonts/`, `tools/contrast.py`, `tests/test_tokens.py`, `tests/test_contrast.py`, `docs/DESIGN.md` | — |
| N2 | The Core orb, wake/dock, earcons, performance test | `ui/components/orb/`, `ui/sounds/`, `tests/e2e/test_performance.py` | N1 |
| N4 | The Rail, docking instead of deleting, marks, voice-driven focus on screen | `ui/components/rail/`, `ui/core/windows.js`, `ui/core/windows-core.js`, `ui/core/presence.js`, `ui/views/now/now.{js,css}`, `jarvis_hub/rail.py`, `tests/e2e/test_windows.py`, `tests/e2e/test_now_canvas.py`, `tests/test_rail.py` | N0, N1 |
| N5a | Glance + thumb components, domain icons, thumbnail cache, Night pass on the Now-side components, mechanical assembly | `ui/components/{glance,thumb,window,big-number,file-tile,now-card,working-on,caption,branch-card}/`, `ui/core/dom.js` (icons only), `jarvis_hub/thumbs.py`, `tools/make_demo_thumbs.py` | N0, N1 |
| N5b | Night pass on the other tabs | `ui/components/{timeline,action-row,approval-card,fact-card,source-chip,notice,mini-chart,tabs,status-line,command-bar,clock,plant}/`, `ui/views/{today,life,activity,memory,branch,controls,hood}/`, `ui/views/views.css` | N0, N1 |
| N6 | Work threads, question index, resume card, PDF reader | `jarvis_hub/threads.py`, `jarvis_hub/pdfindex.py`, `ui/vendor/pdfjs/`, `ui/views/reader/`, `ui/components/resume-card/`, `tests/test_threads.py`, `tests/e2e/test_reader.py` | N0, N1 |
| N7 | Demo re-based to real time, the demo story, character lines (pools, moments, declines) | `jarvis_hub/demo/`, `contracts/examples/state.json` (after N0), `app.py` (demo flag), `tests/test_demo.py` | N0, N5a |
| N3 | Day dial and the ambient screen | `ui/components/day-dial/`, `ui/views/now/ambient.js` | N2, N4 |
| N8 | Phone and strip: Rail row, worst state, game-mode recap | `ui/views/phone/`, `ui/views/strip/` | N4 |

**What N0 hands the others** (details in `docs/contracts.md`): the store keys `rail`, `marks`, `threads`, `focus`; the events `window.dock`, `window.order`, `rail.updated`, `marks.updated`, `thread.updated`, `ui.focus`; the actions `dock`, `recall`, `order`, `seen`, `archive`, `resume_save`, `resume_accept`; the shell regions `#rail` (48 px, centre of the bottom band; `<jv-rail>` upgrades it), `#caption` above it, `#dock` (orb, right) and `#ambient`; and three server hooks that need no edit to `server.py` or `events.py`: `jarvis_hub/rail.py refresh(state, now)` (N4), `jarvis_hub/thumbs.py thumb_path(key)` (N5a), `jarvis_hub/threads.py file_path(file_id)` (N6).

**Gate N:** three fresh reviews (design against the films and Huw, accessibility, hands-on walkthrough of the 14 scenarios) → fixes → release **v0.3.0**. After wave 1, screenshots of the new orb and Now go to De Wet before wave 2.

### H5 — Go live (later, inside P1 when `jarvis-core` exists)
Point the app at `https://<hub>.ts.net` (Tailscale); `jarvis-core` serves the same contracts; demo mode stays for tests and screenshots. No UI rewrite.

---

## 8. Waves (how the parallel work is scheduled)

| Wave | Runs at the same time | Max workers |
|---|---|---|
| 0 | H0.2, H0.3 → then H0.4, H0.5 → then H0.6, H0.7 | 3 |
| 1 | C01–C20, W01 (in batches of ≤ 6), B01, B02 | 6 |
| 2 | V01–V08, B03–B05 | 6 |
| 3 | I01–I04 (reviews by fresh agents) | 4 |
| **N-0** (v0.3.0) | N0 + N1 | 2 |
| **N-1** | N2, N4, N5a, N5b, N6, N7 | 6 |
| **N-2** | N3, N8 → three fresh reviews → fixes → release v0.3.0 | 2 (+ 3 reviewers) |
Batches are ordered by what the views need first (orb, window frame, window manager, now card, tabs).

---

## 9. The overseer (Claude Fable 5.2) and the workers

**Overseer (one Fable 5.2 agent):**
- Owns the plan, `docs/work/STATUS.md`, the shared files and `main`.
- For each wave: writes a short brief per WP (goal, owned paths, contracts and tokens to use, scenes to add, acceptance checks), starts workers, and keeps ≤ 6 running.
- **Reviews every result before merging**: owned paths only; tokens only (hex-lint); contracts respected; the §3 design checks; accessibility; tests and screenshots present. Sends it back with specific fixes, or merges.
- Merges each WP branch (`wp/<id>`) into `main`, adds the component import, runs the full test suite, pushes. Main is always green.
- Runs each gate; at G0 and G4 releases with the **jarvis-release** skill.
- **Escalates to De Wet only for**: a design choice the docs don't settle, a contract change that affects scope, anything needing his accounts or devices, or a gate that fails twice.

**Workers (one per WP):**
- Work in their own git worktree on branch `wp/<id>`, touch only their owned paths, follow `.claude/skills/jarvis-build` and `jarvis-release` (commit format).
- Done = code + scenes + tests passing + screenshots (both themes) + `changes/<id>.md` + folder README, reported back with a 5-line summary.

**Reviewers (fresh agents at G2 and I02):** never review their own work (BUILD_AND_CONSISTENCY: "the work isn't grading itself").

---

## 10. Definition of done for any WP (short form)
1. Only owned paths changed; no hex outside `tokens.css`.
2. All states have `?scene=` entries; screenshots in both themes (Night and Daylight from v0.3.0) at its sizes, looked at.
3. The design checks (§3) and accessibility (contrast, keyboard, labels, reduced motion) pass.
4. Tests pass (`pytest`, e2e smoke); CI green on the branch.
5. Latency tier stated; motion ≤ 300 ms and only for state (named exceptions: the wake beat and the dock slide); on ambient ≤ 8 running animations, HTML elements, `transform`/`opacity` keyframes only.
6. `changes/<WP>.md` fragment written in plain words; commit messages follow jarvis-release.

---

## 11. Releases
- **Versioning:** `0.MINOR.PATCH` until the hub goes live; MINOR = a phase or new view, PATCH = fixes. Contracts carry their own `v` number.
- **How a release happens:** the jarvis-release skill compiles `changes/` fragments into `CHANGELOG.md`, bumps `VERSION`, commits `release: vX.Y.Z`, pushes; `release.yml` on `windows-latest` runs the tests, builds `JarvisHub-Setup.exe` and publishes the GitHub Release. The skill then checks the release and its installer exist.
- **Planned:** v0.1.0 at G0 (shell + demo), v0.2.0 at G4 (full hub), **v0.3.0 at gate N (the Night HUD)**; going live (H5) takes the minor after that.

## 12. Latency (what the hub must hit)
| Path | Target |
|---|---|
| Click/key feedback | ≤ 100 ms |
| SSE event → pixel (widget push, caption, orb state) | ≤ 100 ms |
| App window open (warm) | ≤ 1.5 s; first paint of cached UI < 300 ms |
| Life Map first paint / branch page | < 300 ms / < 100 ms |
| Laptop A strip | ≤ ~1% CPU, no animation (C37) |
| Ambient screen | ≤ 30 fps, paused when hidden; ≤ 8 running animations, HTML elements only, `transform`/`opacity` keyframes only |
| Practice set reopens at the saved question (v0.3.0) | ≤ 400 ms warm; < 50 ms if already open (measured on both laptops before quoting) |
| A spoken offer whose line was pre-rendered (v0.3.0) | < 30 ms to start playing |
