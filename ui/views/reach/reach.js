// Controls › Reach, "What Jarvis can do" (REACH §5.3): every tool on the six rungs of the reach ladder (§1) with
// what it can read and write, its status (connected · needs sign-in · paused in game mode · off), when it was last
// used and an on/off switch; the allowed folders (editable); app scopes; standing permissions (revocable); and the
// cost caps for Claude agent tasks. Route /controls/reach (registered here). Data: state.reach (contracts/reach)
// and settings.standing_permissions. Changes go out as actions (set reach:tool:<id> · reach:folders · reach:caps,
// revoke) and come back as reach.updated / settings.updated: nothing here changes the store itself.
import { addSceneAct } from "../../core/bridge.js";
import { css, html, Jv, whenWords } from "../../core/dom.js";
import { router } from "../../core/router.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import "./tasks.js";
import { sceneReach } from "./scene-act.js";

css(import.meta.url);

/** The reach ladder (REACH §1): the most direct route wins. */
export const RUNGS = [
  { n: 1, name: "Your data", route: "Already polled: the now card and branch cards", speed: "Instant" },
  { n: 2, name: "App APIs", route: "Through Composio: reads free, writes after your yes", speed: "About 1 s" },
  { n: 3, name: "Local tools", route: "Files and apps on your laptops, inside the allowed folders", speed: "Under 0.3 s" },
  { n: 4, name: "App automation", route: "An app's own API through its add-in (MCP)", speed: "Seconds" },
  { n: 5, name: "Claude agents", route: "Bigger jobs, each write asked through Jarvis", speed: "Minutes" },
  { n: 6, name: "Computer use", route: "Screenshots and clicks on Laptop A, last resort, only when you ask", speed: "Slow" },
];
const STATUS = {
  connected: ["on", "Connected"], needs_sign_in: ["warn", "Needs sign-in"], paused: ["paused", "Paused in game mode"], off: ["off", "Off"],
};
const usd = (n) => `$${(Number(n) || 0).toFixed(2).replace(/\.00$/, "")}`;

/** A tool's status as he should read it now: Laptop A's tools pause while game mode is on (C37). */
export function toolStatus(tool, s = store.state) {
  if (!tool.on) return tool.status === "needs_sign_in" ? "needs_sign_in" : "off";
  const game = s.settings?.game_mode === "on" || s.now_card?.moment === "game";
  if (game && tool.where === "Laptop A" && tool.status === "connected") return "paused";
  return tool.status;
}

const mark = (kind, word) => html`<span class="jv-reach__status" data-status="${kind}"><span class="jv-reach__mark" aria-hidden="true"></span>${word}</span>`;

