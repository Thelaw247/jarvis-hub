// The Stage (N9, HUD v2 §6.5): Jarvis's screen, like Huw's dedicated monitor. A second, borderless window
// (app.py makes it hidden at start, full screen on the chosen monitor) where the windows Jarvis pulls up while
// he talks assemble, so the hub's home page stays calm.
//  - Active: the window canvas as Huw's board (canvas.js collage, HUD v3 §14: at most five small glass panels
//    in a loose collage around the docked orb, the one Jarvis means on top, marks, focus brackets, dock into the
//    Rail), the orb docked bottom-right, the shell's bottom row (shared with the hub through the server), the
//    caption above it. No tabs: only three small, quiet words top-right under the ruler: HUB · TIDY · CLEAR VIEW.
//  - Standby: when the last window is put away the Stage fades back to the orb and the clock. On Laptop A
//    app.py hides the window instead (should_show_stage); in a browser it stays on standby.
//  - From standby, windows arrive with the dock beat: the big orb slides into the corner while they assemble.
//  - The 60 s window lifetime runs here (the screen that shows the windows owns their clock).
//  - Links inside a window ("Open it", a branch) open in the hub (focusHub), never on the Stage.
//  - Esc with focus in a window closes it (it docks into its Rail slot); focus goes to the next window.
//  - One window (v0.17.0, the default: "Where Jarvis shows things" = On the hub): this second window is then
//    only a holder for the windows he pulled out of the hub (core/popped.js). No orb, no voice, no bottom row,
//    no standby: just those windows, which he can move and size, and two words top-right (HUB · TIDY) plus
//    BACK TO THE HUB, which sends them all back. Empty, it says what it is for (app.py hides it then). Dragged
//    off its edge a window goes back to the hub. Nothing in it expires: he put it there.
// Route /stage (registered here; main.js pins the Stage window to it).
import { css, html } from "../../core/dom.js";
import { bridge } from "../../core/bridge.js";
import { orbView, stillAwake } from "../../core/orbview.js";
import { KEEP_WINDOWS, windowClock } from "../../core/presence.js";
import { router } from "../../core/router.js";
import { registerScene, sceneName } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { slideOrbToDock, WindowCanvas, handOffSpin } from "./canvas.js";
import { focusHub, holderMode, popIn, windowsFor } from "./desktop.js";
import { popped } from "../../core/popped.js";

css(import.meta.url);

const TICK_MS = 5000;

/** The order TIDY puts the windows back in: the order they came (pushed), so the newest leads again.
 *  → ids, or null when they are already in that order (pure; the tests call it). */
export function tidyOrder(windows) {
  const ids = windows.map((w) => w.id);
  const sorted = [...windows].map((w, i) => [w, i]).sort((a, b) => String(a[0].pushed || "").localeCompare(String(b[0].pushed || "")) || a[1] - b[1]).map(([w]) => w.id);
  return sorted.join("\n") === ids.join("\n") ? null : sorted;
}

