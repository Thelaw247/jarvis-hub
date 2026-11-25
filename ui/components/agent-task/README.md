# jv-agent-task (R3)

A running Claude agent task as a Stage window (REACH §5.4), in the one clean anatomy of HUD v2 §14.2:
`CLAUDE // TASK` kicker with the elapsed time on the right · one hero (the app's view once there is one, else the
goal as a condensed-caps title) · one supporting line (the current step, "Extruding base · 4 of 7", or what it
waits on or how it ended) · the cost so far hanging under the frame. No buttons at rest: **Stop** (while it runs)
and **Open** show on hover or keyboard focus; Open (and the panel itself) goes to Activity › Tasks › the task.

- Window kind `agent_task` (contracts/window), `ref` = the task id (contracts/agent_task, `state.tasks`).
  It registers itself with `registerWindowKind` (views/now/widgets.js), so the Stage and the Now canvas draw it.
- The element reads its task from the store (`task-id` attribute) and redraws on `tasks` / `approvals` changes,
  so steps advance in place without the window being rebuilt.
- Exports used by views/reach: `LIVE`, `TASK_GLANCE`, `elapsed()`, `taskLine()`, `sampleTask(state)`, `SAMPLE_ASK`.
- `demo/task-stand.webp` is the invented Fusion view for the demo (`python tools/make_task_thumb.py`).

Scenes: `?scene=component:agent-task` (every state), and the Stage scenes in `views/reach` (`task-*`).
