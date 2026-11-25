// <jv-orb>: the Core, Jarvis's face (HUD v2 §4, §7; built from Huw Prosser's orb, measured layer by layer).
//
//   state   = idle | listening | thinking | speaking | waiting | muted | offline   (the orb_state contract)
//             + standby (the quiet ambient screen) and alert (an alert with no other state)
//   size    = centre (the full orb) | corner (the docked mini rings: 120 px, 64 px on a laptop) | strip (still)
//             The centre orb's box comes from the host: --jv-orb-size (CSS, on it or a parent). The default makes
//             the outer ornaments about 1/6 of the screen's width, as in Huw's reels (HUD v3 §14).
//   alert   = warn | crit       the ring turns amber or red with one 600 ms pulse (crit also plays the low tone)
//   wake    = full | tighten | none   which beat the next wake plays (idle/standby/muted → listening).
//             Default tighten (250 ms). Say "full" only for the first wake of the day or after ≥ 4 h away
//             (wakeKind() works that out). Listening shows from the first frame either way.
//   docked  (centre only) outer layers retract (200 ms), then the orb slides and scales to the dock (700 ms);
//             fires `jv-orb-docked` / `jv-orb-undocked`. Within 60 s of the last dock it doesn't slide again.
//   openable  the orb is a button that fires `jv-orb-open` (the docked orb brings back the full view)
//   data-offstage  set by a view that hides the orb (the Stage's centre orb while windows are up): every
//             animation pauses and the level loop leaves, as when it is off screen
//   .orb      an orb_state object (level 0–1 brightens the band's glow; countdown_s / window_s the yes window)
//   dial      draw the day dial at 2.5 R (off by default since HUD v3: the home screen has nothing round the orb)
//   .dialSlot the light-DOM box at 2.5 R where the day dial mounts (or give a child slot="dial"); hidden without `dial`
//   Look (v3): near-white lines; the deep blue energy ring only while listening or speaking, with a glow that hugs
//             the band; no pulsing: nothing scales with the voice, the rings turn faster while Jarvis speaks and
//             only the glow's opacity follows the level; the cardinal ticks are bare; a faint blue halo at rest; docked (corner, or centre with docked) white rings only. Standby is the particle sphere with
//             the wordmark; the host puts <jv-clock small> under it (the orb never draws a clock).
//
// Motion: CSS on composited <div>s (rotation about the centre and opacity only; the yes drain is a
// stroke-dashoffset in 48 steps). One shared 30 fps rAF loop, only for the voice level (the glow's opacity), only while listening or speaking, paused when the page
// is hidden, the orb is off screen or a game is on. Reduced motion and the strip: a still pose per state,
// with the state in colour and a word.
import { css, Jv } from "../../core/dom.js";
import { store } from "../../core/store.js";
import { inGame, play } from "../../sounds/earcons.js";
import { ALERT_WORDS, AMBIENT_STATES, LEVEL_STATES, ORB_WORDS, orbMarkup, REST_STATES, RING_WORDS, STATES, stripMarkup, wakeKind } from "./orb-parts.js";
import "./orb-scenes.js";

export { ORB_WORDS, wakeKind };
css(import.meta.url);

const root = document.documentElement;
const calm = matchMedia("(prefers-reduced-motion: reduce)");
/** True when nothing on the orb may move: reduced motion (Windows or Controls) or the strip. */
export const isStill = () => root.hasAttribute("data-still") || root.dataset.size === "strip"
  || ["reduced", "off"].includes(root.dataset.motion) || (calm.matches && root.dataset.motion !== "full");
/** The docked orb's size by screen size (HUD v2 §4: 120 px on the big screen, 64 px on a laptop). */
export const DOCK_SIZES = { full: 120, ambient: 120, laptop: 64, phone: 44 };
const dockSize = () => DOCK_SIZES[root.dataset.size] || 120;
const MINI_UNITS = 146;  // units across the mini rings (the dotted ring at 1.9 R plus its dots)
const DOCK_SKIP_MS = 60_000;
const RETRACT_MS = 120, SLIDE_MS = 450;  // the slide starts while the outer rings are still pulling in (one motion, not two)
const clamp01 = (v) => Math.min(1, Math.max(0, Number(v) || 0));
export const GLOW_ATTACK_S = 0.04, GLOW_RELEASE_S = 0.3;  // like a level meter: ~40 ms up, ~300 ms back down

