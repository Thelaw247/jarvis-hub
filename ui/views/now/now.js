// The Now view (V01): the hub's home page (HUD v3 §14: as empty and calm as Huw's).
//  - The calm home (the default, Controls › Look › "Where Jarvis shows things" = Stage window): the centre drawn
//    by ./ambient.js: awake, the orb alone on the grid; resting, the small standby sphere with a small clock and
//    a tiny date under it. The shell adds the icon row (the Rail) with the page dots, the caption above it while
//    Jarvis speaks, and the status word bottom-left. Nothing pops up on it: the windows Jarvis pulls up go to the
//    Stage (a separate window, ui/views/stage/), and while any are up the icon row shows a small Stage glyph with
//    their count that brings the Stage to the front (this view sets `rail.stage` and answers `jv-rail-stage`).
//  - On the hub ("Where Jarvis shows things" = On the hub, the old behaviour; and always on the phone, which
//    has no Stage): resting shows the same standby centre; awake, the window canvas (../stage/canvas.js) holds
//    at most six windows counting the now card. Waking, the orb slides into the corner while the windows
//    assemble (slideOrbToDock).
// A key, a click or a pushed window wakes it; core/presence.js sends it back to resting after 2 idle minutes.
import { SAMPLE_MARKS, sampleRail } from "../../components/rail/rail.js";
import { css } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { slideOrbToDock, WindowCanvas, handOffSpin } from "../stage/canvas.js";
import { holderMode, popOut, showStage, windowsFor, windowsHere } from "../stage/desktop.js";
import { popped } from "../../core/popped.js";
import { STAGE_WINDOWS } from "../stage/stage.js";  // also registers /stage and its scenes
import { drawAmbient } from "./ambient.js";  // the home's centre: the orb, and resting, the small clock
import { cameBack, OfferCard } from "./offer.js";  // the return offer: one small glass card under the orb, only while live

css(import.meta.url);

/** The Stage glyph's number on the icon row: the windows up on the Stage (pure; the tests call it). */
export const stageCount = (s) => (s.windows || []).length;

