# Jarvis — Hub and Trust Design

Last updated: 2026-11-14
Status: design, built across P1–P3. Part of the design set in Jarvis/. Revised 2026-11-14: the hub uses **Huw Prosser's HUD layout drawn in Pen Reader's plant-and-earth-tone palette** (§5, "Earth HUD"; decided 2026-11-14 afternoon, replacing the morning's dark Night HUD), gains the **Life Map** view (JARVIS_DESIGN_LIFE_TREE.md) and **widget push** (§2a). Revised again 2026-11-14 evening with De Wet's OK: body text is 15/23 (was 15/22), and the Sunset theme follows Saskatoon's real sunset and sunrise (§2 Look, §5.2, §5.3; shipped in hub v0.2.2). The step-by-step build is in JARVIS_HUB_BUILD_PLAN.md.

**The idea:** nothing Jarvis knows or does is a black box. The hub is where every memory, decision and action can be seen, checked, edited and undone. It is laid out like Huw's HUD (an orb and big clock when idle, windows that appear when Jarvis talks) but painted like Pen Reader (cream paper, terracotta, plant green, soft rounded cards), and it behaves calmly: little on screen, everything one tap away.

---

## 1. Trust principles (from research)

1. **Memory he can see, edit and delete.** Branches he can open; edit and forget on every item; **pause memory** and **off-the-record** modes (as Claude's memory does).
2. **Explain partially, locally, with sources.** Not everything at once; the source is part of the explanation; deeper explanation only for high-stakes moments (Google PAIR).
3. **Explanations must make checking cheaper, not make Jarvis more persuasive.** Research found explanations raise acceptance of AI advice *whether or not it's correct*, and only reduce over-reliance when they lower the cost of verifying. So Jarvis's "why" **shows the actual source** (the syllabus line, the Canvas date, "you said this on Nov 13"), never a confident paragraph.
4. **Confidence in words, each with an action.** No percentages.
   - **Sure**: acts.
   - **Likely**: acts if reversible and mentions it.
   - **Guess**: asks.
5. **Every action gets a receipt and an undo.** Preview before acting (feedforward), receipt after (feedback). Undo states its window ("Undo · 24 h"); after the window the row stays but the button goes.
6. **Every explanation comes with a control.** Like "Why am I seeing this?": each "Why?" panel ends with *less of this · don't remind me about X · that's wrong*.
7. **Global controls and change notices.** An interruption dial, quiet hours, game mode, and a small "Jarvis learned 3 things today" feed.
8. **Flag unexpected data use.** If Jarvis uses a source he might not expect (Gmail for a schedule answer), the source chip says so.
9. **Listening is always visible.** The orb shows mic state on every view, one-tap mute, no raw audio kept (C23).
10. **Calm by default, even in a HUD.** Transparency is one tap away, never clutter: ≤ ~4 items per panel, ≤ ~6 panels on screen, widgets fade when unused. Motion only shows state (listening, thinking, speaking, something changed), never decoration that loops for attention.

---

## 2. Information architecture: seven views

No top level shows more than ~4 things. Same views in both themes (§5).

**1. Now** (home; the ambient screen)
- **Idle (ambient), like Huw's monitor:** the Jarvis **orb** in the centre, a large thin clock under it, one line under that (next up, or nothing), a faint dot grid, page dots at the bottom for the other views, a tiny status line in a corner ("Listening · Balanced"). This is what Laptop B's screen and an idle hub window show all day.
- **Active:** when he speaks, the orb reacts (§5.4); when Jarvis has something to show, the orb slides to the bottom-right corner and widgets fill the canvas (§2a).
- **Next up**: one item with time and room. **One flag**, only if there is one ("Lab report due Thu · 40% done"). **Working on…** chip for background jobs ("Syncing Canvas…").
- Controls: mute, focus/quiet, "Why?" on the flag.

**2. Today / Plan**
- Day timeline: classes, Jarvis-booked blocks, his own events, each with a source chip (PAWS · Calendar · You · Jarvis) and a "why this time" note ("after CHEM lab; your lab reports run ~1.5× the estimate").
- **Proposed changes** appear as a preview: *Apply · Tweak · Skip*. Tweaking is easy on purpose.
- "Missed / moved" lane that rebooks without guilt.

**3. Life Map** (new; replaces "Open loops & projects")
- His whole life as a navigable tree: the **constellation** (big screens) or **outline** (phone, keyboard, screen reader), plus a **branch page** for any branch (JARVIS_DESIGN_LIFE_TREE.md §11).
- Projects are branches here (Projects › Jarvis, Pen Reader, Praelecta…); every open loop shows on its branch with its planned slot, and an **Open loops** filter lists them all.
- **Unsorted** tray: items Jarvis couldn't place, each with a guess; one tap or "yes" files them.

**4. Memory: "What Jarvis knows"**
- The fact layer behind the Life Map, for checking and correcting. Filter by branch, source or confidence.
- **Fact cards**: the statement, a source chip ("You · Nov 13", "Syllabus GE 122 p.2", "Canvas", "Guess"), a confidence word only when not Sure, last confirmed, and history ("was Birch House → now Maple").
- Actions on every card: **Confirm · Edit · Pin as rule · Move · Forget**. Forget first previews what derived facts will also go.
- **Guesses to review** (a 10-second habit that keeps guesses apart from facts, C17). **Conflicts**: "Canvas says Fri; you said Thu → kept yours." *Keep mine · Use Canvas.*
- **Recently learned** feed, search, **Pause memory**, **Off the record**.

**5. Activity: receipts**
- **Waiting for you** at the top: every write that's waiting for a yes (C12), the same ones Jarvis will ask about out loud at the next breakpoint. Tap to approve if voice isn't handy.
- Timeline, newest first: what · why (trigger) · sources · result · **Undo** with its window. Includes Life Tree changes (filed, moved, renamed, created).
- **Held back**: remarks Jarvis chose *not* to interrupt with, and why ("held: you were focused").
- Filters: calendar, files, messages, memory, tree, skills.

**6. Controls**
- Interruption dial (Quiet / Balanced / Chatty), quiet hours, focus mode, game mode (auto + manual).
- **Approvals (revised 2026-11-14):** reading is always automatic; every write waits for his yes, asked out loud with a read-back (JARVIS_DESIGN_RUNTIME.md §9). Standing permissions listed here, each revocable by voice or tap. Submissions and payments = never.
- **Look:** theme (Daylight / Evening / follow Windows / Sunset: Evening from Saskatoon's real sunset to sunrise), motion (full / reduced / off), plants on/off, ambient screen on/off per device.
- Data sources: each connector with last sync and on/off. Privacy tiers. Voice settings. Pause memory.

**7. Under the hood** (off the main navigation)
- p50/p95 latency per stage, connector status, ElevenLabs credits left, Claude spend this month (alert at 70% of the $100 credit), last backup and restore test.
- "Know De Wet" eval score trend, placement accuracy, and the weekly self-report ("learned / got wrong").

**Compact modes**
- **Strip** on Laptop A: a small static orb (state by colour + word), status line, next up. Always on top, optional. **Hidden in game mode.** No animation loops (C37).
- **Phone**: Now + Waiting for you (approvals) + Life (outline) + quick controls.
- **Ambient screen**: Laptop B's display (and any idle hub window) shows the Now idle state. Tier-2 branches and private details never appear on it (LIFE_TREE §10).

**Voice ↔ hub link:** when Jarvis speaks, a one-line caption with its source chip fades in near the orb (~150 ms) and out again, so any claim can be checked at a glance.

---

## 2a. Widget push (the HUD's core move, from Huw)

Huw's assistants put things on screen while they talk: stats, charts, photos, camera feeds, text cards, arranged as a collage. Jarvis does the same, without adding latency:
- **How:** the T1 talker writes short cue tags in its stream (`[[show:branch:ge-122]]`, `[[show:file:pps7.pdf]]`, `[[show:due:lab-4]]`). The voice pipeline strips them before TTS and sends them over SSE; the hub renders the widget from data it already has. T0 commands push widgets directly ("open GE 122", "show my week"). **No extra model call; ~10–100 ms event to pixel.**
- **Widget types (v1):** branch card · due countdown (big number) · next-up · day timeline · file preview (PDF page, slide) · fact card with source · approval card (consequences first) · timer · small chart (dataviz rules) · Unsorted item.
- **Layout:** a 12-column grid on the canvas; new widgets fill from the top-left of the free area; at most 6; the oldest unpinned one leaves when a 7th arrives.
- **Lifetime:** fades 60 s after last use unless pinned ("keep that up"); "clear the screen" removes all. Widgets are not pushed to the ambient screen when others may be present (presence signals), and never for tier-2 items.
- **Every widget is a real control too:** tap opens its branch page or source; nothing is voice-only.

---

## 3. Showing provenance, confidence and authority without clutter

- **Source chips**: icon + word, never colour alone (*You · Nov 13*, *Canvas*, *Syllabus p.3*, *Calendar*, *Gmail*). Unexpected sources get a subtle marker.
- **Guesses look different**: Pen Reader's dotted underline for repaired words, reused (unchanged from Pen Reader). Tap: "Guess from: you skipped 3 of 4 8 am blocks. Confirm?" Facts he stated have no underline.
- **Confidence**: Sure (hidden by default) · Likely · Guess. When data is missing Jarvis says so: "Nothing for Thursday afternoon. Free?"
- **Authority**: conflicts always shown resolved his way on intent, with one line of what the other source says and a single toggle. Decisions he made carry a small "Your call · Nov 13" chip.
- **Progressive disclosure**: chip → tap → evidence (source snippet or link, timestamp, rule used) → controls. Never more than one level deep.
- **Approvals show consequences first**: "Sends to prof.smith@… · attachment lab3.pdf · can't be unsent." While Jarvis waits for a spoken answer, the orb shows the ~10 s answer window as a ring that empties (§5.4).

---

## 4. Tech stack

| Part | Choice | Why | Latency / footprint |
|---|---|---|---|
| Hub server | **Python + FastAPI**, same process family as the core on Laptop B | One language, one codebase (C34) | In-process access to the now card, branch cards and memory; reads ≤ 50 ms |
| UI | **HTML/CSS/JS on one tokens file with two themes** (§5); light framework optional; **d3-hierarchy + d3-zoom** for the Life Map (~30 KB); SVG for the orb | Proven toolchain from Pen Reader; SVG is crisp and accessible | Service worker caches assets → opens instantly; map first paint < 300 ms |
| Fonts | Lexend + Atkinson Hyperlegible Next (from Pen Reader) + **JetBrains Mono** only for tiny telemetry (status line, Under the hood numbers), all self-hosted (open licences) | Legibility kept; a hint of HUD without the cold look | Preloaded; no network fonts |
| Transport | **`tailscale serve`** → HTTPS at the hub's tailnet name | Automatic TLS; tailnet-only; HTTPS lets the phone install the PWA | Direct links are a few ms; measure relay latency early (C30) |
| Live updates | **One SSE stream per client** for hub state, widget pushes and orb state; WebSocket only for audio | SSE reconnects on its own; one stream per client | ~10–100 ms event to pixel |
| Phone | **Installed PWA** | No app store, same code | Opens from cache, then live |
| Laptop B | Full hub as the **ambient screen** in an Edge app window (kiosk-style, full screen) | Zero extra code; it's the always-on display | Local |
| Laptop A | **pywebview (WebView2)**, full hub + compact strip, as in Pen Reader | Reuses Pen Reader's toolchain | Must meet C37 (≤ ~3% CPU): the strip is static, the hub window pauses animation when hidden or in game mode. If the strip fails, rebuild only the strip in **Tauri** |
| Auth | Tailnet membership + hub token | Personal data | — |

---

## 5. Design system: "Earth HUD" (Huw's layout, Pen Reader's palette)

**Decision (2026-11-14, afternoon):** De Wet chose **Huw's HUD layout in Pen Reader's plant-and-earth-tone design**. The structure comes from Huw (ambient orb + big clock, windows that pop up while Jarvis talks, the Life Map, page dots); the look comes from Pen Reader (cream paper, sand desk, terracotta for the one main action, plant greens for growth, soft rounded cards, one warm shadow, Lexend + Atkinson). This replaces the morning's dark neon "Night HUD". Evening uses Pen Reader's warm charcoal theme, not neon. All values live in one `tokens.css`; switching theme changes only token values.

**Why this fits the research (JARVIS_PSYCHOLOGY.md A1–A11, E3, K1–K7):** warm medium-saturation colour instead of cold grey or neon (A1), curves over sharp edges (A2), cream pages for reading (A9), one accent with one job (A8, K5), calm periphery (E3, K1). Huw's contribution is *structure and behaviour*, which the research doesn't contradict.

### 5.1 What Huw's interface does (observed 2026-11-14, reels May–Nov 2026)
- **Ambient idle screen:** full-screen canvas with a faint **dot grid**, thin lines and small brackets at the screen edges; a **circular orb** with the assistant's name in the centre; a **large, thin clock** under it; **page dots** at the bottom; tiny status text in the corners.
- **When active:** the orb **moves to the bottom-right corner** and the canvas fills with windows.
- **Thinking/speaking:** the orb becomes several **rotating, intersecting rings** (a gyroscope).
- **Windows:** rectangular panels with thin outlines, small titles, one **big number** or a **mini bar chart**, photo/video/camera tiles; arranged as a loose grid collage; pushed by the assistant.
- **Chrome:** a row of small tabs top-right; a status line bottom-left.
- (His palette is dark navy with cyan, or black with magenta for "Rose". **We don't use it.**)

### 5.2 Earth HUD tokens: Daylight (default) — straight from Pen Reader's `ui/app.css`
- **Surfaces:** canvas (the desk) `#f3ecdf` · sheet `#fbf5e6` · card `#fffbf3` · sunken `#ede4d3` · lines `#e6dcc9` / `#d6c9b1` · control `#8f826d`.
- **Text:** `#2b2622` · muted `#6b6258`.
- **Accent (the one main action, the orb):** terracotta `#b4512a` (hover `#9d4420`, soft `#f6dfd2`, ink `#8c3a1b`; white label contrast 5.1:1).
- **Growth (progress, done, "Your call", Life Map stems):** growth-soft `#e3efe0`, leaf-ink `#2f6a4a`; plants `--leaf #5c9471`, `--leaf-deep #3f7355`, `--stem #4f7a60`, clay pot `#cf9670`, bloom `#f2b655`.
- **Notice / error:** `#fff3cf` / `#6f4a06` · `#fbe3dc` / `#8a2a17`. Honey highlight `#ffe7a3`.
- **HUD touches, in earth tones:** dot grid in `--line` at 24 px on the canvas; panel outlines `--line-strong`; corner brackets in `--control` on the active window; the orb's glow is terracotta-soft, never neon.
- **Shape:** controls 12 px · cards/windows 18 px · sheets 24 px · pill tabs; control height 40 px; padding 20 px.
- **Depth:** one soft warm shadow (`0 1px 2px rgba(96,70,30,.06), 0 8px 24px rgba(96,70,30,.08)`); no glows except the orb.
- **Type:** Lexend (headings, buttons, labels, big numbers, the clock at weight 300); Atkinson Hyperlegible Next (body 15/23, reading blocks held to a comfortable line length with `--measure`); labels in Lexend 500, small caps tracking 0.06em, **never below 12 px**; tabular figures for numbers; JetBrains Mono only for tiny telemetry.
- **Plants:** Pen Reader's leaf family (`tools/make_plants.py`) is reused: a small plant on the ambient screen that grows with the day's completed items (progress, never a streak or guilt; K6, A7), and the **Life Map drawn as a plant**: stems from the orb, leaf-shaped branch nodes (LIFE_TREE §11).
- **Contrast:** every text pair ≥ 4.5:1; outlines and badges ≥ 3:1 (Pen Reader's palette already passes; re-checked by the gate).

### 5.3 Evening tokens (Pen Reader's warm dark)
Canvas `#1f1c19` · sheet `#26221f` · card `#2d2925` · text `#efe7da` · muted `#b5ab9c` · accent `#f0a27a` · leaf-ink `#9fd3b0` · plants as in Pen Reader's dark block. Follows Windows or set in Controls; by default the ambient screen switches to Evening at Saskatoon's real sunset and back to Daylight at sunrise (worked out on the device with the standard sunrise equation, within a couple of minutes, no network; checked every minute).

### 5.4 The orb (Jarvis's face)
SVG (not WebGL, to stay light on both laptops; the look can borrow from his `aiorb-react-component`), ~200 px on the ambient screen, 48 px in the corner, 16 px static in the strip. States, each with a label for screen readers and a word in the status line:
| State | Look | Reduced motion |
|---|---|---|
| Idle | Terracotta ring with a slow breathing soft glow (6 s cycle) and a faint halo of tiny leaf-green dots; "JARVIS" in small caps | Static ring |
| Listening | Ring brightens and its thickness follows his voice level | Ring solid accent + "Listening" |
| Thinking | Two or three tilted ellipses rotate around the ring (Huw's gyroscope), ≤ 1.5 s per turn | Dashed ring + "Thinking" |
| Speaking | Ring pulses with the TTS audio level | Ring solid + "Speaking" |
| **Waiting for your yes** | A tick ring that empties over the ~10 s answer window (RUNTIME §9.2) | Countdown number |
| Muted | Grey ring with a mic-off glyph | Same |
| Offline / problem | Ring with a gap + notice colour; status line says what to do | Same |
- **Animation budget:** CSS/SVG transforms only, ≤ 30 fps on the ambient screen, paused when the page is hidden. The strip's orb never animates.

### 5.5 Motion
- Feedback only: widgets slide/fade in 200 ms; the Life Map flies in 300 ms; press scale 0.97; focus ring 2 px accent.
- Nothing loops for attention except the idle orb's slow breathing (which stops under reduced motion and on battery saver).

### 5.6 Components (Jarvis additions to DESIGN.md)
Orb · ambient clock · status line · page dots · day plant · window (HUD panel with corner brackets) · big-number widget · mini chart · now card · branch card · Life Map node · breadcrumb · fact card · source chip · confidence label · action-log row · approval card · Unsorted item · strip.

### 5.7 Copy
Sentence case for sentences; small-caps labels only for short panel titles (Next, Due, Open loops). Greeting by time of day; errors say what to do next.

---

## 6. Quality bar (same as Pen Reader)
A mock backend that drives every state (`?scene=` URLs, including every orb state and widget type), screenshots of every view in **both themes** at phone, strip, laptop and ambient (full-screen 1080p/1440p) sizes, and three independent reviews (design, accessibility, hands-on walkthrough). Contrast ≥ 4.5:1 for every chip and text pair. A **visual-verdict** pass against Pen Reader screenshots for palette and feel; Huw's layout is checked against the description in §5.1 (no copies of his video frames are kept). Details in JARVIS_BUILD_AND_CONSISTENCY.md.

## Sources
Google PAIR, Explainability + Trust https://pair.withgoogle.com/chapter/explainability-trust/ · Microsoft HAX pattern library https://www.microsoft.com/en-us/haxtoolkit/library/pattern/ · Bansal et al. https://arxiv.org/pdf/2006.14779 · Vasconcelos et al. https://ar5iv.labs.arxiv.org/html/2212.06823 · Claude memory https://support.claude.com/en/articles/11817273-how-does-claude-s-memory-work · Meta "Why am I seeing this?" https://about.fb.com/news/2019/03/why-am-i-seeing-this/amp/ · Agent UX patterns https://hatchworks.com/blog/ai-agents/agent-ux-patterns/ · Activity log pattern https://aiuxplayground.com/pattern/activity-log · Limitless consent https://help.limitless.ai/en/articles/10540861-how-to-ask-for-consent-and-let-others-know-about-the-pendant · Tailscale Serve https://tailscale.com/kb/1312/serve · SSE vs WebSocket https://websocket.org/comparisons/sse/ · Tauri overlay footprint https://dev.to/manasightgg/why-i-chose-tauri-v2-for-a-desktop-overlay-in-2026-597h · Pen Reader docs/design.md, PLAN.md, ui/app.css · Huw Prosser's Instagram reels (@huwprosser): https://www.instagram.com/huwprosser/reel/DYK2IWyoEWh/ · https://www.instagram.com/huwprosser/reel/DfGOQ5pIZqy/ · https://www.instagram.com/huwprosser/reel/Dfo8IADoLCj/ · https://www.instagram.com/huwprosser/reel/DfXwuL0izsO/
