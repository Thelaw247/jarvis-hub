# views/reach (R3): Reach in the hub

- **Controls › What Jarvis can do** (`/controls/reach`, `reach.js`): the six rungs of the reach ladder with every
  tool (reads, writes, status: connected · needs sign-in · paused in game mode · off, last used, on/off switch),
  the allowed folders (editable), app scopes, standing permissions (revocable) and the caps for Claude tasks.
  Actions: `set reach:tool:<id> {value}`, `set reach:folders {value: [...]}`, `set reach:caps {task_usd, day_usd}`,
  `revoke <id>`. The hub checks them (`jarvis_hub/reach.py`) and answers with `reach.updated`.
- **Activity › Tasks** (`/activity/tasks[/<id>]`, `tasks.js`): Claude tasks, running and finished; one opened shows
  every step, the files it touched, its waiting ask (the same approval card: Allow · Deny · Allow for this task),
  the transcript, and Stop or Undo. In demo mode, "Run the demo task" plays "Design a phone stand in Fusion".
- **Email catches**: flagged emails reach the Rail's Messages slot as one line each with the reason (reading only).
- `scene-act.js` mirrors the hub's rules for `?scene=` (core/bridge.js `addSceneAct`).

Scenes: `reach`, `reach-game`, `reach-strict`, `reach-empty`, `messages-catches`, `task-starting`, `task-running`,
`task-waiting`, `task-ask-again`, `task-parked`, `task-done`, `task-stopped`, `task-undone`, `tasks`, `tasks-empty`,
`task-detail`, `task-detail-waiting`, and `component:agent-task`.