// ---- the one loop: 30 fps, voice level only ------------------------------------------------------------
const FRAME_MS = 1000 / 30 - 3;
const loop = { orbs: new Set(), raf: 0, last: -1e9, frames: 0 };
function tick(t) {
  loop.raf = 0;
  if (t - loop.last >= FRAME_MS) { loop.last = t; loop.frames++; for (const o of [...loop.orbs]) o.frame(t); }
  if (loop.orbs.size) loop.raf = requestAnimationFrame(tick);
}
function join(o) { loop.orbs.add(o); if (!loop.raf) loop.raf = requestAnimationFrame(tick); }
function leave(o) { loop.orbs.delete(o); if (!loop.orbs.size && loop.raf) { cancelAnimationFrame(loop.raf); loop.raf = 0; } }
/** For tests and Under the hood: is the loop running, how many orbs it drives, frames run so far. */
export const orbLoop = { get running() { return !!loop.raf; }, get orbs() { return loop.orbs.size; }, get frames() { return loop.frames; } };

// ---- the world the orbs react to: hidden page, reduced motion, size, game mode, metrics -------------------
const orbs = new Set();
const recheck = () => orbs.forEach((o) => o.reconsider());
document.addEventListener("visibilitychange", recheck);
calm.addEventListener("change", recheck);
new MutationObserver(recheck).observe(root, { attributes: true, attributeFilter: ["data-still", "data-size", "data-motion", "data-hidden"] });
store.subscribe((s, keys) => {
  if (keys.has("now_card") || keys.has("settings")) recheck();
  // a voice-level tick (store fast path): the glow and the wheels follow it without re-rendering anything
  // (the resting screen shows "standby" while the state is idle: the room's level reaches it too)
  if (keys.has("orb_level")) orbs.forEach((o) => { if (stateOf(o.dataset.look) === s.orb?.state) o.level = s.orb.level; });
});
const stateOf = (look) => (look === "standby" ? "idle" : look);
const METERED = (look) => LEVEL_STATES.has(look) || AMBIENT_STATES.has(look);
const TICK_GAP_MS = 2500;  // "heard you" at most once per thought: a sentence said in two parts doesn't tick twice
let lastTick = -1e9;

let seq = 0;
let lastDock = -1e9;

// ---- the extra spin (v0.11.2, his design): driven here, not by CSS, so it speeds up and slows down smoothly ------
// deg/s for each ring's extra spinner. The inner arcs turn faster while thinking or speaking (as before, but eased
// in and out instead of switching). While Jarvis speaks, the outer arc and the dotted ring turn the other way
// like a visualizer, as fast as his voice is loud; when he stops they coast to a halt.
export const SPIN = {
  "arcs-a": (look) => (look === "thinking" || look === "speaking" ? 30 : 0),
  "arcs-b": (look) => (look === "thinking" || look === "speaking" ? -18 : 0),
  outer: (look, level) => (look === "speaking" ? -(20 + 200 * level) : 0),
  dots: (look, level) => (look === "speaking" ? -(12 + 120 * level) : 0),
};
const SPIN_EASE_S = 0.35;  // how quickly a ring reaches a new speed (time constant): smooth start, smooth stop

class Orb extends Jv {
  static attrs = ["state", "size", "alert", "wake", "docked", "openable"];
  static props = ["orb"];

  connectedCallback() {
    super.connectedCallback();
    orbs.add(this);
    if (!this._io && "IntersectionObserver" in window) {
      this._io = new IntersectionObserver((entries) => { this._visible = entries[entries.length - 1].isIntersecting; this.reconsider(); });
    }
    this._io?.observe(this);
  }

  setup() {
    this._id = `jvo${++seq}`;
    this._shown = 0; this._target = 0; this._lit = -1; this._hashAt = -1e9;
    this.addEventListener("click", (e) => { if (e.target.closest(".jv-orb__open")) this.emit("jv-orb-open", {}); });
    // a child given slot="dial" (the day dial) moves into the dial slot
    new MutationObserver(() => this.adoptDial()).observe(this, { childList: true });
  }

  teardown() {
    orbs.delete(this);
    leave(this);
    this._io?.unobserve(this);
    for (const t of ["_wakeT", "_pulseT", "_dockT"]) clearTimeout(this[t]);
  }

  /** The state as given (for older callers); unknown values read as idle. */
  get state() { const s = this.getAttribute("state"); return STATES.includes(s) ? s : "idle"; }
  get sizeName() { const s = this.getAttribute("size"); return s === "corner" || s === "strip" ? s : "centre"; }
  get dialSlot() { return this.querySelector(".jv-orb__dial"); }
  /** Set the voice level directly (a local audio meter), without a store round trip. */
  set level(v) { this._target = clamp01(v); this._levelAt = performance.now(); this.reconsider(); }
  get level() { return this._target; }

