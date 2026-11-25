// Jarvis's earcons (HUD v2 §7): three original sounds, made by make_sounds.py (nothing from the films). Soft
// and round (F1, his v0.4.1 report: the sounds as windows opened were unpleasant): low sines, ≥ 15 ms attacks,
// no clicks, ~6 dB quieter than before.
//   wake      a soft two-note rise, ≤ 600 ms: only the first wake of the day (with the full wake beat)
//   tick      a soft tick ≤ 60 ms: the non-verbal "heard you" when listening turns into thinking
//   critical  one low tone: alongside a critical alert (Full only)
// Window pushes are silent. What he heard as windows opened was the tick (plus the wake rise on a first wake),
// played ~75 ms before the windows landed, and twice: once by the hub and once by the Stage, two pages with their
// own audio. Now one page sounds (the Stage when it is open, else the hub: a Web Lock), the rise plays once a
// day, and nothing but the tick may sound within ROUTINE_QUIET_MS of a window push or recall.
// play(name) starts a preloaded WebAudio buffer, so a sound begins in well under 10 ms. Sounds sit ~18 dB
// under the voice and drop another 10 dB while Jarvis speaks. Never in quiet hours, never on the strip
// (Laptop A), never in game mode. Levels: Off / Minimal (the default: wake + tick) / Full (+ critical).
import { store } from "../core/store.js";

export const NAMES = ["wake", "tick", "critical"];
export const LEVELS = { off: [], minimal: ["wake", "tick"], full: ["wake", "tick", "critical"] };
export const UNDER_VOICE_DB = -18;  // the voice peaks near 0 dBFS; earcons sit this far under it
export const DUCK_DB = -10;         // extra, while Jarvis is speaking
export const ROUTINE_QUIET_MS = 600;  // after a window push or recall only the "heard you" tick may sound
const LOCK = "jarvis-earcons";      // the one page that sounds (the Stage steals it while it is open)
const WAKE_KEY = "jarvis.earcons.wake-day";  // the day the rise last played, shared by the hub and the Stage

const dbToGain = (db) => 10 ** (db / 20);
const root = document.documentElement;

// The level is the `earcons` setting (Controls › Sound: Off / Minimal / Full; Minimal when it isn't set).
// setEarconLevel() overrides it for this page (tests, a local preview); setEarconLevel(null) lets go.
let forced = null;
export function setEarconLevel(next) { forced = LEVELS[next] ? next : null; }
export const earconLevel = () => forced || (LEVELS[store.state.settings?.earcons] ? store.state.settings.earcons : "minimal");

/** Quiet hours as the settings contract has them ({ on, from: "22:30", to: "07:30" }), crossing midnight. */
export function inQuietHours(q, now) {
  if (!q?.on || !q.from || !q.to) return false;
  const mins = (hhmm) => { const [h, m] = String(hhmm).split(":").map(Number); return h * 60 + (m || 0); };
  const t = now.getHours() * 60 + now.getMinutes(), from = mins(q.from), to = mins(q.to);
  return from <= to ? t >= from && t < to : t >= from || t < to;
}

/** Game mode as the store has it: the now card's moment, or game mode switched on in Controls. */
export const inGame = (s) => s?.now_card?.moment === "game" || s?.settings?.game_mode === "on";

/** Whether a sound may play. Pure, so the rules can be tested without audio.
 *  `pushed`: a window was pushed or recalled within ROUTINE_QUIET_MS (only the tick may sound);
 *  `wokeToday`: the wake rise already played today (it plays on the first wake of the day only). */
export function shouldPlay(name, { level: lv = earconLevel(), quiet = false, game = false, strip = false, pushed = false, wokeToday = false } = {}) {
  if (!NAMES.includes(name) || strip || game || quiet) return false;
  if (pushed && name !== "tick") return false;
  if (name === "wake" && wokeToday) return false;
  return (LEVELS[lv] || LEVELS.minimal).includes(name);
}

/** The day key for the once-a-day rise, on the hub's clock. */
export const dayKey = (now) => `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`;
const store_ = (() => { try { return window.localStorage; } catch { return null; } })();
const wokeToday = (now) => store_?.getItem(WAKE_KEY) === dayKey(now);

