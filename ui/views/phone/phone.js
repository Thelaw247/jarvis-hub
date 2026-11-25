// Phone layout (V08, N8): the same views, arranged for a narrow screen (390 px, down to 320) and thumbs, in the
// Night look. Tabs sit at the bottom with the orb at their right end (read through `orbView()` by the shell,
// so it shows Standby and the critical alert); the Rail is a 44 px row just above the tabs (gauges, counts and
// worst shapes; its words when there is room); the caption takes its own row above the Rail. Now stacks
// everything full-width: what waits for a yes, the now card, pushed windows (glance + thumbnail), quick
// controls. Life opens as the outline. The reader opens full-screen with the resume card at the bottom.
// This file adds the quick-controls panel, keeps toasts clear of the Rail and the tabs, and registers the
// phone scenes; the layout rules are in phone.css and each view's own :root[data-size="phone"] rules.
import { SAMPLE_MARKS } from "../../components/rail/rail.js";
import { css, html, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

class QuickControls extends Jv {
  setup() { this.stop = store.subscribe((_s, keys) => { if (keys.has("settings") || keys.has("orb")) this.update(); }); }
  teardown() { this.stop?.(); }
  render() {
    const c = store.state.settings, muted = c.muted || store.state.orb.state === "muted";
    const dial = [["quiet", "Quiet"], ["balanced", "Balanced"], ["chatty", "Chatty"]];
    return html`<div class="jv-quick" role="group" aria-label="Quick controls">
      <button type="button" class="jv-switch" role="switch" aria-checked="${!muted}" aria-label="Microphone" data-act="${muted ? "unmute" : "mute"}" data-target="mic" data-key="mic">${muted ? "Mic off" : "Mic on"}</button>
      <button type="button" class="jv-switch" role="switch" aria-checked="${!!c.focus}" aria-label="Focus mode" data-act="set" data-target="focus" data-args='${JSON.stringify({ value: !c.focus })}' data-key="focus">${c.focus ? "Focus on" : "Focus off"}</button>
      <span class="jv-seg" role="radiogroup" aria-label="How chatty">${dial.map(([v, label]) => html`<button type="button" role="radio" aria-checked="${c.interruption === v}" data-act="set" data-target="interruption" data-args='${JSON.stringify({ value: v })}' data-key="dial-${v}">${label}</button>`)}</span>
    </div>`;
  }
}
QuickControls.define("jv-quick-controls");

// ---- toasts: just above the bottom band (caption row + Rail row + tabs), whatever its height right now ----
// The band grows when a caption shows, so a fixed offset would land on it; `--phone-above-band` follows it.
const root = document.documentElement;
function placeToasts() {
  const foot = document.getElementById("foot");
  if (!foot || root.dataset.size !== "phone") return;
  const top = Math.min(foot.getBoundingClientRect().top, document.getElementById("chrome")?.getBoundingClientRect().top ?? Infinity);
  const above = `${Math.max(0, Math.round(innerHeight - top)) + 8}px`;
  if (root.style.getPropertyValue("--phone-above-band") !== above) root.style.setProperty("--phone-above-band", above);
}
function watchBand() {
  const foot = document.getElementById("foot"), chrome = document.getElementById("chrome");
  if (!foot || typeof ResizeObserver === "undefined") return;
  const seen = new ResizeObserver(placeToasts);
  seen.observe(foot);
  if (chrome) seen.observe(chrome);
  addEventListener("resize", placeToasts);
  new MutationObserver(placeToasts).observe(root, { attributes: true, attributeFilter: ["data-size"] });
  placeToasts();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watchBand, { once: true }); else watchBand();

// ---- scenes (the demo day at 3:40 pm Monday, at 390 × 844; add &size=phone at 320 wide to check the narrowest) ----
const D = "2026-11-16";
const W = {
  due: { id: "w-due-pps7", type: "countdown", title: "Due", ref: "due-pps7", size: "1x1", pushed: `${D}T15:40:21` },
  file: { id: "w-pps7", type: "file", title: "PPS 7", ref: "file-pps7", size: "2x2", pushed: `${D}T15:40:40` },
};
const SAID = { text: "PPS 7 is half done and due Wednesday at 8.", source: { kind: "canvas", label: "Canvas" }, ttl_ms: 600000 };
registerScene("phone-now", { path: "/now", size: "phone", about: "Phone: what waits for a yes, the now card, pushed windows stacked full-width with glance and thumbnail, quick controls; the Rail row above the tabs",
  patch: (s) => { s.windows = [W.due, W.file]; } });
registerScene("phone-said", { path: "/now", size: "phone", about: "Phone: a spoken line in its own row above the Rail and a toast clear of both",
  patch: (s) => { s.windows = [W.due, W.file]; s.approvals = []; s.caption = SAID; s.toasts = [{ id: "t-sync", kind: "success", text: "Canvas is up to date." }]; } });
registerScene("phone-rail-open", { path: "/now", size: "phone", about: "Phone: the Homework slot opened from the Rail row, its things above it",
  patch: (s) => { s.windows = [W.file]; s.approvals = []; s.marks = { ...s.marks, ...structuredClone(SAMPLE_MARKS) }; s.ui = { ...(s.ui || {}), railOpen: "homework" }; } });
registerScene("phone-critical", { path: "/now", size: "phone", about: "Phone: something overdue: the orb in the tab bar turns critical and the Rail row shows the triangle",
  patch: (s) => {
    s.windows = [W.due]; s.approvals = [];
    const pps = s.rail.slots.homework.items.find((i) => i.ref === "due-pps7");
    Object.assign(pps, { state: "critical", detail: "Overdue since Wed 8 pm" });
    s.rail.slots.homework.worst = "critical";
  } });
registerScene("phone-standby", { path: "/now", size: "phone", about: "Phone while nobody is at the hub: the orb says Standby", patch: (s) => { s.approvals = []; s.presence = { here: false, others: false }; } });
registerScene("phone-reader", { path: "/read/th-pps7", size: "phone", about: "Phone: PPS 7 opens at Q7 with the resume card at the bottom, within thumb reach" });
registerScene("phone-life", { path: "/life", size: "phone", about: "Phone: Life as the outline" });
registerScene("phone-branch", { path: "/life/ge-122", size: "phone", about: "Phone: a branch as a full-screen card" });
registerScene("phone-activity", { path: "/activity", size: "phone", about: "Phone: approvals first" });
registerScene("phone-controls", { path: "/controls", size: "phone", about: "Phone: controls in one column" });
