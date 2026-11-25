// Idle ↔ ambient (B03) and the window clock.
//  - After 2 minutes with no key, click or pointer, the hub goes back to the ambient Now screen (calm periphery),
//    also when a question is waiting for his yes (the ambient screen shows "1 waiting for your yes").
//  - Any key, click, pushed window, or Jarvis hearing him wakes it.
//  - Windows dock into their Rail slot 60 s after they were last used unless pinned (the window manager decides
//    which). The clock sends `dock` with reason "lifetime": nothing is deleted (HUD v2 §6.2, contracts v2).
//  - Timers stop while the window is hidden, and never run in scenes (so screenshots are stable).
import { bridge } from "./bridge.js";
import { router } from "./router.js";
import { store } from "./store.js";
import { popped } from "./popped.js";
import { WindowClock } from "./windows.js";

export const IDLE_MS = 120_000;
export const KEEP_WINDOWS = true;  // false brings back the 60 s lifetime (core/windows.js WindowClock)
export const windowClock = new WindowClock((id) => bridge.act("dock", id, { reason: "lifetime" }));

let lastActive = performance.now();
let timer = null;

/** Wake the hub (leave the ambient screen). Returns true if it was asleep. */
export function wake() {
  lastActive = performance.now();
  if (!store.state.ui.ambient) return false;
  store.setUi({ ambient: false });
  return true;
}
/** Go to the ambient screen now. */
export function rest() {
  if (router.current.path !== "/now") router.go("/now");
  if (!store.state.ui.ambient) store.setUi({ ambient: true });
}
export const idleFor = () => performance.now() - lastActive;

export function startPresence({ live = true, ambientAtStart = true } = {}) {
  if (ambientAtStart && store.state.ui.ambient === false && !store.state.windows.length) store.setUi({ ambient: true });
  const onInput = (e) => {
    const asleep = store.state.ui.ambient && router.current.path === "/now";
    lastActive = performance.now();
    if (!asleep) return;
    // the first key or click on the idle screen only wakes it (Esc, Enter, Space or any click), like a lock screen;
    // links on the idle screen (page dots, "waiting for your yes") still work
    if (e.type === "keydown" && (e.ctrlKey || e.metaKey || e.altKey || ["Tab", "Shift", "Control", "Alt", "Meta"].includes(e.key))) return;
    if (e.target.closest?.("a, button, jv-tabs, jv-status-line, jv-command-bar")) return;
    wake();
  };
  ["keydown", "pointerdown", "wheel"].forEach((name) => document.addEventListener(name, onInput, { passive: true, capture: true }));
  store.onEvent((event) => {
    if (event.type === "window.push" || event.type === "approval.pending") wake();
    if (event.type === "orb.state" && ["listening", "waiting"].includes(event.data.state)) lastActive = performance.now();
    if (event.type === "presence.changed" && event.data.here === true) lastActive = performance.now();
    // he has left (HUD v2 §9.6 wind-down): the hub rests on the ambient screen, where the orb stands by
    if (event.type === "presence.changed" && event.data.here === false && store.state.settings.ambient !== false
      && !["phone", "strip"].includes(document.documentElement.dataset.size) && !store.state.windows.length) rest();
  });
  router.onChange((route) => { lastActive = performance.now(); if (route.path !== "/now" && store.state.ui.ambient) store.setUi({ ambient: false }); });
  if (!live) return;
  timer = setInterval(() => {
    if (document.hidden || ["phone", "strip"].includes(document.documentElement.dataset.size)) return;  // the size now, not at boot
    // a window that is still waiting for his yes stays up; it is the question, not decoration
    const waiting = new Set(store.state.approvals.filter((a) => a.status === "pending").map((a) => a.id));
    // a window he pulled out into its own window is the holder's, not this screen's: it stays until he closes it
    const out = store.state.settings?.stage === "window" ? new Set() : popped.ids();
    // v0.24.1 (his ask): a window stays up until he closes it, clears the view or a sixth one takes its place. The 60 s
    // clock closed the formula sheet he was working from, and with nothing up the orb went back to the middle.
    if (KEEP_WINDOWS) windowClock.seen(store.state.windows);
    else windowClock.tick(store.state.windows.filter((w) => !(w.type === "approval" && waiting.has(w.ref)) && !out.has(w.id)));
    const step = idleStep(store.state, { path: router.current.path, idle: idleFor(), busy: !!document.querySelector("jv-command-bar")?.isOpen });
    if (step === "rest") rest();
    else if (step === "now") router.go("/now");
  }, 5000);
}

/** What 2 idle minutes do: "rest" (the ambient screen), "now" (go and show the windows that are up) or null.
 *  A question waiting for his yes doesn't keep the hub awake: the ambient screen says "1 waiting for your yes",
 *  and the window comes back when he wakes it. */
export function idleStep(state, { path, idle, busy = false }) {
  const asleep = state.ui.ambient && path === "/now";
  if (state.settings.ambient === false || busy || asleep || idle < IDLE_MS) return null;  // Controls › Look › Ambient screen
  if (["listening", "thinking", "speaking", "waiting"].includes(state.orb.state)) return null;
  const waiting = new Set(state.approvals.filter((a) => a.status === "pending").map((a) => a.id));
  const shown = state.windows.filter((w) => !(w.type === "approval" && waiting.has(w.ref)));
  if (!shown.length) return "rest";
  return path !== "/now" ? "now" : null;  // windows are up: show them, don't hide them
}
export function stopPresence() { clearInterval(timer); }