class ReachView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.stop = store.subscribe((_s, keys) => { if (keys.has("reach") || keys.has("settings") || keys.has("now_card")) this.update(); });
    this.addEventListener("submit", (e) => this.submit(e));
  }
  teardown() { this.stop?.(); }

  /** The two forms (add a folder, the caps) become actions; the hub checks them and answers with reach.updated. */
  submit(e) {
    e.preventDefault();
    const form = e.target, reach = store.state.reach;
    if (!reach) return;
    if (form.dataset.form === "folder") {
      const path = form.elements.path.value.trim();
      if (!path) { form.elements.path.focus(); return; }
      this.emit("jv-act", { action: "set", target: "reach:folders", args: { value: [...reach.folders, path] } });
      form.reset();
    } else if (form.dataset.form === "caps") {
      const task = Number(form.elements.task.value), day = Number(form.elements.day.value);
      this.emit("jv-act", { action: "set", target: "reach:caps", args: { task_usd: task, day_usd: day } });
    }
  }

  render() {
    const s = store.state, reach = s.reach, perms = s.settings?.standing_permissions || [];
    const head = html`<header class="jv-view__head"><nav class="jv-crumbs" aria-label="Breadcrumb"><a href="#/controls" data-nav="/controls" data-key="crumb">Controls</a><span aria-hidden="true">›</span><span aria-current="page">What Jarvis can do</span></nav>
      <h1 tabindex="-1">What Jarvis can do</h1><p class="jv-view__sub">Reading is free. Every write still waits for your yes, with a read-back and an undo. The most direct route wins.</p></header>`;
    if (!reach) return html`<div class="jv-view">${head}<jv-notice kind="empty" heading="Not known yet" text="When Jarvis can reach your apps and files, every tool shows up here with an on/off switch."></jv-notice></div>`;
    const now = store.now();
    const tool = (t) => {
      const st = toolStatus(t, s), [kind, word] = STATUS[st] || STATUS.off;
      const used = t.last_used ? `Used ${whenWords(t.last_used, now)}` : "Never used";
      return html`<li class="jv-reach__tool" data-tool="${t.id}">
        <div class="jv-reach__what"><span class="jv-reach__name"><b>${t.name}</b>${t.where ? html`<span class="jv-reach__where">${t.where}</span>` : ""}</span>
          <span><span class="jv-reach__k">Reads</span> ${t.reads}</span><span><span class="jv-reach__k">Writes</span> ${t.writes}</span></div>
        <div class="jv-reach__state">${mark(kind, word)}<span class="jv-reach__used">${used}</span></div>
        <button type="button" class="jv-switch" role="switch" aria-checked="${!!t.on}" aria-label="${t.name}" data-act="set" data-target="reach:tool:${t.id}" data-args='${JSON.stringify({ value: !t.on })}' data-key="tool-${t.id}" ${st === "needs_sign_in" && !t.on ? html`aria-describedby="signin-${t.id}"` : ""}>${t.on ? "On" : "Off"}</button>
        ${st === "needs_sign_in" && !t.on ? html`<span class="jv-sr" id="signin-${t.id}">Sign in to ${t.name} first.</span>` : ""}
      </li>`;
    };
    const rung = (r) => {
      const tools = reach.tools.filter((t) => t.rung === r.n);
      return html`<section class="jv-reach__rung" aria-labelledby="rung-${r.n}">
        <h3 id="rung-${r.n}" class="jv-reach__rung-head"><span class="jv-kicker">Rung ${r.n} // ${r.name}</span><span class="jv-kicker jv-kicker--end jv-reach__speed">${r.speed}</span></h3>
        <p class="jv-reach__route">${r.route}</p>
        ${tools.length ? html`<ul class="jv-reach__tools">${tools.map(tool)}</ul>` : html`<p class="jv-muted">Nothing on this rung yet.</p>`}
      </section>`;
    };
    const caps = reach.caps;
    return html`<div class="jv-view jv-reach">${head}
      <div class="jv-view__cols jv-reach__cols">
        <section class="jv-sheet jv-reach__ladder" aria-labelledby="r-ladder"><h2 id="r-ladder" class="jv-view__kicker"><span class="jv-kicker">Reach // Ladder</span><span class="jv-kicker jv-kicker--end">${reach.tools.filter((t) => toolStatus(t, s) === "connected").length} of ${reach.tools.length} ready</span></h2>
          ${RUNGS.map(rung)}
        </section>
        <div class="jv-view__stack">
          <section class="jv-sheet" aria-labelledby="r-folders"><h2 id="r-folders" class="jv-view__kicker"><span class="jv-kicker">Allowed folders // ${reach.folders.length}</span></h2>
            <p class="jv-reach__note">Local tools and Claude work only inside these. System folders, AppData and passwords are never reachable.</p>
            <ul class="jv-reach__list">${reach.folders.map((f, i) => html`<li><span class="jv-reach__path">${f}</span>
              <button type="button" class="jv-btn jv-btn--small" data-act="set" data-target="reach:folders" data-args='${JSON.stringify({ value: reach.folders.filter((_, j) => j !== i) })}' data-key="rm-${i}">Remove<span class="jv-sr">: ${f}</span></button></li>`)}</ul>
            <form class="jv-reach__add" data-form="folder"><label class="jv-sr" for="reach-add">Add a folder</label>
              <input id="reach-add" name="path" type="text" autocomplete="off" spellcheck="false" placeholder="Add a folder, e.g. OneDrive\\Projects" data-key="add-input" maxlength="260">
              <button class="jv-btn jv-btn--small" data-key="add">Add</button></form>
          </section>
          <section class="jv-sheet" aria-labelledby="r-apps"><h2 id="r-apps" class="jv-view__kicker"><span class="jv-kicker">App scopes // ${reach.apps.length}</span></h2>
            <ul class="jv-reach__list">${reach.apps.map((a) => html`<li data-app="${a.id}"><span class="jv-reach__what"><b>${a.name}</b><span>${a.scope}</span></span>
              ${mark(a.status === "set_up" ? "on" : "off", a.status === "set_up" ? "Set up" : "Not set up")}</li>`)}</ul>
          </section>
          <section class="jv-sheet" aria-labelledby="r-perms"><h2 id="r-perms" class="jv-view__kicker"><span class="jv-kicker">Standing permissions // ${perms.length}</span></h2>
            ${perms.length ? html`<ul class="jv-reach__list">${perms.map((p) => html`<li><span class="jv-reach__what"><span>${p.text}</span><span class="jv-reach__used">Since ${p.granted}</span></span>
              <button type="button" class="jv-btn jv-btn--small" data-act="revoke" data-target="${p.id}" data-key="revoke-${p.id}">Revoke<span class="jv-sr">: ${p.text}</span></button></li>`)}</ul>`
              : html`<p class="jv-reach__note">None. Jarvis asks every time. Say "you can always make folders in Class Content" to add one.</p>`}
          </section>
          <section class="jv-sheet" aria-labelledby="r-caps"><h2 id="r-caps" class="jv-view__kicker"><span class="jv-kicker">Caps // Claude tasks</span><span class="jv-kicker jv-kicker--end">${usd(caps.spent_today_usd)} of ${usd(caps.day_usd)} today</span></h2>
            <form class="jv-reach__caps" data-form="caps">
              <label><span>Per task</span><span class="jv-reach__money">$<input name="task" type="number" inputmode="decimal" min="0.1" max="50" step="0.01" value="${caps.task_usd}" data-key="cap-task"></span></label>
              <label><span>Per day</span><span class="jv-reach__money">$<input name="day" type="number" inputmode="decimal" min="0.1" max="200" step="0.01" value="${caps.day_usd}" data-key="cap-day"></span></label>
              <button class="jv-btn jv-btn--small" data-key="cap-save">Save caps</button></form>
            <p class="jv-reach__note">A task stops when its next step would pass a cap, and says why. At most two run at once.</p>
          </section>
        </div>
      </div>
    </div>`;
  }
}
ReachView.define("jv-view-reach");
router.register("/controls/reach", "jv-view-reach", "controls", "What Jarvis can do");
addSceneAct(sceneReach);

