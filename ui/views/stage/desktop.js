// The hub and the Stage are two windows (N9, HUD v2 §6.5). This is the one place that talks between them.
//  - Desktop (app.py, pywebview): the Stage is a second, borderless window, made hidden at start. The hub
//    window reports what decides it (windows up, the setting, game mode) to `sync_stage`; app.py's
//    should_show_stage() shows it, keeps it on standby or hides it. `show_stage()` brings it to the front (the
//    "Stage · N" chip) and `focus_hub(path?)` brings the hub back, at a page if given (the Stage's Hub pill,
//    a link inside a window).
//  - Browser (dev, --browser): the Stage is /stage in a window named "jarvis-stage"; the hub is "jarvis-hub".
// Both windows read the same live stream, so nothing here carries data, only "show" and "where".
import { popped } from "../../core/popped.js";
import { store } from "../../core/store.js";

export const STAGE_URL = "/?window=stage#/stage";
const api = () => window.pywebview?.api || null;

/** Controls › Screens › "Where Jarvis shows things": "hub" (one window, the default since v0.17.0: what Jarvis
 *  pulls up shows on the hub itself) or "window" (the Stage: a second, full-screen window for them). */
export const stageSetting = (s = store.state) => (s.settings?.stage === "window" ? "window" : "hub");

/** Do pushed windows show on this screen? The Stage always; the hub with "On the hub"; the phone always
 *  (the phone has no Stage: it keeps its own column). */
export function windowsHere(s = store.state, { stageWindow = false, size = document.documentElement.dataset.size } = {}) {
  return stageWindow || size === "phone" || stageSetting(s) === "hub";
}

/** With one window, the second window is only a holder for what he pulled out of the hub. */
export const holderMode = (s = store.state) => stageSetting(s) === "hub";

/** Which of `windows` this screen draws. One window: the hub draws all but the ones he pulled out, the holder
 *  only those. The Stage (the other setting) draws them all and the hub none. */
export function windowsFor(windows, { stageWindow = false, s = store.state, out = popped.ids() } = {}) {
  if (!holderMode(s) || document.documentElement.dataset.size === "phone") return windows;
  return windows.filter((w) => out.has(w.id) === stageWindow);
}

/** How many windows are out in the holder right now (only ones that are still up count). */
export const outCount = (s = store.state, out = popped.ids()) => (s.windows || []).filter((w) => out.has(w.id)).length;

/** What app.py's should_show_stage(state, settings, device) reads, and nothing else (no titles, no data). */
export function stageReport(s = store.state) {
  return {
    state: { windows: (s.windows || []).map((w) => ({ id: w.id })), now_card: { moment: s.now_card?.moment ?? null }, popped: outCount(s) },
    settings: { stage: stageSetting(s), game_mode: s.settings?.game_mode || "auto" },
  };
}

/** Pull a window out of the hub into the holder (it opens if it isn't up), or bring one back. */
export function popOut(id) {
  popped.out(id);
  const desk = api();
  if (!desk?.sync_stage) named("jarvis-stage", STAGE_URL);  // a browser: the holder is a window named jarvis-stage
}
export function popIn(id) { popped.in(id); }

/** Open (or find) a named browser window without reloading it if it is already there.
 *  → { win, fresh }: fresh is true when it was just sent to `url` (so the caller doesn't overwrite that pending navigation). */
function named(name, url) {
  const win = window.open("", name);
  if (!win) return null;  // a blocked pop-up: nothing to do
  let fresh = false;
  try { if (win.location.href === "about:blank") { win.location.href = url; fresh = true; } } catch { win.location.href = url; fresh = true; }
  win.focus();
  return { win, fresh };
}

/** Bring the Stage to the front ("Stage · N"). → "desktop" | "browser" | null */
export function showStage() {
  const desk = api();
  if (desk?.show_stage) { desk.show_stage(); return "desktop"; }
  return named("jarvis-stage", STAGE_URL)?.win ? "browser" : null;
}

/** Bring the hub back, at `path` if given ("put it on the hub", a link inside a Stage window). */
export function focusHub(path = null) {
  const desk = api();
  if (desk?.focus_hub) { desk.focus_hub(path); return "desktop"; }
  const opener = window.opener && !window.opener.closed && window.opener.name === "jarvis-hub" ? window.opener : null;
  const found = opener ? { win: opener, fresh: false } : named("jarvis-hub", `/${path ? `#${path}` : ""}`);
  const hub = found?.win;
  if (!hub) return null;
  // a hub window that was only just opened is already on its way to the path: setting the hash on its
  // about:blank would cancel that (it used to open about:blank#/read/…)
  if (path && !found.fresh) { try { hub.__jarvis?.router ? hub.__jarvis.router.go(path) : (hub.location.hash = `#${path}`); } catch { /* another origin: it opened at the path */ } }
  hub.focus();
  return "browser";
}

/** The hub window tells app.py what decides the Stage, whenever it changes (desktop only; a no-op in a
 *  browser). Event-driven, so the Stage shows within a frame of the push (it was made hidden at start). */
export function startStageSync() {
  let last = "";
  const send = () => {
    const desk = api();
    if (!desk?.sync_stage) return;
    const report = stageReport(store.state), key = JSON.stringify(report);
    if (key === last) return;
    last = key;
    desk.sync_stage(report);
  };
  store.subscribe((s, keys) => {
    if (keys.has("windows")) popped.prune(new Set((s.windows || []).map((w) => w.id)));  // a closed window is out of nothing
    if (keys.has("windows") || keys.has("settings") || keys.has("now_card")) send();
  });
  popped.subscribe(send);
  window.addEventListener("pywebviewready", () => { last = ""; send(); });
  send();
}
