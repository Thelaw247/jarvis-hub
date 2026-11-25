// Activity › Tasks (REACH §5.4): Claude agent tasks, running and finished, each with its transcript and Undo.
// /activity/tasks is the list; /activity/tasks/<id> is one task opened (the agent task window's Open): the full step
// list, the files it touched, its permission ask if one waits (the same approval card as Your yes), the transcript,
// and Stop or Undo. Data: state.tasks (contracts/agent_task). Actions: stop, undo, start (demo), approve/decline.
import { asDate, clockTime, html, Jv, whenWords } from "../../core/dom.js";
import { router } from "../../core/router.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { glance } from "../../components/glance/glance.js";
import { elapsed, LIVE, SAMPLE_ASK, sampleTask, TASK_GLANCE, taskLine } from "../../components/agent-task/agent-task.js";
import { withReach } from "./reach.js";

// styles: reach.css (one stylesheet for the package, loaded by reach.js)

const usd = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const CHANGE = { created: "Made", changed: "Changed", moved: "Moved", deleted: "In the undo bin", restored: "Put back" };
const WHO = { claude: "Claude", jarvis: "Jarvis", you: "You" };
const STEP_GLANCE = { done: ["done", "Done"], now: ["jarvis", "Now"], todo: [null, "To do"], skipped: ["parked", "Skipped"] };
const state = (t) => { const [code, word] = TASK_GLANCE[t.state] || TASK_GLANCE.failed; return glance(code, { size: "inline", word }); };
const canUndo = (t, now) => !!t.undo && t.files.length > 0 && asDate(t.undo.until) > now && !LIVE.has(t.state);
const undoBtn = (t) => html`<button type="button" class="jv-btn jv-btn--small" data-act="undo" data-target="${t.id}" data-key="undo-${t.id}">Undo (${t.undo.label})<span class="jv-sr">: ${t.goal}</span></button>`;
const stopBtn = (t) => html`<button type="button" class="jv-btn jv-btn--small" data-act="stop" data-target="${t.id}" data-key="stop-${t.id}">Stop<span class="jv-sr">: ${t.goal}</span></button>`;

class TasksView extends Jv {
  static props = ["params", "route"];
  setup() { this.stop = store.subscribe((_s, keys) => { if (keys.has("tasks") || keys.has("approvals") || keys.has("reach")) this.update(); }); }
  teardown() { this.stop?.(); }
  render() {
    const id = this.params?.[0];
    const task = id && (store.state.tasks || []).find((t) => t.id === id);
    return task ? this.one(task) : this.list(id);
  }

  list(missing) {
    const s = store.state, tasks = s.tasks || [], now = store.now();
    const live = tasks.filter((t) => LIVE.has(t.state)), done = tasks.filter((t) => !LIVE.has(t.state));
    const row = (t) => html`<li class="jv-tasks__row" data-task="${t.id}">
      <span class="jv-tasks__state">${state(t)}</span>
      <a class="jv-tasks__goal" href="#/activity/tasks/${t.id}" data-nav="/activity/tasks/${t.id}" data-key="open-${t.id}">${t.goal}</a>
      <span class="jv-tasks__line">${taskLine(t)}</span>
      <span class="jv-tasks__meta">${whenWords(t.started, now)} · ${elapsed(t, now)} · ${usd(t.cost_usd)}${t.files.length ? ` · ${t.files.length} ${t.files.length === 1 ? "file" : "files"}` : ""}</span>
      <span class="jv-tasks__do">${LIVE.has(t.state) ? stopBtn(t) : canUndo(t, now) ? undoBtn(t) : ""}</span></li>`;
    return html`<div class="jv-view jv-tasks">
      <header class="jv-view__head"><nav class="jv-crumbs" aria-label="Where you are"><a href="#/activity" data-nav="/activity" data-key="crumb">Activity</a><span aria-hidden="true">›</span><span aria-current="page">Tasks</span></nav>
        <h1 tabindex="-1">Claude tasks</h1><p class="jv-view__sub">Bigger jobs Jarvis handed to Claude. Each write it wanted came to you first; what it made can be undone.</p></header>
      ${missing ? html`<jv-notice kind="info" heading="That task isn't here any more" text="Finished tasks stay on this list with their transcript."></jv-notice>` : ""}
      <section class="jv-sheet" aria-labelledby="t-live"><h2 id="t-live" class="jv-view__kicker"><span class="jv-kicker">Running // ${live.length}</span>
        ${s.mode === "demo" && !live.length ? html`<button type="button" class="jv-btn jv-btn--small jv-tasks__demo" data-act="start" data-target="task-stand" data-key="demo">Run the demo task<span class="jv-sr">: design a phone stand in Fusion</span></button>` : ""}</h2>
        ${live.length ? html`<ul class="jv-tasks__list">${live.map(row)}</ul>` : html`<p class="jv-muted">Nothing running. Ask for something bigger, like "design a phone stand in Fusion", and it shows here and on the Stage.</p>`}
      </section>
      <section class="jv-sheet" aria-labelledby="t-done"><h2 id="t-done" class="jv-view__kicker"><span class="jv-kicker">Finished // ${done.length}</span></h2>
        ${done.length ? html`<ul class="jv-tasks__list">${done.map(row)}</ul>` : html`<p class="jv-muted">No finished tasks yet.</p>`}
      </section>
    </div>`;
  }

