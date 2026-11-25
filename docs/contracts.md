# Contracts v2

Everything the hub UI shows or sends goes through these shapes. The demo backend speaks them now; `jarvis-core`
will speak the same ones later, so the UI doesn't change when the hub goes live.
**v1 was frozen at gate G0. v2 (hub v0.3.0, the Night HUD, package N0) adds what "nothing gets away" needs.**
A change needs the overseer's approval and a version bump (`v` in the envelope and state).

| File (`contracts/`) | What it is | Example (`contracts/examples/`) |
|---|---|---|
| `common.schema.json` | Shared pieces: `id`, `iso`, `source` (icon + word chip), `confidence` (sure, likely, guess), **`thumb`**, **`glance`**, **`slot`** | — |
| `state.schema.json` | The whole hub state, `GET /api/state` | `state.json` (the demo day; also what `?scene=` uses) |
| `event.schema.json` | The envelope for live updates, `GET /api/events` (SSE); `$defs` holds the data shapes of the v2 events | `event.json` |
| `act.schema.json` | A UI action, `POST /api/act` | `act.json` |
| `orb_state` | The orb: idle, listening, thinking, speaking, waiting, muted, offline, **standby**, **alert**; **`alert`** (warn, crit) on top of any state; **`last_wake`** on a wake | `orb_state.json` |
| `now_card` | Next up, one flag, ready to offer, gaps, day progress, **`moment`** | `now_card.json` |
| `branch` · `branch_card` | A Life Tree node, and its briefing | `branch.json`, `branch_card.json` |
| `fact` | One thing Jarvis knows, with source, confidence, history, conflict | `fact.json` |
| `action` | A receipt (or a held-back remark) with its undo window | `action.json` |
| `approval` | A write waiting for his yes: consequences first, read-back, answer window | `approval.json` |
| `window` | A HUD window (widget push), with **`docked`** and **`slot`** | `window.json` |
| `day` | Today's timeline and proposed changes, and **`dial[]`** for the day dial | `day.json` |
| `job` · `caption` · `toast` | Working-on chip, spoken-line caption, short notice | same names |
| `settings` · `metrics` | Controls, Under the hood | same names |
| **`rail`** | The Rail: six fixed slots that track things | `rail.json` |
| **`marks`** | "Since you looked" marks, one per thing | `marks.json` |
| **`thread`** | A work thread and its resume point | `thread.json` |
| **`focus`** | The focus cue: what Jarvis means right now | `focus.json` |

## What changed in v2 (every change)

1. **Version.** `v` is `2` in the state and in every event envelope. The SSE client (`ui/core/events.js`) takes
   `2` and still folds in a `1`.
2. **Nothing is deleted any more.** `state.windows` holds only the windows **on screen**. A window that is closed,
   pushed out by a sixth, cleared (CLEAR VIEW), stepping aside, timed out, or whose approval ran out is **docked**:
   it moves, whole, to `rail.slots.<slot>.items[].window` with `docked: true` and its `slot`. Only **done** or
   **archive** removes a thing. Pure views (`chart`, `next_up`, with no `slot` of their own) just close.
3. **`window`** gains `docked` (boolean), `slot` (a Rail slot; left out, the hub picks one from the type) and `thumb`.
   Slot by type: approval → `yes` · timeline, timer → `today` · countdown, file → `homework` · fact, unsorted,
   notice → `jarvis` · branch_card → `parked`.
