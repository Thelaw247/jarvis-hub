// Boot: theme and size, state, the shell regions, then views. Keeps the shell elements in step with the store.
import "./placeholder.js";
import { startA11y } from "./a11y.js";
import { bridge } from "./bridge.js";
import { connect } from "./events.js";
import { showShortcuts, startKeys } from "./keys.js";
import { orbView, showOrb } from "./orbview.js";
import { rest, startPresence, windowClock } from "./presence.js";
import { router, TABS } from "./router.js";
import { getScene, params, sceneName, sceneNames } from "./scenes.js";
import { store } from "./store.js";
import { forcedTheme, startTheme } from "./theme.js";
import { command as windowCommand } from "./windows.js";
import { focusHub, startStageSync, windowsHere } from "../views/stage/desktop.js";
import { popped } from "./popped.js";

const root = document.documentElement;
const $ = (id) => document.getElementById(id);
// The Stage (N9, HUD v2 §6.5) is this same page in a second window: ?window=stage#/stage. It stays on /stage
// (links open in the hub), has no ambient screen and keeps the windows' 60 s clock itself (views/stage).
const STAGE_WINDOW = params.get("window") === "stage";

// Size follows the window live (resize, snap, rotate): phone below 720 px, laptop to 1280 px, full above.
// ?size= (strip, ambient, or a forced size) and a scene's own size stay fixed.
const PHONE = matchMedia("(max-width: 719.98px)"), LAPTOP = matchMedia("(max-width: 1280px)");
let sizeFixed = false;
export const autoSize = () => (PHONE.matches ? "phone" : LAPTOP.matches ? "laptop" : "full");

/** Set data-size and put the tabs where they are read: before the view on a big screen; on the phone after the
 *  bottom band (the Rail row sits above the tab bar there), so the reading and Tab order match the screen. */
function applySize(size) {
  const was = root.dataset.size;
  root.dataset.size = size;
  const chrome = $("chrome"), stage = $("stage"), foot = $("foot");
  if (size === "phone") { if (chrome.previousElementSibling !== foot) foot.after(chrome); }
  else if (chrome.nextElementSibling !== stage) stage.before(chrome);
  if (was && was !== size && root.hasAttribute("data-ready")) {
    if (size === "phone" && store.state.ui.ambient) store.setUi({ ambient: false });  // no ambient screen on a phone
    store.setUi({ size });   // views that arrange themselves by size redraw
    router.refresh();
  }
}

function setLook() {
  const theme = params.get("theme");
  if (theme) root.dataset.theme = forcedTheme(theme);
  const motion = params.get("motion");
  if (motion) root.dataset.motion = motion;
  sizeFixed = !!params.get("size");
  applySize(params.get("size") || autoSize());
  const follow = () => { if (!sizeFixed) applySize(autoSize()); };
  PHONE.addEventListener("change", follow);
  LAPTOP.addEventListener("change", follow);
  document.addEventListener("visibilitychange", () => root.toggleAttribute("data-hidden", document.hidden));
}

/** The state of the orb he can see. Where the standby sphere is up (the resting screen, the empty Stage) it
 *  stands by whenever it has nothing else to say, so the status line says "Standby", not "Listening" under a
 *  standby sphere (film review S2). The awake calm home shows the white rings (HUD v3 §14), so it says
 *  "Listening". Elsewhere it is orbView()'s state. */
function shownOrbState(s, view = orbView(s), { stageWindow = STAGE_WINDOW, path = router.current.path } = {}) {
  if (view.state !== "idle") return view.state;
  const bigOrb = stageWindow ? !(s.windows || []).length : path === "/now" && !!s.ui?.ambient;
  return bigOrb ? "standby" : view.state;
}

/** Keep the shell (tabs, status line, corner orb, caption, chips, toasts) in step with the store. */
function syncShell(s) {
  const pending = s.approvals.filter((a) => a.status === "pending").length;
  Object.assign($("tabs"), { tabs: TABS, current: router.current.tab, badge: pending });
  const view = orbView(s), shown = shownOrbState(s, view);
  Object.assign($("status"), { orb: shown === s.orb.state ? s.orb : { ...s.orb, state: shown }, settings: s.settings, online: s.ui.online });
  showOrb($("orb"), s);  // standby when nobody is here, an alert for anything critical, the right wake beat
  $("caption").caption = s.caption;
  $("jobs").jobs = s.jobs;
  $("toasts").toasts = s.toasts;
  $("demo-chip").hidden = s.mode !== "demo";
  $("command-bar").hidden = false;
  root.toggleAttribute("data-ambient", !!s.ui.ambient);
  root.dataset.orb = view.state;
}