  // Built once per size; every other change only updates attributes, text and inline transforms, so state
  // changes can transition and the level loop never touches the DOM structure.
  _render() {
    if (this._built !== this.sizeName || this._openable !== this.hasAttribute("openable")) this.build();
    this.sync();
  }

  build() {
    const size = this.sizeName, keep = [...this.querySelectorAll(":scope > [slot=dial], .jv-orb__dial > *")];
    this._built = size;
    this._openable = this.hasAttribute("openable");
    this.innerHTML = `<div class="jv-orb__stage" role="img">${size === "strip" ? stripMarkup() : orbMarkup(this._id, { corner: size === "corner" })}<span class="jv-orb__word" aria-hidden="true"></span></div>${
      this._openable ? '<button type="button" class="jv-orb__open" aria-label="Show the full view"></button>' : ""}`;
    const q = (s) => this.querySelector(s);
    this.$ = { stage: q(".jv-orb__stage"), glow: q(".jv-orb__L--glow .jv-orb__lvl"), halo: q(".jv-orb__L--halo"),
      hash: [...this.querySelectorAll(".jv-orb__hash")],
      word: q(".jv-orb__word"), drain: q(".jv-orb__drain-mask"), dial: q(".jv-orb__dial") };
    const prev = this._spins || {};
    this._spins = Object.fromEntries(Object.keys(SPIN).map((name) => [name, {
      el: q(`.jv-orb__L--${name} .jv-orb__spin2`), angle: prev[name]?.angle || 0, v: 0 }]).filter(([, w]) => w.el));
    for (const w of Object.values(this._spins)) w.el.style.transform = `rotate(${w.angle.toFixed(2)}deg)`;
    this.$.dial?.append(...keep);
    this._state = undefined; this._docked = undefined; this._alert = ""; this._lit = -1;
  }

  adoptDial() {
    const kids = this.querySelectorAll(":scope > [slot=dial]");
    if (kids.length && this.$?.dial) this.$.dial.append(...kids);
  }

  sync() {
    const state = this.state, prev = this._state, o = this.orb || {}, look = state === "alert" ? "idle" : state;
    const given = this.getAttribute("alert");
    const alert = given === "warn" || given === "crit" ? given : state === "alert" ? "warn" : "";
    this.dataset.look = look;
    if (alert) this.dataset.alert = alert; else delete this.dataset.alert;

    // a wake: Listening is drawn from this very frame; the beat is decoration on top of it
    if (prev !== undefined && prev !== state) {
      if (REST_STATES.has(prev) && state === "listening") {
        const want = this.getAttribute("wake");
        this.beat("wake", want === "none" ? null : want === "full" ? "full" : "tighten", want === "full" ? 1300 : 260, "_wakeT");
        if (want === "full") play("wake");
      }
      if (prev === "listening" && state === "thinking" && performance.now() - lastTick >= TICK_GAP_MS) {
        lastTick = performance.now();
        play("tick");  // heard and taken: the non-verbal "got it"
      }
    }
    // the low tone marks a critical alert arriving, never one that was already there when the page (re)loaded
    if (alert && alert !== this._alert) { this.beat("pulse", "", 620, "_pulseT"); if (alert === "crit" && prev !== undefined) play("critical"); }
    this._alert = alert;

    if (state === "waiting" && (prev !== "waiting" || o !== this._waitFor)) this.startDrain(o);
    this._state = state;

    const label = `Jarvis: ${ORB_WORDS[look].toLowerCase()}${alert ? `, ${ALERT_WORDS[alert].toLowerCase()}` : ""}`;
    this.$.stage.setAttribute("aria-label", label);
    const word = alert ? ALERT_WORDS[alert] : RING_WORDS[look] || "";
    if (this.$.word.textContent !== word) this.$.word.textContent = word;
    // a state change with no level keeps the meter's last reading (a tick is ~80 ms away); with no meter at all
    // (no voice window open) the rest states sit at their full, steady light as before
    if (o.level != null) { this._target = clamp01(o.level); this._levelAt = performance.now(); }
    else if (performance.now() - (this._levelAt ?? -1e9) > 1500) this._target = AMBIENT_STATES.has(look) ? 1 : look === "listening" ? 0.5 : 0.6;

    const docked = this.hasAttribute("docked") && this.sizeName === "centre";
    if (docked !== this._docked) { const first = this._docked === undefined; this._docked = docked; if (docked || !first) this.dock(docked, first); }
    this.reconsider();
  }

