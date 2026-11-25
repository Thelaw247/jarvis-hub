// The one rule the store needs about windows (the full window manager is core/windows.js, WP W01):
// at most six on screen, and the Now card is one of them, so at most five pushed windows. When a sixth
// arrives the oldest unpinned one **docks** into its Rail slot (HUD v2 §6.2): it leaves the screen, never
// the hub. Mirrors jarvis_hub/events.py apply_event("window.push").
export const MAX_WINDOWS = 6;
export const MAX_PUSHED = MAX_WINDOWS - 1;

/** The windows on screen after `incoming` arrives (the same id again updates it in place and keeps its spot).
 *  Windows pushed out by it are handed to `onDock(window)` (marked `docked: true`) and are not in the result;
 *  the store folds them into their Rail slot. → the new list */
export function placeWindow(windows, incoming, onDock = () => {}) {
  let next = windows.some((w) => w.id === incoming.id)
    ? windows.map((w) => (w.id === incoming.id ? { ...w, ...incoming } : w))
    : [...windows, incoming];
  while (next.length > MAX_PUSHED) {
    const victim = next.find((w) => !w.pinned) || next[0];
    next = next.filter((w) => w !== victim);
    onDock({ ...victim, docked: true });
  }
  return next;
}

/** placeWindow, returning what docked too. → { windows, docked: [windows that left the screen] } */
export function placeAndDock(windows, incoming) {
  const docked = [];
  return { windows: placeWindow(windows, incoming, (w) => docked.push(w)), docked };
}