class NowView extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<section class="jv-now" aria-label="Now"><h1 class="jv-sr" tabindex="-1">Now</h1><div class="jv-now__ambient"></div><div class="jv-now__canvas"></div></section>`;
    this.section = this.querySelector(".jv-now");
    this.ambientEl = this.querySelector(".jv-now__ambient");
    this.canvas = new WindowCanvas(this, this.querySelector(".jv-now__canvas"), {
      nowCard: true, resting: () => !!store.state.ui.ambient,
      redraw: () => { if (this.calm || !store.state.ui.ambient) this.draw(); },
      only: (windows, s) => windowsFor(windows, { s }),  // one window: all but the ones he pulled out into the holder
    });
    this.stopPopped = popped.subscribe(() => this.draw());
    this.offer = new OfferCard();
    this.onStage = () => showStage();  // the icon row's Stage glyph
    document.addEventListener("jv-rail-stage", this.onStage);
    this.onRailOpen = () => this.offer.acted();
    document.addEventListener("jv-rail-open", this.onRailOpen);
    this.stop = store.watch(["windows", "now_card", "orb", "ui", "presence", "approvals", "cards", "facts", "branches", "settings", "day", "rail", "marks", "focus", "threads"], () => this.draw());
  }
  disconnectedCallback() {
    this.stop?.(); this.stopPopped?.(); this.canvas.stop(); this.offer.stop();
    document.removeEventListener("jv-rail-stage", this.onStage);
    document.removeEventListener("jv-rail-open", this.onRailOpen);
    this.setStageGlyph(0);
    this.endDocking?.();
    delete document.documentElement.dataset.home;
    if (store.state.ui.ambient) store.setUi({ ambient: false });
  }

  draw() {
    const s = store.state, ambient = !!s.ui.ambient, wasResting = this._resting;
    this._resting = ambient;
    // v0.18.0: with nothing up, the hub is the orb (his ask: one window, the orb in it, and it goes to the corner
    // only when Jarvis pulls something up). So a hub with no windows is the calm home, as it was with a Stage.
    const bare = !windowsFor(s.windows || [], { s }).length && !(s.approvals || []).some((a) => a.status === "pending");
    this.calm = !windowsHere(s) || bare;
    const was = this._ambient;
    this._ambient = this.calm || ambient;  // the orb was in the middle: it slides to the corner when windows come up
    if (wasResting === true && !ambient) queueMicrotask(cameBack);  // he's back: what he let go earlier may be offered again
    const root = document.documentElement;
    if (this.calm) root.dataset.home = "calm"; else delete root.dataset.home;
    const layout = this.calm || ambient;  // the ambient layout: always on the calm home, else while resting
    this.section.classList.toggle("jv-now--ambient-was", this.section.classList.contains("jv-now--ambient"));
    this.section.classList.toggle("jv-now--ambient", layout);
    this.section.classList.toggle("jv-now--calm", this.calm);
    if (layout) {
      const back = !this.section.classList.contains("jv-now--ambient-was");
      this.endDocking?.();
      drawAmbient(this.ambientEl, s);
      // the big orb picks up where the corner orb's rings are (no jump on the way back, v0.6.3)
      if (back) handOffSpin(document.getElementById("orb"), this.ambientEl.querySelector("jv-orb"));
      this.offer.draw(this.ambientEl.querySelector(".jv-amb"), s);
      this.setStageGlyph(this.calm ? stageCount(s) : 0);
      this._ambientBox = this.ambientEl.getBoundingClientRect();
      if (bare && this.querySelector(".jv-now__canvas jv-window[window-id]")) this.canvas.draw(s);  // the last window left: clear it away under the orb
      return;
    }
    this.setStageGlyph(0);
    this.offer.draw(null, s);
    // the screen wakes: the big orb slides into the corner while windows assemble
    this.canvas.move = holderMode(s) ? popOut : null;  // a window dragged off the hub's edge gets a window of its own
    this.canvas.draw(s);
    if (was === true) { this.endDocking?.(); this.endDocking = slideOrbToDock({ layer: this.ambientEl, host: this.section, cls: "jv-now--docking", box: this._ambientBox, windows: this.querySelector(".jv-now__canvas") }); }
  }

  /** The Stage glyph on the icon row: only on the calm home, only while windows are up there. */
  setStageGlyph(n) {
    const rail = document.getElementById("rail");
    if (rail && rail.stage !== (n || null)) rail.stage = n;
  }
}

if (!customElements.get("jv-view-now")) customElements.define("jv-view-now", NowView);

// ---- scenes ----
// The calm home (the default: windows go to the Stage) and, with "On the hub", the old canvas on Now.
const D = "2026-11-16";
const W = STAGE_WINDOWS;
const onHub = (s) => { s.settings = { ...s.settings, stage: "hub" }; };  // Controls › Look › Where Jarvis shows things
const ambient = (s) => { s.ui = { ambient: true }; s.approvals = []; };
registerScene("now-calm", { path: "/now", about: "The calm home, awake, nothing up: the orb alone on the grid, the icon row and the page dots (Huw's awake screen)", patch: (s) => { s.approvals = []; } });
registerScene("now", { path: "/now", about: "The calm home while Jarvis speaks with four windows up on the Stage: his line above the icon row, the Stage glyph says 4", patch: (s) => {
  s.windows = [W.next, W.due, W.file, W.branch]; s.approvals = [];
  s.orb = { state: "speaking", level: 0.6 };
  s.caption = { text: "On track. PPS 7 is half done and due Wednesday at 8.", source: { kind: "canvas", label: "Canvas" }, ttl_ms: 600000 };
} });
registerScene("now-calm-waiting", { path: "/now", about: "The calm home with a question waiting for his yes (the Your yes icon's amber square) and two windows on the Stage", patch: (s) => { s.windows = [W.due, W.approval]; } });
registerScene("now-ambient", { path: "/now", about: "Resting: the small standby sphere with the small clock and the tiny date under it", patch: ambient });
// the return offer ("the hidden trick"): a piece of work he left 35 minutes ago
const left = (s) => { s.approvals = []; s.caption = null; s.threads = s.threads.map((t) => (t.id === "th-pps7" ? { ...t, state: "open", resume: { ...t.resume, at: `${D}T15:05:00` }, updated: `${D}T15:05:00` } : t)); };
registerScene("now-offer", { path: "/now", about: "The calm home with a return offer: one small glass card under the orb (PPS 7 · Q7 · Today), only while it is live", patch: left });
registerScene("now-ambient-resume", { path: "/now", about: "Resting after a short break: the return offer under the small clock", patch: (s) => { ambient(s); left(s); } });
registerScene("now-offer-spoken", { path: "/now", about: "Jarvis says the offer: his line above the icon row has the floor, the card waits until he stops", patch: (s) => {
  left(s); s.orb = { state: "speaking", level: 0.6 };
  s.caption = { text: "PPS 7 is where you left it, at question seven.", source: { kind: "file", label: "PPS 7.pdf" }, ttl_ms: 600000 };
} });
registerScene("now-ambient-waiting", { path: "/now", about: "Resting, with something waiting for a yes (the amber square on the Your yes icon)", patch: (s) => { s.ui = { ambient: true }; } });
registerScene("now-ambient-listening", { path: "/now", about: "Resting while he speaks: the rings wake and his words show above the icon row", patch: (s) => { ambient(s); s.orb = { state: "listening", level: 0.8 }; s.caption = { text: "“Pull up PPS 7.”", source: { kind: "you", label: "You · just now" }, ttl_ms: 600000 }; } });
// "On the hub": the windows on the home page, as before the Stage
registerScene("now-awake", { path: "/now", about: "On the hub: awake with only the now card", patch: (s) => { onHub(s); s.approvals = []; } });
registerScene("now-active", { path: "/now", about: "On the hub: windows pushed while Jarvis talks", patch: (s) => { onHub(s); s.windows = [W.next, W.due, W.file, W.branch]; s.orb = { state: "speaking", level: 0.6 }; s.caption = { text: "On track. PPS 7 is half done and due Wednesday at 8.", source: { kind: "canvas", label: "Canvas" }, ttl_ms: 600000 }; s.approvals = []; } });
registerScene("now-waiting", { path: "/now", about: "On the hub: an approval waiting for his yes", patch: (s) => { onHub(s); s.windows = [W.due, W.approval]; s.orb = { state: "waiting", countdown_s: 7, window_s: 10 }; } });
registerScene("now-full", { path: "/now", about: "On the hub: the now card and five windows (six on screen, the most)", patch: (s) => { onHub(s); s.windows = [W.due, W.chart, W.file, W.branch, W.approval]; } });
registerScene("now-crowded", { path: "/now", about: "On the hub: six windows from an older hub: the oldest unpinned one docks (a pure view just closes)", patch: (s) => { onHub(s); s.windows = [W.next, W.due, W.chart, W.file, W.branch, W.approval]; } });
registerScene("now-pulled-out", { path: "/now", about: "On the hub with one window pulled out into its own window: the hub draws the rest", patch: (s) => { onHub(s); s.windows = [W.next, W.due, W.file, W.branch]; s.approvals = []; popped.pretend([W.file.id]); } });
// "nothing gets away": the Rail filled as the hub builds it, marks, the wants-you brackets and the voice's focus cue
const railed = (s) => { onHub(s); s.rail = sampleRail(); delete s.rail.slots.homework.items[0].window; s.marks = {}; };
registerScene("now-rail", { path: "/now", about: "On the hub: windows up, the icon row filled: counts and the wants-you shapes", patch: (s) => { s.windows = [W.due, W.file, W.branch]; railed(s); s.approvals = []; s.rail.slots.yes = { items: [] }; } });
registerScene("now-marks", { path: "/now", about: "On the hub: since you looked: cyan notches on the icon row and on the window whose due date moved", patch: (s) => { s.windows = [W.due, W.file, W.branch]; railed(s); s.marks = structuredClone(SAMPLE_MARKS); } });
registerScene("now-wants", { path: "/now", about: "On the hub: corner brackets only for wants-you: your yes, soon, and an overdue one (critical)", patch: (s) => {
  s.windows = [W.due, W.file, W.approval]; railed(s);
  const pps = s.rail.slots.homework.items[0]; pps.state = "critical"; pps.detail = "Overdue since Wed 8 pm"; s.rail.slots.homework.worst = "critical";
  s.rail.slots.homework.items.push({ ref: "file-pps7", slot: "homework", kind: "thread", title: "PPS 7", at: "2026-11-16T15:40:00", state: "soon", detail: "Q7" });
} });
registerScene("now-focus", { path: "/now", about: "On the hub: Jarvis names PPS 7 as he speaks: brackets snap onto its window and its icon", patch: (s) => {
  s.windows = [W.next, W.due, W.file, W.branch]; railed(s); s.approvals = [];
  s.focus = { ref: "due-pps7", until: `${D}T15:40:44` }; s.orb = { state: "speaking", level: 0.6 };
  s.caption = { text: "Two due this week, the nearest Wednesday at 8.", source: { kind: "canvas", label: "Canvas" }, ttl_ms: 600000 };
} });
registerScene("now-rail-open", { path: "/now", about: "On the hub: the Homework icon opened: its things fan out above the icon row", patch: (s) => { s.windows = [W.file, W.branch]; railed(s); s.marks = structuredClone(SAMPLE_MARKS); s.ui = { ...s.ui, railOpen: "homework" }; } });
registerScene("now-ambient-rail", { path: "/now", about: "Resting, with the icon row: only filled slots, static", patch: (s) => { ambient(s); s.rail = sampleRail(); delete s.rail.slots.homework.items[0].window; s.rail.slots.yes = { items: [] }; s.marks = structuredClone(SAMPLE_MARKS); } });
registerScene("now-offline", { path: "/now", about: "The hub can't be reached", patch: (s) => { ambient(s); s.orb = { state: "offline", message: "Can't reach the hub. It will reconnect on its own." }; s.ui.online = false; } });
