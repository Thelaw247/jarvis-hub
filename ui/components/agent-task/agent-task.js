// <jv-agent-task task-id="task-stand">: a running Claude agent session as a Stage window's content (REACH §5.4),
// in the one clean anatomy (HUD v2 §14.2):
//   kicker   CLAUDE // TASK, the elapsed time on the right            (the window's kicker, via registerWindowKind)
//   hero     the app's view (a thumb, sat in: static dark tint) when there is one, else the goal as a title
//   line     one supporting line: the current step ("Extruding base · 4 of 7"), or what it waits on / how it ended
//   footer   cost so far, outside the frame                            (the window's meta)
// No buttons at rest: Stop (while it runs) and Open show on hover or keyboard focus only. Open (also the panel
// itself, data-key="open") goes to Activity › Tasks › this task: the full step list, the files touched and Undo.
// It reads the task from the store itself (contracts/agent_task, state.tasks), so steps advance without the window
// being rebuilt. Emits jv-act stop and jv-nav; never calls the backend itself.
import { asDate, css, html, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { glance } from "../glance/glance.js";
import { registerWindowKind } from "../../core/window-kinds.js";

css(import.meta.url);

export const LIVE = new Set(["running", "waiting", "parked"]);
/** A task state as a glance code (HUD v2 §5): shape + colour + word, never colour alone. */
export const TASK_GLANCE = {
  running: ["jarvis", "Working"], waiting: ["yes", "Your yes"], parked: ["parked", "Parked"], done: ["done", "Done"],
  stopped: ["parked", "Stopped"], failed: ["critical", "Didn't finish"], undone: ["parked", "Undone"],
};
const usd = (n) => `$${(Number(n) || 0).toFixed(2)}`;

/** "0:42", "4:05", "1:02:10": how long it has run (or ran). */
export function elapsed(task, now = store.now()) {
  const end = task.ended ? asDate(task.ended) : asDate(now);
  const s = Math.max(0, Math.round((end - asDate(task.started)) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

/** The one supporting line (≤ ~90 characters). */
export function taskLine(task) {
  const step = task.step || {};
  const ask = (task.asks || []).find((a) => a.answer === "waiting");
  const what = ask ? store.state.approvals.find((x) => x.id === ask.id)?.title?.replace(/^Claude: /, "") : "";
  switch (task.state) {
    case "running": return step.label ? `${step.label} · ${step.n} of ${step.of}` : "Starting";
    case "waiting": return what ? `Asks to ${what}` : "Asks for your yes";
    case "parked": return what ? `Waits for you: ${what}` : "Waits for your answer";
    case "done": return step.label || "Finished";
    case "undone": return "Undone: what it made is in the undo bin";
    default: return task.why || (task.state === "stopped" ? "Stopped" : "Didn't finish");
  }
}

/** The window's kicker and footer (HUD v2 §14.2): CLAUDE // TASK, elapsed time right, cost outside the frame. */
export function taskKicker(win, s) {
  const task = (s.tasks || []).find((t) => t.id === win.ref);
  if (!task) return { heading: "Claude", status: "Task", index: "", meta: "" };
  const live = LIVE.has(task.state);
  return { heading: "Claude", status: "Task", index: elapsed(task), meta: `${usd(task.cost_usd)} ${live ? "so far" : "spent"}` };
}

class AgentTask extends Jv {
  static attrs = ["task-id"];
  setup() { this.stop = store.subscribe((_s, keys) => { if (keys.has("tasks") || keys.has("approvals")) this.update(); }); }
  teardown() { this.stop?.(); }
  render() {
    const task = (store.state.tasks || []).find((t) => t.id === this.getAttribute("task-id"));
    if (!task) return html`<p class="jv-muted">That task isn't here any more.</p>`;
    const [code, word] = TASK_GLANCE[task.state] || TASK_GLANCE.failed;
    const live = LIVE.has(task.state);
    const mark = code === "yes" || code === "parked" || code === "critical" ? glance(code, { size: "inline", word, bare: true }) : "";
    const hero = task.thumb
      ? html`<figure class="jv-agent-task__view"><img src="${task.thumb.src}" alt="${task.thumb.alt}" loading="lazy" decoding="async"></figure>`
      : html`<h3 class="jv-agent-task__goal">${task.goal}</h3>`;
    return html`<article class="jv-agent-task" data-state="${task.state}" aria-label="Claude task: ${task.goal}. ${word}.">
      ${hero}
      <p class="jv-agent-task__line">${mark || html`<span class="jv-sr">${word}: </span>`}${taskLine(task)}</p>
      <p class="jv-agent-task__tools">
        ${live ? html`<button type="button" class="jv-btn jv-btn--small" data-act="stop" data-target="${task.id}" data-key="stop">Stop<span class="jv-sr"> the task: ${task.goal}</span></button>` : ""}
        <button type="button" class="jv-btn jv-btn--small" data-nav="/activity/tasks/${task.id}" data-key="open">Open<span class="jv-sr">: the steps, files and undo for ${task.goal}</span></button>
      </p>
    </article>`;
  }
}
AgentTask.define("jv-agent-task");

registerWindowKind("agent_task", {
  content: (win) => el("jv-agent-task", {}, { "task-id": win.ref }),
  kicker: taskKicker,
});

// ---- gallery: the window in every state, in its glass frame ----------------------------------------------------
const D = "2026-11-16";
export const SAMPLE_TASK = {
  id: "task-stand", goal: "Design a phone stand in Fusion", app: "Fusion", state: "running", started: `${D}T15:37:10`,
  step: { n: 4, of: 7, label: "Extruding base" },
  steps: ["Reading the brief", "Opening Fusion", "Sketching the base", "Extruding base", "Adding the back rest", "Rounding the edges", "Saving Stand v1.f3d"]
    .map((label, i) => ({ n: i + 1, label, state: i < 3 ? "done" : i === 3 ? "now" : "todo" })),
  files: [], cost_usd: 0.15, cap_usd: 1, asks: [], allowed: [], undo: null,
  thumb: { src: "/components/agent-task/demo/task-stand.webp", kind: "design", alt: "Fusion view: the phone stand, base and back rest" },
  transcript: [{ at: `${D}T15:37:10`, who: "you", text: "Design a phone stand in Fusion." }],
  brief: { folders: ["Jarvis Workspace"], apps: ["Fusion"], done_when: "Stand v1.f3d is saved in Fusion Projects" },
};
const ASK = { id: "ap-task-stand-1", title: "Claude: create Stand v1.f3d", status: "pending", asked: `${D}T15:39:40`, category: "agent", reversible: true,
  consequences: ["Creates 'Stand v1.f3d' in Fusion Projects", "Only for this task: Design a phone stand in Fusion", "Undo from the task puts it back"],
  read_back: "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?", sources: [{ kind: "jarvis", label: "Claude task · Design a phone stand in Fusion" }] };
/** The sample task in one state (also used by the scenes in views/reach). */
export function sampleTask(state) {
  const t = structuredClone(SAMPLE_TASK);
  const all = (st) => t.steps.forEach((s) => { s.state = st; });
  if (state === "starting") { Object.assign(t, { step: { n: 2, of: 7, label: "Opening Fusion" }, cost_usd: 0.04 }); delete t.thumb; t.steps.forEach((s, i) => { s.state = i < 1 ? "done" : i === 1 ? "now" : "todo"; }); }
  if (["waiting", "parked", "done", "undone", "stopped"].includes(state)) {
    t.step = { n: 7, of: 7, label: "Saving Stand v1.f3d" }; t.cost_usd = 0.31;
    t.steps.forEach((s, i) => { s.state = i < 6 ? "done" : "now"; });
    t.asks = [{ id: ASK.id, kind: "create:fusion projects", answer: "waiting", similar: 1 }];
    t.state = state;
  }
  if (state === "done" || state === "undone") {
    all("done"); Object.assign(t, { ended: `${D}T15:40:02`, cost_usd: 0.35, step: { n: 7, of: 7, label: "Saved Stand v1.f3d" } });
    t.asks[0].answer = "allowed";
    t.files = [{ path: "Fusion Projects\\Jarvis\\Stand v1.f3d", change: "created", where: "Fusion" }];
    t.undo = { until: `${D}T21:40:02`, label: "24 h" };
    t.transcript.push({ at: `${D}T15:39:58`, who: "you", text: "Allow." }, { at: `${D}T15:40:02`, who: "claude", text: "Saved Stand v1.f3d in Fusion Projects › Jarvis." });
  }
  if (state === "undone") { t.undo = null; t.files.push({ path: "Fusion Projects\\Jarvis\\Stand v1.f3d", change: "deleted", where: "undo bin, 30 days" }); }
  if (state === "stopped") { t.steps.forEach((s) => { if (s.state !== "done") s.state = "skipped"; }); Object.assign(t, { ended: `${D}T15:39:50`, why: "You stopped it." }); t.asks[0].answer = "denied"; }
  return t;
}
export const SAMPLE_ASK = ASK;

const framed = (state, s) => () => {
  const task = { ...sampleTask(state), id: `task-g-${state}` };  // one id per state: every copy reads the store
  store.state.tasks = [task, ...(store.state.tasks || []).filter((t) => t.id !== task.id)];
  const win = el("jv-window", {}, { heading: "Claude", status: "Task", index: elapsed(task, asDate(s?.now || `${D}T15:40:00`)), meta: `${usd(task.cost_usd)} ${LIVE.has(task.state) ? "so far" : "spent"}` });
  const body = el("jv-agent-task", {}, { "task-id": task.id });
  win.append(body);
  return win;
};
registerGallery("agent-task", ["starting", "running", "waiting", "parked", "done", "stopped", "undone"].map((st) => ({
  label: st, build: (s) => { s.approvals = [ASK, ...s.approvals]; store.state.approvals = s.approvals; return framed(st, s)(); },
})), { about: "A Claude agent task on the Stage: CLAUDE // TASK, the elapsed time, one hero (the goal, or the app's view once there is one), the current step, cost under the frame. Stop and Open only on hover or focus.", columns: "420px" });