  /** Set data-<name> for `ms` (restarting its CSS animation), unless nothing may move. */
  beat(name, value, ms, timer) {
    clearTimeout(this[timer]);
    delete this.dataset[name];
    if (value == null || isStill() || this.sizeName === "strip") return;
    void this.offsetWidth;  // restart the animation if the same beat comes again
    this.dataset[name] = value;
    this[timer] = setTimeout(() => delete this.dataset[name], ms);
  }

  /** The answer window: only the dim dotted ring drains, one dot at a time (no number, ever). */
  startDrain(o) {
    this._waitFor = o;
    const m = this.$.drain;
    if (!m) return;
    const total = Math.max(1, Number(o.window_s ?? o.countdown_s ?? 10));
    const left = Math.min(total, Math.max(0, Number(o.countdown_s ?? total)));
    m.style.setProperty("--win", `${total}s`);
    m.style.setProperty("--ago", `${-(total - left)}s`);
    m.style.setProperty("--left", `${-Math.round(48 * (1 - left / total))}`);  // the still pose: what's left now
    m.style.animationName = "none";
    void m.getBoundingClientRect();
    m.style.animationName = "";
  }

  // ---- the level loop --------------------------------------------------------------------------------
  /** Join or leave the loop, and pause the CSS motion when off screen or in a game. */
  reconsider() {
    if (!this.$) return;
    // off screen: outside the viewport, or hidden by its view (data-offstage: the Stage's centre orb while windows are up)
    const look = this.dataset.look, offscreen = this._visible === false || this.hasAttribute("data-offstage"), game = inGame(store.state);
    this.toggleAttribute("data-paused", offscreen || game);
    const can = this.isConnected && this.sizeName !== "strip" && !isStill() && !document.hidden && !offscreen && !game;
    const levelWork = METERED(look) && Math.abs(this._target - this._shown) > 0.002;
    if (can && (levelWork || this.spinning())) join(this);
    else { leave(this); this._lastT = undefined; this.pose(); }
  }

  /** Does any ring still have to turn (a speed to reach, or one to coast down from)? */
  spinning() {
    const look = this.dataset.look, lvl = this._shown;
    return Object.entries(this._spins || {}).some(([name, w]) => Math.abs(w.v) > 0.05 || SPIN[name](look, lvl) !== 0);
  }

  /** Turn each ring's extra spinner by its speed, easing the speed toward the target (never a jump). */
  turn(dt) {
    const look = this.dataset.look, k = 1 - Math.exp(-dt / SPIN_EASE_S);
    for (const [name, w] of Object.entries(this._spins || {})) {
      const target = SPIN[name](look, this._shown);
      w.v += (target - w.v) * k;
      if (target === 0 && Math.abs(w.v) < 0.05) w.v = 0;
      if (w.v) { w.angle = (w.angle + w.v * dt) % 360; w.el.style.transform = `rotate(${w.angle.toFixed(2)}deg)`; }
    }
  }

  /** Take the rings' angles and speeds from another orb (the Stage's hand-off), so nothing jumps. */
  takeSpin(from) {
    for (const [name, w] of Object.entries(this._spins || {})) {
      const o = from?._spins?.[name];
      if (!o) continue;
      w.angle = o.angle; w.v = o.v; w.el.style.transform = `rotate(${w.angle.toFixed(2)}deg)`;
    }
    this.reconsider();
  }

  frame(t) {
    const dt = this._lastT === undefined ? 1 / 30 : Math.min(0.1, (t - this._lastT) / 1000);
    this._lastT = t;
    this.turn(dt);
    if (!METERED(this.dataset.look)) {
      this.pose();
      if (!this.spinning()) { leave(this); this._lastT = undefined; }
      return;
    }
    // meter ballistics (v0.12.3): rise fast so every syllable shows, fall back slowly so it reads as a voice
    const tau = this._target > this._shown ? GLOW_ATTACK_S : GLOW_RELEASE_S;
    this._shown += (this._target - this._shown) * (1 - Math.exp(-dt / tau));
    if (Math.abs(this._target - this._shown) < 0.002) this._shown = this._target;
    this.applyLevel(this._shown);
    // hash marks step in order with the voice, at most 3 changes a second (never a glitchy re-randomise)
    if (this.dataset.look === "speaking") {
      const lit = Math.max(1, Math.round(this._shown * 4));
      if (lit !== this._lit && t - this._hashAt >= 334) { this._lit = lit; this._hashAt = t; this.$.hash.forEach((p, k) => { p.style.opacity = k < lit ? "1" : "0.22"; }); }
    } else if (this._lit !== 0) { this._lit = 0; this.$.hash.forEach((p) => { p.style.opacity = ""; }); }
    if (this._shown === this._target && !this.spinning()) { leave(this); this._lastT = undefined; }  // settled
  }