// ---- scenes (the demo reach is contracts/examples/reach.json; scene mode reads it once) ----------------------------
export const EXAMPLES = sceneNameOrNull() ? await loadExamples() : null;
function sceneNameOrNull() { return new URLSearchParams(location.search).get("scene"); }
async function loadExamples() {
  const get = (name) => fetch(`/contracts/examples/${name}.json`, { cache: "no-store" }).then((r) => r.json());
  const [reach, task] = await Promise.all([get("reach"), get("agent_task")]);
  return { reach, task };
}
/** Put the demo reach, the finished task and the email catches (Rail › Messages) into a scene's state. */
export function withReach(s) {
  if (!EXAMPLES) return s;
  s.reach = structuredClone(EXAMPLES.reach);
  s.tasks = [structuredClone(EXAMPLES.task)];
  const items = s.rail.slots.messages.items;
  for (const c of s.reach.catches.slice().reverse()) {
    if (!items.some((i) => i.ref === `mail-${c.id}`)) items.unshift({ ref: `mail-${c.id}`, slot: "messages", kind: "message", title: c.line, at: c.at, detail: `${c.from} · ${c.source.label.split(" · ")[0]}` });
  }
  return s;
}
registerScene("reach", { path: "/controls/reach", about: "What Jarvis can do: the six rungs with every tool, allowed folders, app scopes, standing permissions and the caps", patch: withReach });
registerScene("reach-game", { path: "/controls/reach", about: "Game mode on: Laptop A's tools say Paused in game mode", patch: (s) => { withReach(s); s.settings.game_mode = "on"; } });
registerScene("reach-empty", { path: "/controls/reach", about: "Before the hub knows its reach: one plain card", patch: (s) => { s.reach = null; } });
registerScene("reach-strict", { path: "/controls/reach", about: "No standing permissions, Gmail off, two folders, a $0.50 task cap", patch: (s) => {
  withReach(s); s.settings.standing_permissions = [];
  s.reach.tools.find((t) => t.id === "gmail").on = false; s.reach.tools.find((t) => t.id === "gmail").status = "off";
  s.reach.folders = ["OneDrive\\Class Content", "Jarvis Workspace"]; s.reach.caps = { task_usd: 0.5, day_usd: 2, spent_today_usd: 0.35 };
} });
registerScene("messages-catches", { path: "/now", about: "The Messages icon opened: the emails Jarvis flagged, one line each with the reason (reading only, no reply)", patch: (s) => {
  withReach(s); s.approvals = []; s.ui = { ...(s.ui || {}), railOpen: "messages" };
} });