  one(t) {
    const s = store.state, now = store.now(), live = LIVE.has(t.state);
    const asks = (t.asks || []).map((a) => s.approvals.find((x) => x.id === a.id)).filter((a) => a && a.status === "pending");
    const step = (x) => { const [code, word] = STEP_GLANCE[x.state] || STEP_GLANCE.todo; return html`<li data-state="${x.state}"><span class="jv-tasks__n">${String(x.n).padStart(2, "0")}</span><span>${x.label}</span>${code ? glance(code, { size: "inline", word }) : html`<span class="jv-tasks__todo">${word}</span>`}</li>`; };
    this._asks = asks;
    return html`<div class="jv-view jv-tasks jv-tasks--one">
      <header class="jv-view__head"><nav class="jv-crumbs" aria-label="Where you are"><a href="#/activity" data-nav="/activity" data-key="crumb">Activity</a><span aria-hidden="true">›</span><a href="#/activity/tasks" data-nav="/activity/tasks" data-key="crumb-tasks">Tasks</a><span aria-hidden="true">›</span><span aria-current="page">${t.goal}</span></nav>
        <h1 tabindex="-1">${t.goal}</h1>
        <p class="jv-tasks__status">${state(t)}<span>${taskLine(t)}</span></p>
        <p class="jv-tasks__meta">Started ${clockTime(t.started)} · ${elapsed(t, now)} · ${usd(t.cost_usd)} of a ${usd(t.cap_usd)} cap${t.app ? ` · ${t.app}` : ""}</p>
        <p class="jv-tasks__actions">${live ? stopBtn(t) : canUndo(t, now) ? undoBtn(t) : ""}</p></header>
      <div class="jv-view__cols">
        <div class="jv-view__stack">
          ${asks.length ? html`<section aria-labelledby="t-ask"><h2 id="t-ask" class="jv-view__kicker"><span class="jv-kicker">Claude asks</span><span class="jv-view__count jv-view__count--waiting">${asks.length}</span></h2>
            ${asks.map((a, i) => html`<jv-window heading="Needs your yes" class="jv-tasks__ask"><jv-approval-card data-i="${i}"></jv-approval-card></jv-window>`)}</section>` : ""}
          <section class="jv-sheet" aria-labelledby="t-steps"><h2 id="t-steps" class="jv-view__kicker"><span class="jv-kicker">Steps // ${t.steps.length}</span></h2>
            <ol class="jv-tasks__steps">${t.steps.map(step)}</ol></section>
          <section class="jv-sheet" aria-labelledby="t-files"><h2 id="t-files" class="jv-view__kicker"><span class="jv-kicker">Files touched // ${t.files.length}</span></h2>
            ${t.files.length ? html`<ul class="jv-tasks__files">${t.files.map((f) => html`<li><span class="jv-tasks__change" data-change="${f.change}">${CHANGE[f.change] || f.change}</span><span class="jv-tasks__path">${f.path}</span>${f.where ? html`<span class="jv-tasks__todo">${f.where}</span>` : ""}</li>`)}</ul>`
              : html`<p class="jv-muted">Nothing written yet.</p>`}</section>
        </div>
        <div class="jv-view__stack">
          <section class="jv-sheet" aria-labelledby="t-log"><h2 id="t-log" class="jv-view__kicker"><span class="jv-kicker">Transcript // ${t.transcript.length}</span></h2>
            <ol class="jv-tasks__log">${t.transcript.map((x) => html`<li data-who="${x.who}"><span class="jv-tasks__who">${WHO[x.who] || x.who}</span><time datetime="${x.at}">${clockTime(x.at)}</time><span class="jv-tasks__said">${x.text}</span></li>`)}</ol></section>
          ${t.brief ? html`<section class="jv-sheet" aria-labelledby="t-brief"><h2 id="t-brief" class="jv-view__kicker"><span class="jv-kicker">Brief</span></h2>
            <p class="jv-tasks__brief"><span class="jv-tasks__todo">Done when</span> ${t.brief.done_when}</p>
            ${t.brief.folders?.length || t.brief.apps?.length ? html`<p class="jv-tasks__brief"><span class="jv-tasks__todo">Only</span> ${[...(t.brief.apps || []), ...(t.brief.folders || [])].join(" · ")}</p>` : ""}</section>` : ""}
        </div>
      </div>
    </div>`;
  }
  rendered() { this.querySelectorAll("jv-approval-card").forEach((c) => Object.assign(c, { approval: this._asks?.[c.dataset.i], now: store.now() })); }
}
TasksView.define("jv-view-tasks");
router.register("/activity/tasks", "jv-view-tasks", "activity", "Claude tasks");

