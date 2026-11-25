# Jarvis — Life Tree and Life Map Design

Last updated: 2026-11-14
Status: design, built in P1 (tree, placement, branch cards, voice access, Life Map v1) and P2 (branch proposals, nightly stories). Part of the design set in Jarvis/. Extends JARVIS_DESIGN_MEMORY.md (same database, same pipeline) and JARVIS_DESIGN_HUB_TRUST.md (the HUD look and the Life Map view).

**What De Wet asked for (2026-11-14):** "I want to be able to access information about any part of my life at will… every part of my life gets its own branch… school stuff under a general branch… then other branches that go into more detail, like one for each class." The hardest part: making it graphic, accessible, user-friendly and well designed, in the style of Huw Prosser's HUD.

---

## 1. The idea

Every memory Jarvis holds already has a subject. The **Life Tree** gives every subject a home: one tree with De Wet at the root, a handful of big **areas** (School, Projects, People, Life, Learning, Tech), and branches that get more specific as you go down (School › Fall 2026 › GE 122 › Assessments › Midterm 2).

- **Each branch has a card**: what's happening, what's next, what's due, what's open, the key facts with their sources, the people, the files, what changed recently, and what Jarvis doesn't know.
- **He can reach any branch at will**, by voice ("what's going on with GE 122?", "open Pen Reader") or on the hub, where the tree is drawn as a **Life Map**: a HUD-style constellation he can fly through.
- **Jarvis files things itself.** New facts land on the right branch automatically; anything it isn't sure about waits in **Unsorted** for a one-tap or one-word decision.
- **The tree is a view over the memory, not a second store.** Branches are rows in the same SQLite file; facts keep their sources, history, undo and forget exactly as in JARVIS_DESIGN_MEMORY.md.

**Latency effect:** none on normal turns. Branch cards are pre-built in the background (T2), reading one is a single row (< 5 ms), "open X" is a T0 command (no LLM), and asking about a branch adds ~1k tokens of card to an otherwise normal T1 turn (~50–100 ms).

---

## 2. Requirements this design meets

| Need | How |
|---|---|
| Any part of his life, at will | Every memory item is linked to ≥ 1 branch; every branch has a pre-built card; voice and hub both open any branch in one step |
| A branch per part of life, general → specific | A tree up to 4 levels below the root; areas → branches → leaves → details |
| Graphic and well designed | Life Map: HUD constellation with semantic zoom, in the Huw-inspired look (HUB_TRUST §5) |
| Accessible and user-friendly | Same data also as an outline list (keyboard, screen reader, phone); every encoding has a word or icon, never colour alone; ≤ 7 branches shown per level |
| Fast (C7–C10) | Pre-built cards; T0 navigation; subtree filters are plain SQL |
| Trust (nothing is a black box) | Every card line keeps its source chip; every filing, move, rename and merge is in `audit` and undoable |
| Privacy (C21–C23) | Branches carry a privacy tier; sensitive areas never show on ambient screens, the strip, the phone lock screen or the cached prompt |
| One maintainer (C34) | Two tables and one card builder added to the existing memory service; no graph database, no new process |

---

## 3. The tree

### 3.1 Levels
| Level | Name | Example | Typical count |
|---|---|---|---|
| 0 | **Root** (him) | De Wet | 1 |
| 1 | **Area** | School | 6–8 |
| 2 | **Branch** | Fall 2026 · Jarvis · Residence | ≤ 7 visible per area |
| 3 | **Leaf** | GE 122 · Pen Reader v2 · Laundry | ≤ 7 visible per branch |
| 4 | **Detail** | GE 122 › Assessments · GE 122 › Lectures | only where there's enough to say |