class StageView extends HTMLElement {
  connectedCallback() {
    const root = document.documentElement;
    root.dataset.window = "stage";
    this.innerHTML = String(html`<section class="jv-stage" aria-label="Stage">
      <h1 class="jv-sr" tabindex="-1">Stage</h1>
      <div class="jv-stage__bar" data-keep-clear>
        <nav class="jv-stage__pills" aria-label="Stage">
          <button type="button" class="jv-stage__word" data-do="hub" aria-label="Show the hub">Hub</button>
          <button type="button" class="jv-stage__word jv-stage__tool" data-do="tidy" aria-label="Tidy: lay the windows out again">Tidy</button>
          <button type="button" class="jv-stage__word jv-stage__tool" data-do="clear" aria-label="Clear view: send everything to the Rail">Clear view</button>
        </nav>
      </div>
      <p class="jv-stage__empty" hidden>Nothing here. Drag a window off the edge of the hub, or use its own-window button, and it stays in this window.</p>
      <div class="jv-stage__standby">
        <div class="jv-stage__centre"><jv-orb size="centre" class="jv-stage__orb"></jv-orb><jv-clock live small class="jv-stage__clock"></jv-clock></div>
      </div>
      <div class="jv-stage__canvas" aria-label="Windows"></div>
    </section>`);
    this.section = this.querySelector(".jv-stage");
    this.standby = this.querySelector(".jv-stage__standby");
    this.canvas = new WindowCanvas(this, this.querySelector(".jv-stage__canvas"), { collage: true, redraw: () => this.draw(),
      only: (windows, s) => windowsFor(windows, { stageWindow: true, s }) });  // one window: only what he pulled out
    this.stopPopped = popped.subscribe(() => this.draw());
    this.addEventListener("click", (e) => {
      const what = e.target.closest("[data-do]")?.dataset.do;
      if (what === "hub") focusHub();
      else if (what === "tidy") {  // back to the order they came, laid out afresh
        const ids = tidyOrder(store.state.windows);
        if (ids) bridge.act("order", "windows", { ids });
        this.canvas.tidy();
      }
      else if (what === "clear") bridge.act("close_all", "all");  // CLEAR VIEW docks everything into the Rail
      else if (what === "back") popped.clear();  // the holder: everything goes back to the hub
    });
    // Esc on the Stage: close what's open. Focus inside a window → that window docks into its Rail slot (the
    // canvas hands focus to the next window); the router is pinned here, so there is no "back" to step to.
    this.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const win = e.target.closest?.(".jv-stage__canvas jv-window[window-id]");
      if (!win || e.target.closest("input, textarea, select, [contenteditable], details[open], form")) return;
      e.preventDefault();
      win.dispatchEvent(new CustomEvent("jv-act", { bubbles: true, detail: { action: "close", target: win.getAttribute("window-id") } }));
    });
    this.stop = store.watch(["windows", "orb", "presence", "approvals", "cards", "facts", "branches", "settings", "day", "rail", "marks", "focus", "threads", "now_card"], () => this.draw());
    // the window lifetime: the Stage shows the windows, so it keeps their 60 s clock (never in scenes, never hidden)
    if (!sceneName) this.ticker = setInterval(() => {
      if (document.hidden || holderMode() || KEEP_WINDOWS) return;  // what he pulled out stays; since v0.24.1 every window does
      const waiting = new Set(store.state.approvals.filter((a) => a.status === "pending").map((a) => a.id));
      windowClock.tick(store.state.windows.filter((w) => !(w.type === "approval" && waiting.has(w.ref))));
    }, TICK_MS);
    this.onShown = () => { if (!document.hidden && this._pendingArrive && this._mode === "active") this.arrive(); };
    document.addEventListener("visibilitychange", this.onShown);
    this.draw();
  }
  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this.onShown);
    this.stop?.(); this.stopPopped?.(); clearInterval(this.ticker); this.canvas?.stop(); this.endDocking?.();
    const root = document.documentElement;
    delete root.dataset.window; delete root.dataset.stage;
  }
  update() { this.draw(); }

  draw() {
    const s = store.state, root = document.documentElement, holder = holderMode(s);
    this.canvas.move = holder ? popIn : null;  // dragged off the holder's edge, a window goes back to the hub
    const n = this.canvas.draw(s);
    const mode = holder ? "holder" : n ? "active" : "standby", was = this._mode;
    this._mode = mode;
    if (root.dataset.stage !== mode) root.dataset.stage = mode;
    this.section.classList.toggle("jv-stage--standby", !n && !holder);
    this.section.classList.toggle("jv-stage--holder", holder);
    for (const b of this.querySelectorAll(".jv-stage__tool")) b.hidden = !n;
    this.querySelector('[data-do="clear"]').hidden = !n || holder;
    let back = this.querySelector('[data-do="back"]');  // only in the holder, and only with something to send back
    if (holder && n && !back) {
      back = Object.assign(document.createElement("button"), { type: "button", className: "jv-stage__word", textContent: "Back to the hub" });
      back.dataset.do = "back"; back.setAttribute("aria-label", "Move every window here back to the hub");
      this.querySelector(".jv-stage__pills").append(back);
    } else if (back && !(holder && n)) back.remove();
    this.querySelector(".jv-stage__empty").hidden = !holder || n > 0;
    if (holder) {  // no orb here at all: nothing to stand by, nothing to dock
      this.endDocking?.(); this._pendingArrive = false;
      this.section.classList.remove("jv-stage--arriving", "jv-stage--from-hub", "jv-stage--docking");
      const big = this.querySelector(".jv-stage__orb");
      if (!big.hasAttribute("data-offstage")) { big.setAttribute("data-offstage", ""); big.reconsider?.(); }
      return;
    }
    // standby: the orb in the centre (standby whenever it has nothing else to show) over the clock
    const orb = this.querySelector(".jv-stage__orb"), view = orbView(s);
    const awake = stillAwake(s.orb?.state || "idle", "stage", () => this.draw());  // rings stay out a moment after a turn
    const state = view.state === "idle" && !awake ? "standby" : view.state;
    if (view.alert) orb.setAttribute("alert", view.alert); else orb.removeAttribute("alert");
    if (orb.getAttribute("state") !== state) orb.setAttribute("state", state);
    orb.orb = s.orb;
    if (mode === "standby") { handOffSpin(document.getElementById("orb"), this.querySelector(".jv-stage__orb")); this.endDocking?.(); this._pendingArrive = false; this.section.classList.remove("jv-stage--arriving", "jv-stage--from-hub"); this._standbyBox = this.standby.getBoundingClientRect(); }
    else if (was === "standby") this.arrive();
    this.offstage();
  }

  /** Windows arrive: the orb sits where the hub's orb was, then slides to the corner while the windows come out
   *  of it. On Laptop A the Stage window is hidden until the push, so the beat waits until it is on screen
   *  (played while hidden, he only saw the orb vanish and the windows pop). */
  arrive() {
    this.endDocking?.(); this.endDocking = null;
    this.section.classList.add("jv-stage--arriving");
    if (document.hidden) {
      this._pendingArrive = true; this.section.classList.add("jv-stage--from-hub");
      // never leave the windows waiting on a visibility change that doesn't come (a browser or WebView that keeps
      // reporting hidden): after 600 ms they show as they are, without the beat
      clearTimeout(this._arriveT);
      this._arriveT = setTimeout(() => { if (!this._pendingArrive) return; this._pendingArrive = false;
        this.section.classList.remove("jv-stage--arriving", "jv-stage--from-hub"); this.offstage(); }, 600);
      return;
    }
    clearTimeout(this._arriveT);
    this._pendingArrive = false;
    requestAnimationFrame(() => {
      const land = () => { this.section.classList.remove("jv-stage--from-hub"); this.offstage(); };
      if (this._mode !== "active") { this.section.classList.remove("jv-stage--arriving"); land(); return; }
      const box = this.standby.getBoundingClientRect();
      this.endDocking = slideOrbToDock({ layer: this.standby, host: this.section, cls: "jv-stage--docking", box, windows: this.querySelector(".jv-stage__canvas"), onDone: land });
      this.section.classList.remove("jv-stage--arriving");
      if (!this.endDocking) land();
      this.offstage();
    });
  }

  /** With windows up (and the dock beat over) the centre orb is hidden: its motion and level loop stop. */
  offstage() {
    const orb = this.querySelector(".jv-stage__orb");
    const off = this._mode === "active" && !this.section.matches(".jv-stage--docking, .jv-stage--arriving");
    if (orb && orb.hasAttribute("data-offstage") !== off) { orb.toggleAttribute("data-offstage", off); orb.reconsider?.(); }
  }
}
if (!customElements.get("jv-view-stage")) customElements.define("jv-view-stage", StageView);
router.register("/stage", "jv-view-stage", "stage", "Stage");