// a routine push: no sound rides on it (HUD v2 §7)
let lastPush = -1e9;
store.onEvent?.((e) => { if (e.type === "window.push") lastPush = performance.now(); });  // (a recall is a push too)

function context() {
  const s = store.state, now = store.now();
  return {
    level: earconLevel(),
    quiet: inQuietHours(s.settings?.quiet_hours, now),
    game: inGame(s),
    strip: root.dataset.size === "strip",
    pushed: performance.now() - lastPush < ROUTINE_QUIET_MS,
    wokeToday: wokeToday(now),
  };
}

// ---- one page sounds -----------------------------------------------------------------------------------
// The hub and the Stage are two windows of the same app, each with its own audio: without this every earcon
// played twice, a few ms apart. The page holding the lock sounds; the Stage takes it while it is open (it is
// the screen Jarvis talks on) and the hub gets it back when the Stage closes. No Web Locks: every page sounds.
let owner = typeof navigator === "undefined" || !navigator.locks;
let claimed = false;
function claim(steal = root.dataset.window === "stage" || new URLSearchParams(location.search).get("window") === "stage") {
  if (!navigator.locks) return;
  claimed = true;
  navigator.locks.request(LOCK, steal ? { steal: true } : {}, () => { owner = true; return new Promise(() => {}); })
    .catch(() => { owner = false; claim(false); });  // stolen by the Stage: wait in line for it to close
}
/** Whether this page is the one that sounds (for tests and Under the hood). */
export const soundOwner = () => owner;

// ---- audio --------------------------------------------------------------------------------------------
let ctx = null, out = null;
const buffers = new Map();
const lastPlayed = new Map();
const files = new Map();  // name → Promise<ArrayBuffer>, fetched once the page is idle

function fetchAll() {
  for (const name of NAMES) {
    if (!files.has(name)) files.set(name, fetch(new URL(`./${name}.wav`, import.meta.url)).then((r) => (r.ok ? r.arrayBuffer() : null)).catch(() => null));
  }
}

/** Create the audio context and decode every sound now, so play() never waits. Safe to call twice. */
export async function preload() {
  if (root.dataset.size === "strip" || typeof AudioContext === "undefined") return false;
  if (!claimed) claim();
  fetchAll();
  if (!ctx) {
    ctx = new AudioContext({ latencyHint: "interactive" });
    out = ctx.createGain();
    out.gain.value = dbToGain(UNDER_VOICE_DB);
    out.connect(ctx.destination);
  }
  await Promise.all(NAMES.map(async (name) => {
    if (buffers.has(name)) return;
    const data = await files.get(name);
    if (data) buffers.set(name, await ctx.decodeAudioData(data.slice(0)));
  }));
  return buffers.size === NAMES.length;
}

/** Play an earcon if the rules allow it. Returns { played, ms } (ms = time to start the sound). */
export function play(name, { force = false } = {}) {
  const t0 = performance.now();
  if (!force && (!owner || !shouldPlay(name, context()))) return { played: false, ms: 0 };
  if (t0 - (lastPlayed.get(name) || -1e9) < 200) return { played: false, ms: 0 };  // two orbs, one sound
  const buf = buffers.get(name);
  if (!ctx || !buf) { preload(); return { played: false, ms: 0 }; }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  lastPlayed.set(name, t0);
  if (name === "wake" && !force) store_?.setItem(WAKE_KEY, dayKey(store.now()));
  const speaking = store.state.orb?.state === "speaking";
  const src = ctx.createBufferSource();
  src.buffer = buf;
  if (speaking) {
    const duck = ctx.createGain();
    duck.gain.value = dbToGain(DUCK_DB);
    src.connect(duck).connect(out);
  } else src.connect(out);
  src.start();
  return { played: true, ms: performance.now() - t0 };
}

// Browsers start audio only after a gesture (the Windows app can lift that for Laptop B): wake the context on
// the first click or key. Preload when the page is idle, never on the strip.
const unlock = () => { preload().then(() => ctx?.state === "suspended" && ctx.resume().catch(() => {})); };
addEventListener("pointerdown", unlock, { once: true, capture: true });
addEventListener("keydown", unlock, { once: true, capture: true });
(window.requestIdleCallback || ((fn) => setTimeout(fn, 1500)))(() => { if (root.dataset.size !== "strip") preload().catch(() => {}); });