Rules: **at most 4 levels below the root** (deeper trees get lost; a course's 30 lectures are items on the Lectures branch, not branches). **At most 7 children shown** at once; the rest collapse into "+3 more" sorted by recent activity.

### 3.2 Starting tree (seeded from what Jarvis already knows; he renames, moves or deletes anything)
| Area | Branches (seed) | Seeded from |
|---|---|---|
| **School** (USask) | **Fall 2026** › one leaf per course (GE 122, CHEM 142, GEOL …), each with details: Lectures · Assessments · Labs/Tutorials · Policies (incl. the course's AI rules) · People (prof, TAs) · Grades. **Study system** (study plans, techniques). **Admin** (registration, PAWS, residence fees, scholarships) | PAWS → `schedule.json`, `courses.json`, `lecture_topics.json`, `homework.json`; Class Content folder (one folder per class and lecture); Canvas courses |
| **Projects** | Jarvis · Pen Reader · Praelecta · Cedar Student Pilot · Ideas (unfiled) | His Claude Projects and docs, repos, F12 |
| **People** | Family · Friends · Classmates · Profs & TAs · Others | Entities of type person; relationship context only, never a dossier (F3.17) |
| **Life** | Residence (Maple Hall, laundry) · Errands & admin · Money (tier 2) · Health & fitness (tier 2) · Plans & trips | Calendar, laundry-timing, what he says |
| **Learning** (outside school) | High Valyrian · anything he starts learning | What he says; study-plan for outside topics |
| **Tech & setup** | Laptop A · Laptop B (hub) · Phone · Gaming · Desk setup | Device info, game mode, his own notes |
| **Unsorted** (system) | Items Jarvis couldn't place with confidence | Placement step (§5) |

- **Terms roll over:** "Fall 2026" archives itself two weeks after his last final (from the syllabus/PAWS dates); "Winter 2027" is created from PAWS when he registers. Archived branches leave the map's main ring but stay searchable ("what did I get on the CHEM 142 final last fall?").
- **Course leaves come from official data**, so the tree is right on day one without him typing anything.

### 3.3 What hangs on a branch
Everything in memory can link to a branch: **entities** (the course, the prof), **facts** (due dates, decisions, preferences), **episodes** (the conversation where he said it), **open loops**, **files** (Class Content paths, repo paths), **calendar events**, **actions** (receipts in Activity) and **patterns** ("PPS takes you ~2× the estimate"). An item can live on more than one branch (a lab partner is on People › Classmates and on CHEM 142); one link is **primary**, the others are **also**.

---

## 4. Data model (added to `jarvis.db`)

**`branches`**
| Field | Meaning |
|---|---|
| `id`, `parent_id`, `path` | Materialised path, e.g. `school/fall-2026/ge-122/assessments`. Subtree = one indexed range query (`path >= 'school/' AND path < 'school0'`), < 1 ms |
| `name`, `aliases[]` | "GE 122" = "engineering math" = "linear algebra". Aliases feed the T0 grammar and the STT word boost |
| `level`, `kind` | area · branch · leaf · detail · system (Unsorted) |
| `entity_id` | Optional: the entity this branch *is* (the course GE 122) |
| `icon`, `glyph` | One line icon + a 2–3 letter glyph for the map (GE, CH, PR) |
| `status` | active · proposed · archived |
| `privacy_tier` | Inherited from the parent unless set (§10) |
| `created_by`, `confirm_state` | his · official (PAWS/Canvas) · jarvis-proposed; stated / proposed |
| `sort_hint`, `pinned` | Manual order; pinned branches always show on the map |
| `centroid` | Mean embedding of its items, refreshed nightly (used by placement) |
| `activity_14d`, `next_due_at`, `open_loop_count`, `pending_yes_count` | Roll-ups for the map's encodings, updated by the card builder |
| `valid_from`, `valid_to` | Terms and finished projects have an end |

**`branch_links`**: `item_type` (fact, entity, episode, open_loop, file, event, action, pattern), `item_id`, `branch_id`, `role` (primary / also), `assigned_by` (rule · entity · embedding · llm · him), `confidence`, `ts`. Index on (`branch_id`, `item_type`) and (`item_type`, `item_id`).

**`branch_cards`**: `branch_id`, `card_json`, `card_text` (spoken/LLM form, ~300–900 tokens), `story` (nightly paragraph with citations), `built_at`, `inputs_hash`. Rebuilt only when `inputs_hash` changes.

**Audit:** creating, renaming, moving, merging, archiving a branch and every link change is an `audit` row with before/after, so "undo that" and "undo everything you filed today" work exactly as in MEMORY §9.

---

## 5. Placement: where does a new memory go?

A new step in the write pipeline (MEMORY §4), **between "resolve entities" and "reconcile"**. All T2, never on the hot path.

1. **Rules first (free, ~0 ms):** a course code in the text or source (GE 122, CHEM 142) → that course; a Class Content path → its class and lecture; a Canvas or Crowdmark course id → its course; a calendar event's colour and title pattern (his colour scheme) → its branch; a repo or project folder → its project; an email sender on a course's people list → that course.
2. **Entity link:** if the fact's subject or object entity already has a branch, it goes there.
3. **Embedding match:** cosine similarity to branch centroids, restricted to active branches. Top score ≥ 0.80 and ≥ 0.10 ahead of the runner-up → placed.
4. **LLM judge for the grey zone:** Haiku picks from the top 5 candidate paths (or "none"); batched with extraction, so no extra call in most cases.
5. **Otherwise → Unsorted**, with Jarvis's best guess attached.

- **His moves teach the rules.** When he moves an item ("put that under Pen Reader"), the link is set `assigned_by = him` (pinned, never re-placed by inference), and a pattern is recorded so similar items follow.
- **Outside content is placed like anything else**, but placement never raises its authority (MEMORY §4 step 4).
- **Accuracy target:** ≥ 90% correct primary branch on a labelled set of 200 real items; Unsorted ≤ 10% of new items per week.

---

## 6. Growing and pruning the tree

| Change | Who | How |
|---|---|---|
| **New course / term** | Automatic (official source) | PAWS or Canvas shows a new course → leaf + standard details created; announced once in the debrief ("Added Winter 2027 with 5 courses.") |
| **New project or topic** | **He says so** | "Make a branch for High Valyrian" / "Start a project called X" → created at once (T0 command + T2 write) |
| **Proposed branch** | Jarvis suggests | ≥ 5 items in Unsorted or on one branch cluster around a new entity or topic over ≥ 2 days → a **proposed** branch (dotted outline on the map) and one line in the next debrief: "You've mentioned the robotics club a few times. Give it a branch?" Yes / no / "under School". Max one proposal a day |
| **Move, rename, merge** | He decides | Voice ("move Praelecta under School", "rename that to Linear Algebra", "merge People › Others into Friends") or drag on the map; read back and done; undoable |
| **Archive** | Automatic or him | Terms end; projects with no activity for 60 days are *proposed* for archiving (never archived silently unless it's an official end date) |
| **Delete** | Him | Deleting a branch moves its items to the parent (never deletes memories); forgetting the content is a separate, explicit "forget" (MEMORY §9) |

Creating, moving and renaming branches are **Jarvis's own notes**, so they don't need an approval (RUNTIME §9.1), but every one is visible in Activity and undoable.

---

## 7. Branch cards

A **branch card** is the now card's sibling: a templated briefing for one branch, built by code (deterministic, < 100 ms), stored, and read in ~0 ms.

**Fixed sections (each ≤ 3 lines; empty sections are left out):**
1. **Status:** one line (e.g. "GE 122 · Week 10 of 13 · on track; PPS 7 in progress").
2. **Next:** the next 3 events (lecture, lab, meeting) with time and room.
3. **Due:** items due within 14 days, nearest first, each with a countdown and progress.
4. **Open loops:** commitments on this branch, each with its planned slot.
5. **Key facts:** pinned and top-ranked facts, each with its source chip (`[you, 3 Nov]`, `[Syllabus p.2]`, `[Canvas]`).
6. **Decisions:** his recent decisions here, with "Your call · date".
7. **People:** who's involved (name + role only).
8. **Files:** the 3 most relevant files with paths (study pack, solutions, repo).
9. **Recent:** the last 5 changes on this branch (from `audit`), each undoable.
10. **Gaps:** what Jarvis doesn't know here ("no grade yet for Lab 4").
11. **Story** (nightly, P2): a 2–4 sentence summary written by Sonnet in the nightly batch, **every sentence citing its facts**; labelled "summary" on the hub, never presented as his word.

- **Roll-ups for parent branches:** a parent's card summarises its children (counts, nearest due date across the subtree, children needing attention) rather than repeating their contents. "School" = "5 courses · 3 things due this week · CHEM 142 lab report is the closest."
- **Rebuilt on events** for the affected branch and its ancestors (debounced 2–5 s): a fact added or superseded, a due date changed, an event moved, a file filed, a task done.
- **Never in the cached prefix.** Cards go into a turn only when that branch is asked about or is the active context (§9), so the prompt cache stays warm.

---

## 8. Asking about any part of his life (voice)

| He says | What happens | Tier and latency |
|---|---|---|
| "Open GE 122" / "show me Pen Reader" | T0 grammar matches a branch name or alias → the hub flies the Life Map to that branch and opens its page | **T0**, < 50 ms match + ~150 ms to pixels |
| "What's going on with GE 122?" | T0 resolves the branch; its card is attached to the turn; Haiku answers in ≤ 3 items from the card; the hub opens the branch page at the same time | **T1**, first audio ≈ a normal turn + ~50–100 ms for ~1k card tokens |
| "What's due in School?" / "anything I'm forgetting in Projects?" | Same, using the area's roll-up card | T1 |
| "What did the prof say about the midterm?" | Deep recall (MEMORY §7.4) with `branch = ge-122` (subtree filter) and the card as context; "let me check" if > 300 ms | T1 + 70–200 ms |
| "Go deeper" / "assessments" / "back" / "up" | Map navigation on the current branch | T0 |
| "Put that under Pen Reader" / "file this under CHEM" | Moves the item just discussed or shown; read back once ("Moved to Pen Reader.") | T0 match, T2 write |
| "Make a branch for the robotics club" | Creates it (under the best-matching area, said aloud so he can correct) | T0 match, T2 write |
| "What's in Unsorted?" | Reads the top 3 with Jarvis's guess each; "yes" files them | T1 |

- **Branch names are spoken words, so they're added to the STT hotword list** (course codes like "GE one twenty-two" are easy to mishear).
- **Ambiguity:** two matches ("labs" → CHEM 142 or GEOL) → one closed question with the likely answer first: "CHEM 142 labs?"

---

## 9. Retrieval scoped to branches (replaces "domain gating")

MEMORY §5 gates retrieval by domain so school memories don't leak into unrelated answers. The tree makes this precise:
- **Active branch(es):** set by context: the branch he asked about, the class he's in or just left (schedule), the file or repo open on Laptop A, the project he said he's working on (F12.3). Shown on the hub's status line ("Context: GE 122").
- **Recall filters** to the active subtree first, then widens to linked branches (one hop via `also` links and entity links), and only searches the whole tree when he asks broadly ("anything about X anywhere?") or the first pass finds nothing.
- **Leakage rule:** a memory from another area enters an answer only if it changes the answer (code of conduct rule 4; F3.26). Tier-2 branches never leak (§10).
- **Latency:** the subtree filter is part of the SQL (no extra step); it makes recall slightly *faster* by shrinking the candidate set.

---

## 10. Privacy per branch
- **Tier inheritance:** a branch inherits its parent's privacy tier unless set. Life › Money and Life › Health & fitness default to **tier 2** (local only; sent to the cloud only when the current task needs it, reason logged).
- **Never on display surfaces:** tier-2 branches don't appear on the ambient HUD, the strip, the phone's lock-screen widget or any widget pushed while someone else may be present; the map shows them as a closed node with a lock glyph until he opens them on purpose.
- **Never in the cached prompt** and never in a roll-up card's spoken text unless he asked about that branch.
- **"Hide this branch"** removes a branch from the map entirely (still searchable by him by name).
- **Forget a branch** = forget everything only it supports (MEMORY §9, with a preview of what goes).

---

## 11. The Life Map (the graphic explorer)

### 11.1 Options explored
| Option | What it looks like | Good at | Weak at | Verdict |
|---|---|---|---|---|
| **A. Constellation (radial tree, semantic zoom)** | Him (the orb) at the centre; areas on a ring; tap or say a branch and the map flies in: that branch becomes the centre with its children around it | Feels like Huw's HUD; orientation (you always know where you are); shows activity at a glance; works with voice ("open X" = fly to X) | Pure spatial views are hard for screen readers and on narrow screens | **Primary view on the big screens** |
| **B. Drill-down columns (Miller columns)** | Area | Branch | Leaf columns side by side, like macOS Finder | Fast, precise, keyboard-friendly | Looks like a file manager, not a HUD | Used inside the **outline view** |
| **C. Sunburst / treemap** | Nested rings or rectangles sized by activity | "Where is my time and stuff?" overview | Labels get tiny; hard to read; hard to click | Kept only as a **weekly review widget** (P2) |
| **D. Force-directed graph** | Everything linked to everything | Shows cross-links | Messy, unstable layout, slow, hard to use | Rejected |
| **E. Plain outline (tree list)** | Indented list with counts | Accessible, phone, screen reader | Not graphic | **Accessible view and phone view** |

**Choice:** **A + E over the same data**, plus a **branch page** that both open. The constellation is what he sees and talks to; the outline is the same tree for keyboard, screen readers and the phone. Toggle with one key ("L") or "show as list".

### 11.2 Constellation spec
- **Layout:** radial tree (d3-hierarchy `cluster` in polar coordinates). The current focus sits in the centre as the orb; its children sit on a ring; grandchildren appear as small dots on an outer ring (preview only). Siblings of the focus fade to a thin arc so context is never lost.
- **Semantic zoom:** flying into a branch takes 300 ms (ease-in-out); the new centre's children fade in; breadcrumbs update (`LIFE › SCHOOL › FALL 2026 › GE 122`). "Back", Esc or a tap on a breadcrumb flies out.
- **Node anatomy:** a circle with the branch glyph (GE), its name below in the mono label style, and up to two **badges**, each icon + number, never colour alone:
  - **Size** = activity in the last 14 days (3 sizes only, so it's readable).
  - **Due ring** = a thin arc that fills as the nearest due date approaches (≤ 72 h → accent colour + "2d" badge).
  - **Needs-your-yes dot** = pending approvals on this branch.
  - **Dotted outline** = proposed branch; **dim** = archived; **lock glyph** = tier 2.
- **Limits:** ≤ 7 children around a centre; the rest collapse into "+3 more" (sorted by activity). ≤ ~60 nodes drawn at any time.
- **Search:** type or say a name from anywhere ("/" focuses search); results fly the map to that branch.
- **Live:** badges update over the hub's SSE stream (~10–100 ms) when cards are rebuilt; a branch that just changed glows once (no repeating animation).
- **Keyboard:** arrow keys move around the ring, Enter flies in, Backspace flies out, "L" toggles the outline. Every node is a focusable element with a text label (the SVG uses real `<a>`/`<button>` roles).

### 11.3 Branch page
Opens beside the map (or full screen on the phone). HUD panels, ≤ 6 visible, the rest under "More":
- **Header:** breadcrumb, branch name, glyph, status line, the "Context: …" chip if it's active.
- **Panels:** STATUS · NEXT · DUE (big countdown number for the nearest item, e.g. `2D 04H`) · OPEN LOOPS · KEY FACTS (fact cards with source chips, Confirm/Edit/Pin/Forget) · RECENT (changes with Undo) · then under More: PEOPLE · FILES (open on Laptop A with one tap or "open it") · DECISIONS · GAPS · STORY.
- **Children strip:** the branch's children as small tiles along the bottom, so drilling down never needs the map.
- **Controls:** rename, move, archive, hide, privacy tier, "pin to map", "forget branch" (with preview).

### 11.4 Outline view (accessible and phone)
An indented list: name, counts ("3 due · 1 needs your yes"), and the same badges as words. Expand/collapse with arrow keys; screen-reader tree semantics (`role="tree"`). On the phone this is the default Life view, and a branch opens as a full-screen card.

### 11.5 Voice and map together
- The map follows the conversation: "what's going on with GE 122?" flies the map there while Jarvis answers.
- **Widget push** (HUB_TRUST §2a): when Jarvis mentions a branch, a file, a due date or a chart, it pushes that widget onto the HUD (the PPS 7 PDF, the due-date countdown). Pushed widgets fade after 60 s of no use unless pinned ("keep that up").

### 11.6 Performance budget
- SVG + d3-hierarchy and d3-zoom (~30 KB); no canvas or WebGL needed at ≤ 60 nodes.
- Flying: CSS transforms only, 60 fps on Laptop B; on reduced motion the map cuts instead of flying.
- First paint of the map from cached state: < 300 ms; a branch page from its stored card: < 100 ms.
- **Laptop A never runs the map in the strip** (C37). The full hub window on Laptop A pauses all animation when hidden or in game mode.

---

## 12. Tests
- **Placement:** ≥ 90% primary-branch accuracy on a labelled set of 200 real items; replayed after every pipeline change. Every move he makes becomes a test case.
- **Voice access:** 50 spoken branch requests (incl. aliases and course codes) → ≥ 95% correct branch; ambiguous ones ask one question.
- **Cards:** every line traces to a fact id; build < 100 ms; a changed due date shows on the card and the map within 5 s.
- **Leakage:** questions about one area never surface tier-2 items or unrelated areas unless they change the answer (extends the "Know De Wet" probes).
- **Forget and undo:** forgetting an item removes it from every card, centroid and roll-up; undoing a move restores the old link only.
- **Accessibility:** outline view fully usable with keyboard and screen reader; contrast ≥ 4.5:1 for every label and badge in both themes; reduced motion respected.

## Sources
Huw Prosser's Instagram (@huwprosser), reels viewed 2026-11-14: DYK2IWyoEWh (pinned, May 2026: ambient Jarvis screen, orb + clock, orb moves to the corner), DfGOQ5pIZqy (Oct 29: "Rose" orb, gyroscope "thinking" state, pushed widget collage), Dfo8IADoLCj (Nov 12: monitor HUD widgets, tablet setups), DfXwuL0izsO (Nov 5: dual-monitor setup with the assistant beside a terminal). Design reasoning for the explorer options is ours; it follows the calm-technology and progressive-disclosure principles already cited in JARVIS_DESIGN_HUB_TRUST.md.