  /** The still pose for this state (reduced motion, paused, or simply settled). */
  pose() {
    if (!this.$) return;
    this._shown = this._target;
    if (METERED(this.dataset.look) && this.sizeName !== "strip") this.applyLevel(this._shown);
    else { if (this.$.glow) this.$.glow.style.opacity = ""; if (this.$.halo) this.$.halo.style.opacity = ""; }
    const lit = this.dataset.look === "speaking" ? Math.max(1, Math.round(this._shown * 4)) : 0;
    if (lit !== this._lit) { this._lit = lit; this.$.hash.forEach((p, k) => { p.style.opacity = lit ? (k < lit ? "1" : "0.22") : ""; }); }
  }

  /** The voice changes one thing: the opacity of the static glow that hugs the band. Nothing scales: the orb
   *  never pulses (his decision, v0.4.1); while Jarvis speaks the rings turn faster instead (orb.css). */
  applyLevel(level) {
    const { glow, halo } = this.$, look = this.dataset.look;
    if (look === "standby") {
      // the resting sphere: its halo breathes with the room (0.12 in silence, up to ~0.6 for a voice)
      if (halo) halo.style.opacity = (0.12 + 0.5 * level).toFixed(3);
      if (glow) glow.style.opacity = "";
      return;
    }
    if (halo) halo.style.opacity = "";
    if (!glow) return;
    // a voice (his or Jarvis's): the wide range from v0.11.2. At rest: gentler, never dark, full with no meter.
    glow.style.opacity = (LEVEL_STATES.has(look) ? 0.3 + 0.7 * level : 0.45 + 0.55 * level).toFixed(3);
  }

  // ---- docking ---------------------------------------------------------------------------------------
  /** Outer layers retract (200 ms), then the orb slides and scales into the dock (700 ms), or back out. */
  dock(on, first = false) {
    const stage = this.$.stage, now = performance.now();
    clearTimeout(this._dockT);
    const instant = first || isStill() || (on && now - lastDock < DOCK_SKIP_MS);
    const done = (name) => this.emit(name, {});
    if (instant) {
      this.dataset.instant = "";
      if (on) { this.dataset.dock = "docked"; stage.style.transform = this.dockTransform(); lastDock = now; } else { delete this.dataset.dock; stage.style.transform = ""; }
      requestAnimationFrame(() => requestAnimationFrame(() => delete this.dataset.instant));
      if (!first) done(on ? "jv-orb-docked" : "jv-orb-undocked");
      return;
    }
    if (on) {
      this.dataset.dock = "retract";
      this._dockT = setTimeout(() => {
        this.dataset.dock = "slide";
        stage.style.transform = this.dockTransform();
        this._dockT = setTimeout(() => { this.dataset.dock = "docked"; lastDock = performance.now(); done("jv-orb-docked"); }, SLIDE_MS);
      }, RETRACT_MS);
    } else {
      this.dataset.dock = "return";
      stage.style.transform = "";
      this._dockT = setTimeout(() => { delete this.dataset.dock; done("jv-orb-undocked"); }, SLIDE_MS);
    }
  }

  /** From where the orb is to the dock (#dock, or the selector in dock-to): the mini rings' size and place. */
  dockTransform() {
    const r = this.getBoundingClientRect();
    if (!r.width) return "";
    const S = dockSize(), dock = document.querySelector(this.getAttribute("dock-to") || "#dock")?.getBoundingClientRect();
    const right = dock && dock.right > 0 ? dock.right : innerWidth - 20, bottom = dock && dock.bottom > 0 ? dock.bottom : innerHeight - 14;
    const dx = right - S / 2 - (r.left + r.width / 2), dy = bottom - S / 2 - (r.top + r.height / 2);
    return `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px) scale(${(S / ((r.width * MINI_UNITS) / 220)).toFixed(4)})`;
  }
}
Orb.define("jv-orb");

/** Forget when the orb last docked (scenes and tests). */
export const resetDock = () => { lastDock = -1e9; };