// ---- scenes ----
const D = "2026-11-16";
export const STAGE_WINDOWS = {
  next: { id: "w-next", type: "next_up", title: "Next", size: "1x1", pushed: `${D}T15:40:20` },
  due: { id: "w-due-pps7", type: "countdown", title: "Due", ref: "due-pps7", size: "1x1", pushed: `${D}T15:40:21` },
  file: { id: "w-pps7", type: "file", title: "PPS 7", ref: "file-pps7", size: "2x2", pushed: `${D}T15:40:40` },
  branch: { id: "w-ge122", type: "branch_card", title: "GE 122", ref: "ge-122", size: "1x2", pushed: `${D}T15:41:00` },
  approval: { id: "w-ap-week", type: "approval", title: "Waiting for your yes", ref: "ap-week", size: "2x2", pushed: `${D}T15:41:30` },
  fact: { id: "w-fact-late", type: "fact", title: "GE 122", ref: "f-ge-late", size: "2x1", pushed: `${D}T15:41:10`, data: { heading: "Late penalty: 10% a day" } },
  notice: { id: "w-lab4-room", type: "notice", title: "CHEM 142 · Lab 4", size: "2x1", pushed: `${D}T15:41:20`, data: { kind: "info", heading: "Room change", text: "CHEM 142 lab 4 moved to Thorvaldson 173 this week." } },
  chart: { id: "w-chart", type: "chart", title: "Calendar · This week", size: "2x1", pinned: true, pushed: `${D}T15:39:50`, data: { heading: "Study hours planned", unit: "h", tone: "growth", data: [{ label: "Mon", value: 2.5 }, { label: "Tue", value: 3 }, { label: "Wed", value: 1.5 }, { label: "Thu", value: 2 }, { label: "Fri", value: 1 }] } },
};
const W = STAGE_WINDOWS;
const speaking = (s, text, source = { kind: "canvas", label: "Canvas" }) => { s.orb = { state: "speaking", level: 0.6 }; s.caption = { text, source, ttl_ms: 600000 }; };
registerScene("stage-active", { path: "/stage", about: "The Stage while Jarvis talks: four windows, the orb docked, the Rail below", patch: (s) => {
  s.windows = [W.next, W.due, W.file, W.branch]; s.approvals = [];
  speaking(s, "On track. PPS 7 is half done and due Wednesday at 8.");
} });
registerScene("stage-waiting", { path: "/stage", about: "The Stage with a question waiting for his yes", patch: (s) => { s.windows = [W.due, W.approval]; s.orb = { state: "waiting", countdown_s: 7, window_s: 10 }; } });
registerScene("stage-crowded", { path: "/stage", about: "Six windows from an older hub: the oldest unpinned one docks (a pure view just closes)", patch: (s) => { s.windows = [W.next, W.due, W.chart, W.file, W.branch, W.approval]; } });
registerScene("stage-board", { path: "/stage", about: "Huw's board: five windows of every kind (a page, a chart, a countdown, a fact, a note) in the glass collage", patch: (s) => {
  s.windows = [W.chart, W.due, W.file, W.fact, W.notice]; s.approvals = [];
  speaking(s, "Here's the week: PPS 7 first, then the lab.");
} });
// his v0.4.1 report: the Homework icon opened over a crowded Stage. The fan sits above every window, which dim a step.
registerScene("stage-rail-open", { path: "/stage", about: "The Homework icon opened over a crowded Stage: the fan is on top, the windows dim a step", patch: (s) => {
  s.windows = [W.branch, W.due]; s.approvals = [];
  s.focus = { ref: "due-pps7", until: `${D}T15:40:44` };
  speaking(s, "Two due this week, the nearest Wednesday at 8.");
  s.ui = { ...(s.ui || {}), railOpen: "homework" };
} });
// one window (the default): this window only holds what he pulled out of the hub
const held = (s, ...ids) => { s.settings = { ...s.settings, stage: "hub" }; s.approvals = []; popped.pretend(ids); };
registerScene("stage-holder", { path: "/stage", about: "One window: the holder with two windows he pulled out of the hub. No orb, no voice, no bottom row", patch: (s) => { s.windows = [W.next, W.due, W.file, W.branch]; held(s, W.file.id, W.due.id); } });
registerScene("stage-holder-live", { path: "/stage", about: "One window: the holder reading what is really pulled out (tests: two pages share it)", patch: (s) => { s.windows = [W.next, W.due, W.file, W.branch]; s.settings = { ...s.settings, stage: "hub" }; s.approvals = []; } });
registerScene("stage-holder-empty", { path: "/stage", about: "One window: the holder with nothing in it says what it is for (the desktop app hides it)", patch: (s) => { s.windows = [W.next, W.due]; held(s); } });
registerScene("stage-empty", { path: "/stage", about: "Nothing up: standby, the orb and the clock (Laptop A hides the window instead)", patch: (s) => { s.windows = []; s.approvals = []; s.caption = null; } });
registerScene("stage-focus", { path: "/stage", about: "Jarvis names PPS 7 as he speaks: brackets snap onto its window and its Rail slot", patch: (s) => {
  s.windows = [W.next, W.due, W.file, W.branch]; s.approvals = [];
  s.focus = { ref: "due-pps7", until: `${D}T15:40:44` };
  speaking(s, "Two due this week, the nearest Wednesday at 8.");
} });