4. **`rail`** (new, kept on the server so the hub, the ambient screen and the phone agree):
   `rail.slots` always has the six slots `yes`, `today`, `homework`, `messages`, `jarvis`, `parked`. A slot is
   `{ items[], count?, done?, worst?, said? }`. An item is a **thing**, not a window:
   `{ ref, slot, kind, title, at, state?, detail?, thumb?, tier?, from?, window? }`.
   - **One item per `ref`** in the whole Rail (docking the same thing again replaces it).
   - **Idle 7 days** (`at`): the item moves into `parked.items` with `from` = its old slot, and `parked.count` goes up.
     It is folded, not lost: it can still be recalled.
   - `slots.jarvis.said[]` keeps **the last 10 lines Jarvis said or toasted** (`{ text, at, kind: caption|toast, source? }`),
     newest first. His own words (a caption whose source is `you`) are not kept.
   - Finished and failed jobs get an item in `jarvis` (they drop out of `jobs`, not out of sight).
   - `count`, `done` (today's share done, the gauge arc) and `worst` (a `glance` state) are for the Rail's own
     logic (`jarvis_hub/rail.py`, N4); N0 only stores them.
5. **`marks`** (new): `{ <ref>: { what, at } }`, one mark per thing; a newer change replaces the older one. The hub
   makes them from:
   - field diffs on `branch.updated` (a due date in the branch card: "Due moved Wed 8 pm → Thu 11:59 pm"; a new
     due item; status; things due), `day.updated` (moved, room changed, added, removed, missed) and
     `nowcard.updated` (next up, the flag → refs `now_card`, `now_card:flag`);
   - anything Jarvis said or toasted (ref `jarvis:said`);
   - finished jobs (ref = the job id); approvals that ran out (ref = the approval id).
   They are cleared **only** by the `seen` action (or `recall` / `archive` of that thing). Being shown, on the
   ambient screen or anywhere, never clears a mark.
6. **`thread`** (new) and `state.threads[]`:
   `{ id, kind, ref, branch, title, thumb?, resume, done[], viewed[], state?, updated? }` with
   `resume { page?, y?, label, source: inferred|confirmed, at }`. Kinds: pdf, video, doc, session, deck, layout,
   code, plotter, research. `viewed` (solutions looked at) shows only under "Why?" or in a review.
7. **`thumb { src, kind, alt }`** (in `common`), allowed on windows, branches, approvals, files, day items, the
   now card's next up, threads and Rail items. `src` is `/api/thumb/<key>.webp` (or a path inside `ui/`); `alt`
   is never empty. Pictures are cached outside git.
8. **`day.dial[]`**: the day dial's arcs in **full ISO date-times** (so it crosses midnight):
   `{ id, kind, start, end?, title, where?, state?, ref? }`; kinds add `exam` and `due` (a due item has `start` =
   when it is due and no `end`); states: upcoming, next, now, done, moved, missed, overdue. `day.items` keep
   their `HH:MM` times for the Today view.
9. **`now_card.moment`**: `rushed | between | settled | heads_down | others | game`: how much Jarvis may say.
10. **`focus`** (new) and `state.focus`: `{ ref, until }`, set by `ui.focus`, for lighting up what Jarvis names as
    he says it. `ref` is a window id or a thing's ref; `ref: null` lets go at once; the hub drops it after `until`.
11. **`glance`** (in `common`): `done | progress | jarvis | soon | yes | critical | parked`, the glance codes
    (HUD v2 §5), used by Rail items and slots.
12. **State:** `rail`, `marks` and `threads` are required; `focus` is optional. A v1 state without them still
    loads (the hub and the store fill them in).

13. **Added at the wave 1 merge (still v2, nothing released in between):**
    - **`settings.earcons`**: `off | minimal | full` (left out = `minimal`): Jarvis's own sounds. Minimal is the wake
      rise and the "heard you" tick; Full adds the low tone with a critical alert. `ui/sounds/earcons.js` reads it.
    - **`settings.address`**: `name | sir | none` (left out = `name`): how Jarvis addresses him ("sir" is opt-in). The
      lines (`jarvis_hub/demo/lines.py` `Voice(address=…)`) follow it.
    - **`orb_state.state`** gains `standby` (the quiet ambient screen) and `alert` (an alert with no other state), and
      **`orb_state.alert`** (`warn | crit`) puts an alert on top of any state. A backend may send these; when it
      doesn't, the shell works them out (`ui/core/orbview.js`): `standby` when the orb is idle and
      `presence.here` is false, `alert: crit` while a thing on the Rail is critical.
    - **A wake is never a state.** It is the change from a resting state (idle, standby, muted, offline) to
      `listening`. The hub adds **`orb_state.last_wake`** to that event: when he woke Jarvis the time before, or
      `null` for the first wake. The orb plays the full wake beat for the first wake of the day or one after ≥ 4 h,
      and the short "tighten" otherwise (`wakeKind(last_wake, now)`); with no `last_wake` field it plays the short one.
    - **`thread.resume.seconds`** (a video's place, seconds from the start), also taken by `resume_save`.
    - **`resume_save` / `resume_accept` go through `jarvis_hub/threads.py on_act` first**: a `session` in the args
      (what the reader saw) is turned into the resume point, the done questions and the time per question there;
      an explicit spot (`{ label, page?, y?, seconds?, confirmed? }`) is saved as given.
    - **The hub refreshes the Rail when it starts, resets and hands out a snapshot** (`rail.refresh`), so the first
      state already holds every derived item and an event that changes nothing on the Rail sends no `rail.updated`.
      The demo fixture's Rail is exactly what `refresh` derives (one item per `ref`; a thread's item uses the
      thread's `ref`, its file).

14. **Added for the Stage (N9, HUD v2 §6.5; still v2, nothing released in between):**
    - **`settings.stage`**: `window | hub` (left out = `window`): where the windows Jarvis pulls up are shown.
      `window` = the **Stage**, a separate borderless window (`/?window=stage#/stage`, made hidden by `app.py`
      at start); the hub's home page stays calm and shows a "Stage · N" chip. `hub` = on the hub's home page, as
      before the Stage. Controls › Look › "Where Jarvis shows things" sets it with `set`. Nothing else changes:
      both windows read the same state and the same live stream; `window.push`, `window.dock`, the Rail and
      the marks work the same on either screen. The phone always shows its own column (it has no Stage).
    - **"Put it on the hub"** is the existing **`open`** action with the thing's page as its target
      (`open` · `/life/ge-122`, `/read/th-pps7`): the hub sends `nav.go`, the hub window follows it and the
      Stage window stays where it is. No new action.
    - **Desktop only, not a contract:** `app.py` gives both windows a small JS API (`show_stage()`,
      `focus_hub(path?)`, `sync_stage(report)`), where `report` is `{ state: { windows: [{ id }], now_card:
      { moment } }, settings: { stage, game_mode } }` (`ui/views/stage/desktop.js stageReport`) and
      `should_show_stage(state, settings, device)` decides: never with `stage: hub`, never in game mode
      (`game_mode: on` or `moment: game`), shown while windows are up; empty, Laptop B keeps it on standby
      and Laptop A hides it.

## Events
`{ "v": 2, "type": "<name>", "ts": "<iso>", "data": { … } }`

| Type | `data` | What the UI does |
|---|---|---|
| `orb.state` | `orb_state` | Orb and status line change |
| `nowcard.updated` | `now_card` | Now card redraws |
| `branch.updated` | `{ branch, card? }` | Life Map badge and branch page update |
| `window.push` | `window` | A window appears; the same id again updates it in place. Pushing a docked window's id **recalls** it (its Rail item goes). With `docked: true` it goes straight to its slot. A sixth window **docks** the oldest unpinned one |
| **`window.dock`** | `{ id }` or `{ all: true }`, + `slot?`, `reason?` (closed, lifetime, evicted, aside, cleared, expired) | The window leaves the screen and docks into its Rail slot (a pure view just closes) |
| **`window.order`** | `{ ids: [...] }` | The windows on screen take this order (ids not named keep their order, after). A real reorder: nothing closes, nothing is marked new |
| `window.close` | `{ id }` | The window leaves for good: **only for done, archive and pure views**. The v1 form `{ all: true }` is still taken and docks everything |
| `caption.show` | `caption` | One line fades in above the Rail |
| `approval.pending` / `approval.resolved` | `approval` / `{ id, status }` | Waiting for you gains or loses an item. `expired` docks the approval (and its window) under `yes`; any other answer takes it off the Rail |
| `activity.added` | `action` | New receipt at the top of Activity |
| `job.progress` | `job` | Working-on chip |
| `toast` | `toast` | Short notice |
| `presence.changed` | `{ here, others?, idle_s? }` | Ambient screen, privacy of pushed windows |
| `fact.updated` | `{ fact }` or `{ id, forgotten: true }` | Memory updates |
| `day.updated` · `settings.updated` | `day` · `settings` | Today, Controls, the day dial |
| `nav.go` | `{ path }` | The hub follows the conversation ("open GE 122", "put it on the hub"); the Stage window doesn't |
| **`rail.updated`** | `rail` (whole) | The Rail redraws. The hub sends it after any event that changed the Rail |
| **`marks.updated`** | `{ marks }` (whole) | "Since you looked" notches redraw. Sent after any event that changed the marks |
| **`thread.updated`** | `{ thread }` or `{ id, archived: true }` | A work thread (and its resume point) changes or goes |
| **`ui.focus`** | `focus` = `{ ref, until }` | Brackets snap onto the thing Jarvis is naming, until `until` |
| **`reach.updated`** (v0.5.0) | `reach` (whole) | Controls › Reach redraws: tools, folders, app scopes, standing permissions, caps |
| **`task.updated`** (v0.5.0) | `{ task }` (`agent_task`) | A Claude task's window, Activity › Tasks and the working-on chip follow it; newest first |
| **`keys.updated`** (v0.5.0) | `{ row, audit? }` (`keys.schema.json#/$defs/updated`) | Controls › Keys updates the row. A row in `fell_back` puts a Your yes item (`ref: keys:<id>`) on the Rail; it goes when the row recovers. Never carries a key |

The store (`ui/core/store.js`) folds every one of these in; `apply_event` in `jarvis_hub/events.py` is its mirror.
Marks, spoken lines, finished jobs and the 7-day fold are worked out **only on the server** and reach screens as
`rail.updated` / `marks.updated`.

## Actions
`{ "action": "<name>", "target": "<id>", "args": { … } }`. Names: approve, decline, change, undo, pin, unpin, close,
close_all, move, resize, forget, confirm, edit, pin_rule, file, mute, unmute, set, apply, skip, keep_mine, use_theirs,
open, ask, revoke, demo, save_layout, less ("less of this"), wrong ("that's wrong"), and in v2:

| Action | Target · args | What the hub does |
|---|---|---|
| `dock` | window id · `{ reason?, slot? }` | `window.dock`. **`close` now does the same** (so the ✕, "close that" and the 60 s lifetime dock) |
| `close_all` | `all` | `window.dock { all: true, reason: "cleared" }` (CLEAR VIEW docks everything) |
| `move` | window id · `{ to: left\|right }` | `window.order` |
| `order` | `windows` · `{ ids: [...] }` | `window.order` |
| `recall` | a thing's `ref` (or its docked window's id) | `window.push` of the docked window; clears its mark |
| `seen` | a `ref`, or `all` | Clears that mark, or every mark ("mark all seen") → `marks.updated` |
| `archive` | a thing's `ref` | Takes it off the Rail for good (and closes its window) |
| `resume_save` | thread id · `{ label, page?, y?, seconds?, confirmed?, session? }` | Saves the resume point (`inferred` unless `confirmed: true`). A local note: no yes needed |
| `resume_accept` | thread id | He took the offer: the resume point becomes `confirmed` |

| `start` (v0.5.0) | `task` · `{ goal, … }` | Starts a Claude agent task inside Reach's limits → `task.updated` |
| `stop` (v0.5.0) | task id | Stops that task; what it already did stays undoable → `task.updated` |

The UI applies the visible effect at once (feedback within 0.1 s) and the backend confirms with events.

## Added in hub v0.5.0 (additive; still contract v2)
- **Window types** `web`, `map`, `agent_task` (`window.schema.json`). Their `data`: `web.schema.json` (`{ pages: [{ id, url,
  title?, site?, frame? }], active? }`; two or more pages get a tab row), `map.schema.json` (the day's stops, route
  and the pin it leads with; a pure view), and for `agent_task` the window's `ref` is the task id in `state.tasks`.
  Each registers itself in the one window-kind registry, `ui/core/window-kinds.js` (content, kicker, role, tier,
  size); the window manager and the content switch ask it, so a new kind needs no switch edits.
- **State** gains optional `reach` (`reach.schema.json`) and `tasks` (`agent_task.schema.json[]`).
- **Categories** (`action.category`, and `approval.category` by convention): `keys` (receipts for key changes) and
  `agent` (a Claude task's permission asks: ordinary approvals answered Allow · Deny · Allow for this task, which is
  `approve` with `args.scope = "task"`).
- **Source kinds** gain `crowdmark`.
- **Keys** (`keys.schema.json`): the `/api/keys` documents, kept apart from `/api/act` on purpose. A key is
  write-only: no document, event, receipt or log ever holds more than its last 4 characters. The hub answers
  `/api/keys` itself with example rows (header `X-Jarvis-Keys: example`) until `JARVIS_CORE_URL` and
  `JARVIS_CORE_SESSION` are set; then it passes the request straight to jarvis-core with `X-Jarvis-Session`.
- **Branch card `recent`**: action ids. A memory change keeps one id for both (`chg-<n>` in jarvis-core's memory
  and on its Activity receipt).

## Routes for pictures and files
| Route | Answers | Served by |
|---|---|---|
| `GET /api/thumb/<key>` | The picture behind `thumb.src` | `jarvis_hub/thumbs.py` `thumb_path(key) -> Path \| None` (the cache outside git, then the made-up demo pictures); 404 for a key nobody made |
| `GET /api/file/<id>` | A file for the hub's reader, with HTTP Range (206); `<id>.qindex.json` is its question index | `jarvis_hub/threads.py` `file_path(file_id) -> Path \| None`; 404 with `Accept-Ranges: bytes` for an unknown id |
| (hook) | `jarvis_hub/rail.py` `refresh(state, now)` derives the Rail's own items, counts and worst states | called at start, on reset, for every snapshot and after every event |

Keys and ids follow the contract id pattern (no slashes), so a request can never walk the disk.

## Rules
- Unknown fields are rejected (`additionalProperties: false`): never invent a field; ask for a contract change.
- Times are ISO local date-times. Sources are always `{ kind, label }` and render as a chip.
- Tier-2 items (`tier: 2`) never appear on the ambient screen or in pushed windows.
- **Dock, never delete.** No client may send `window.close`-style deletion for a thing. In particular the
  **60 s window lifetime in `ui/core/presence.js` (N4) must dock, not close**: send `dock` with
  `{ reason: "lifetime" }`. (Today it sends `close`, which the hub already treats as a dock.) Stepping aside in
  `ui/core/windows.js` sends `dock` with `{ reason: "aside" }`.
- **Moves are `window.order`**, never close + push.
- **Marks are cleared by `seen` only**: on opening the thing, keyboard focus, a deliberate hover (≥ 800 ms) or
  "mark all seen"; never just by being shown.
- Scene mode (`ui/core/bridge.js`) must mirror these rules the way it mirrors the rest of `Hub.act`.

## v1 consumers
Kept working: `state.windows` is still exactly what is on screen; `close`, `close_all` and `move` are still
accepted; a v1 state still loads; v1 envelopes still fold in. What a v1 screen does not show yet is the Rail,
the marks, threads and the focus cue.