function wireEvents() {
  // Components never call the backend themselves: they emit jv-act / jv-nav and the shell does the rest.
  document.addEventListener("jv-act", async (e) => {
    const { action, target, args } = e.detail;
    if (action === "dismiss-toast") { store.set({ toasts: store.state.toasts.filter((t) => t.id !== target) }); return; }
    if (action === "open" && target.startsWith("/")) { router.go(target); return; }
    if (action === "open") {  // "Open it" on a file with a PDF work thread: the hub's reader, at his resume point
      const thread = store.state.threads.find((t) => t.kind === "pdf" && (t.ref === target || t.id === target));
      if (thread) { router.go(`/read/${thread.id}`); return; }
    }
    if (action === "shortcuts") { showShortcuts(); return; }
    if (action === "search") { $("command-bar").open(); return; }
    if (action === "ask" && args?.text) {
      // typed window commands work like the spoken ones: "close that", "clear the screen", "bigger", "keep that up"
      const cmd = windowCommand(args.text, store.state.windows);
      if (cmd) {  // then show the windows, where they are on this screen (the Stage shows its own)
        await bridge.act(cmd.action, cmd.target, cmd.args);
        if (router.current.path !== "/now" && !STAGE_WINDOW && windowsHere(store.state)) router.go("/now");
        return;
      }
    }
    const result = await bridge.act(action, target, args);
    if (result && result.ok === false && result.message) {
      store.apply({ v: 1, type: "toast", ts: store.now().toISOString(), data: { id: `t-err-${Date.now()}`, kind: "error", text: result.message, ttl_ms: 6000 } });
    }
  });
  document.addEventListener("jv-nav", (e) => router.go(e.detail.path));
  // clicking the docked orb brings back the full view: the big orb and the clock (HUD v2 §4)
  // (not on the Stage: its orb stays docked while windows are up, and it rests by itself when they are put away)
  $("orb").addEventListener("jv-orb-open", () => { if (!STAGE_WINDOW && !["phone", "strip"].includes(root.dataset.size)) rest(); });
  router.onChange(() => syncShell(store.state));
}

/** A new version was put on this laptop: reload once Jarvis is quiet, so the hub never keeps running old code
 *  (v0.11.2: after v0.11.0 the open page still had the old orb until someone refreshed it). */
async function watchVersion() {
  const get = async () => {
    try { return (await (await fetch("/api/health", { cache: "no-store" })).json()).version || null; } catch { return null; }
  };
  const loaded = await get();
  if (!loaded) return;
  setInterval(async () => {
    const now = await get();
    const quiet = ["idle", "standby"].includes(store.state.orb?.state || "idle");
    const typing = document.activeElement?.matches?.("input, textarea, [contenteditable]");
    if (now && now !== loaded && quiet && !typing) location.reload();
  }, 30_000);
}

async function boot() {
  setLook();
  await Promise.all([import("../components/index.js"), import("../views/index.js")]);
  const scene = sceneName ? getScene(sceneName) : null;
  let state;
  try {
    state = await bridge.loadState({ scene: !!sceneName });
  } catch (err) {
    $("stage").innerHTML = `<jv-notice kind="error" heading="Jarvis isn't answering" text="Start the hub again, or check that Jarvis is running on Laptop B. This window will keep trying."></jv-notice>`;
    setTimeout(() => location.reload(), 5000);
    return;
  }
  if (sceneName) {
    if (scene?.size && !params.get("size")) { sizeFixed = true; applySize(scene.size); }
    scene?.patch?.(state);
    root.dataset.scene = sceneName;
  }
  store.load(state, { frozen: !!sceneName });
  if (!sceneName) watchVersion();
  startTheme({ live: !sceneName });
  wireEvents();
  startKeys();
  startA11y();
  // a demo restart (or a reconnect) asks every window to reload its state
  store.onEvent(async (event) => {
    if (event.type === "nav.go" && event.data?.reload) { try { store.load(await bridge.loadState()); } catch { /* the stream will catch us up */ } }
  });
  store.subscribe(syncShell);
  syncShell(store.state);

  if (sceneName && !scene) {
    $("stage").innerHTML = `<jv-notice kind="empty" heading="No scene called “${sceneName.replace(/[<>&"]/g, "")}”" text="Scenes: ${sceneNames().join(", ")}"></jv-notice>`;
  } else if (scene?.render) {
    root.dataset.gallery = "";
    scene.render($("stage"), state);
  } else if (STAGE_WINDOW && !sceneName) {
    window.name = "jarvis-stage";
    // landmarks say which window this is, and the docked orb sits in the bottom band's contentinfo (a11y NICE 13);
    // the dock is position: fixed, so moving it doesn't move it on screen
    $("stage").setAttribute("aria-label", "Jarvis Stage");
    $("foot").append($("dock"));
    router.pin("/stage", (path) => focusHub(path));  // a link on the Stage opens in the hub
    router.start($("stage"), "/stage");
  } else {
    router.start($("stage"), scene?.path || (root.dataset.size === "strip" ? "/strip" : null));
  }
  if (!STAGE_WINDOW || sceneName) {
    const small = ["phone", "strip"].includes(root.dataset.size);
    startPresence({ live: !sceneName, ambientAtStart: !sceneName && !small });  // presence checks the size as it is, every tick
  }
  if (!sceneName && !STAGE_WINDOW) {
    // the hub: the Stage (a second window) shows what is pushed, so the hub's own window clock only docks
    // windows when they are on this screen ("On the hub", or the phone); and app.py hears what decides the Stage.
    // Rule: the hub never docks a window the Stage is showing (the Stage keeps that window's 60 s clock itself).
    // It belongs with the clock in core/presence.js (windowClock); this wrapper stays here until presence.js
    // owns it (N9 review note), so don't add a second copy of the rule there or here.
    window.name = "jarvis-hub";
    const dockHere = windowClock.dock;
    windowClock.dock = (id) => { if (windowsHere(store.state)) dockHere(id); };
    startStageSync();
  }
  if (!sceneName) connect();
  window.__jarvis = { store, router, bridge, popped, scenes: sceneNames, ready: true };
  root.dataset.ready = "";
}

boot();
