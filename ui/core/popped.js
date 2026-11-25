// Windows he has pulled out of the hub (v0.17.0, his ask of 2026-11-21: "pull them off of the entire window and
// it would open another Jarvis hub thing, without the orb or voice, just a window to hold more windows").
// One window by default: what Jarvis pulls up shows on the hub. A window he drags off the hub's edge (or sends
// with its "own window" button) is "out": the hub stops drawing it and the holder (the second window, the same
// page at ?window=stage) draws it instead. Dragged off the holder, or the holder closed, it is back on the hub.
//  - This is where a window is shown on THIS laptop, not a fact about the window, so it lives here (the browser's
//    own storage, shared by the hub and the holder) and never goes to jarvis-core or the other laptop.
//  - Both windows hear a change at once (the browser's "storage" event); a slow check every 1.5 s covers a
//    webview that doesn't deliver it.
const KEY = "jv-popped";
const CHECK_MS = 1500;
const listeners = new Set();
let memory = [];  // used as-is where the browser gives no storage (a private window): then it is this page only
let last = "";

let pretend = null;  // scenes: a fixed set for this page only, never stored

function read() {
  if (pretend) return pretend;
  try { const raw = localStorage.getItem(KEY); const ids = raw ? JSON.parse(raw) : []; return Array.isArray(ids) ? ids.filter((x) => typeof x === "string") : []; }
  catch { return memory; }
}
function write(ids) {
  if (pretend) { pretend = ids; tell(); return; }
  memory = ids;
  try { if (ids.length) localStorage.setItem(KEY, JSON.stringify(ids)); else localStorage.removeItem(KEY); } catch { /* memory only */ }
  tell();
}
function tell() {
  const now = JSON.stringify(read());
  if (now === last) return;
  last = now;
  for (const fn of [...listeners]) fn(new Set(read()));
}

export const popped = {
  /** → Set of window ids shown in the holder instead of the hub. */
  ids: () => new Set(read()),
  has: (id) => read().includes(id),
  /** Send a window to the holder. */
  out(id) { const ids = read(); if (id && !ids.includes(id)) write([...ids, id]); },
  /** Bring a window back to the hub. */
  in(id) { const ids = read(); if (ids.includes(id)) write(ids.filter((x) => x !== id)); },
  /** Everything back on the hub (the holder was closed). */
  clear() { if (read().length) write([]); },
  /** Forget windows that are gone (closed, docked into the Rail). `alive`: the ids on state.windows. */
  prune(alive) { const ids = read(), keep = ids.filter((id) => alive.has(id)); if (keep.length !== ids.length) write(keep); },
  /** Scenes and tests: this page acts as if exactly these were out, and stores nothing. */
  pretend(ids) { pretend = [...ids]; tell(); },
  /** fn(Set) on every change, from this window or the other one. → stop() */
  subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
};

last = JSON.stringify(read());
addEventListener("storage", (e) => { if (e.key === KEY || e.key === null) tell(); });
setInterval(tell, CHECK_MS);