// ---- scenes: every state of a task, on the Stage and in Activity ----------------------------------------------
const D = "2026-11-16";
const taskWindow = (pushed = `${D}T15:37:12`) => ({ id: "w-task-stand", type: "agent_task", title: "Design a phone stand in Fusion", ref: "task-stand", size: "2x1", pushed, slot: "jarvis" });
const askWindow = { id: `w-${SAMPLE_ASK.id}`, type: "approval", title: "Waiting for your yes", ref: SAMPLE_ASK.id, size: "2x2", pushed: `${D}T15:39:40` };
const dueWindow = { id: "w-due-pps7", type: "countdown", title: "Due", ref: "due-pps7", size: "1x1", pushed: `${D}T15:36:21` };
/** A scene's state with the demo task in `st`; `asked` adds its permission ask (and `similar` asks of its kind). */
function withTask(s, st, { asked = false, similar = 1, stage = true } = {}) {
  withReach(s);
  const task = sampleTask(st);
  if (asked) { task.asks = [{ id: SAMPLE_ASK.id, kind: "create:fusion projects", answer: "waiting", similar }]; s.approvals = [{ ...SAMPLE_ASK }, ...s.approvals.filter((a) => a.id !== "ap-week")]; }
  else s.approvals = s.approvals.filter((a) => a.id !== "ap-week");
  s.tasks = [task, ...s.tasks];
  if (LIVE.has(st)) s.jobs = [{ id: task.id, label: `Claude: ${task.goal.length > 26 ? `${task.goal.slice(0, 25)}…` : task.goal}`, state: "running", progress: (task.step.n - 1) / task.step.of, detail: taskLine(task) }];
  if (stage) s.windows = [dueWindow, taskWindow(), ...(asked && st !== "parked" ? [askWindow] : [])];
  return task;
}
const speak = (s, text) => { s.orb = { state: "speaking", level: 0.6 }; s.caption = { text, source: { kind: "jarvis", label: "Jarvis" }, ttl_ms: 600000 }; };
registerScene("task-starting", { path: "/stage", about: "A Claude task has just started: the goal is the hero until there is something to see", patch: (s) => { withTask(s, "starting"); speak(s, "On it."); } });
registerScene("task-running", { path: "/stage", about: "A Claude task running on the Stage: CLAUDE // TASK, elapsed time, the app's view, the current step, cost under the frame", patch: (s) => { withTask(s, "running"); } });
registerScene("task-waiting", { path: "/stage", about: "Claude asks to save Stand v1.f3d: the code read-back, Allow · Deny, the task waits", patch: (s) => {
  withTask(s, "waiting", { asked: true }); s.orb = { state: "waiting", countdown_s: 7, window_s: 8 };
  s.caption = { text: SAMPLE_ASK.read_back, source: { kind: "jarvis", label: "Jarvis" }, ttl_ms: 600000 };
} });
registerScene("task-ask-again", { path: "/activity/tasks/task-stand", about: "The second similar ask in the same task: Allow for this task is offered", patch: (s) => { withTask(s, "waiting", { asked: true, similar: 2, stage: false }); } });
registerScene("task-parked", { path: "/stage", about: "He's away while it waits: the task is parked (not failed) and the ask stays under Your yes", patch: (s) => { withTask(s, "parked", { asked: true }); s.presence = { here: false }; } });
registerScene("task-done", { path: "/stage", about: "Finished: Stand v1.f3d saved, cost spent under the frame", patch: (s) => { withTask(s, "done"); } });
registerScene("task-stopped", { path: "/stage", about: "He said \"Stop that\": stopped, never failed", patch: (s) => { withTask(s, "stopped"); } });
registerScene("tasks", { path: "/activity/tasks", about: "Activity › Tasks: one running, one finished yesterday (with Undo)", patch: (s) => { withTask(s, "running", { stage: false }); } });
registerScene("tasks-empty", { path: "/activity/tasks", about: "Activity › Tasks with nothing yet", patch: (s) => { withReach(s); s.tasks = []; } });
registerScene("task-detail", { path: "/activity/tasks/task-stand", about: "A finished task opened: every step, the files it touched, the transcript and Undo", patch: (s) => { withTask(s, "done", { stage: false }); } });
registerScene("task-detail-waiting", { path: "/activity/tasks/task-stand", about: "A task opened while it waits for his yes: the ask on the same approval card (Allow · Deny)", patch: (s) => { withTask(s, "waiting", { asked: true, stage: false }); } });
registerScene("task-undone", { path: "/activity/tasks/task-stand", about: "After Undo: what it made is in the undo bin", patch: (s) => { withTask(s, "undone", { stage: false }); } });
