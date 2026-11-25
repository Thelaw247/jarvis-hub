// What the orb shows, worked out from the store (contracts v2, note 13). One place, so the corner orb, the big
// ambient orb, the phone and the strip always agree.
//   state  the orb_state's own state, except: idle with nobody here (presence.here === false) is standby
//   alert  the orb_state's own alert, else "crit" while a thing on the Rail is critical (never a tier-2 thing
//          when others may see the screen)
//   wake   on a wake (listening with last_wake): "full" for the first wake of the day or after ≥ 4 h away,
//          "tighten" otherwise; null when the event says nothing (the orb then plays its short default)
import { wakeKind } from "../components/orb/orb-parts.js";
import { store } from "./store.js";

export function orbView(s = store.state, now = store.now()) {
  const orb = s.orb || { state: "idle" };
  const state = orb.state === "idle" && s.presence?.here === false ? "standby" : orb.state;
  const shared = !!(s.presence?.others || s.ui?.ambient);
  const critical = Object.values(s.rail?.slots || {}).some((slot) => (slot.items || []).some((i) => i.state === "critical" && !(shared && i.tier === 2)));
  const alert = orb.alert === "warn" || orb.alert === "crit" ? orb.alert : critical ? "crit" : null;
  const wake = orb.state === "listening" && "last_wake" in orb ? wakeKind(orb.last_wake, now) : null;
  return { state, alert, wake };
}

/** Put the store's orb on a <jv-orb>: the wake beat first (it must be known before the state changes). */
export function showOrb(el, s = store.state) {
  if (!el) return;
  const { state, alert, wake } = orbView(s);
  if (wake) el.setAttribute("wake", wake); else el.removeAttribute("wake");
  if (alert) el.setAttribute("alert", alert); else el.removeAttribute("alert");
  if (el.getAttribute("state") !== state) el.setAttribute("state", state);
  el.orb = s.orb;
}

// ---- back to standby a calm moment after a turn, not the instant he stops (v0.11, his ask) ---------------
/** How long the orb stays awake (white rings out) after it last listened, thought or spoke. */
export const REST_LINGER_MS = 3000;
let lastActive = -1e9;
const lingerTimers = new Map();
/** Call on every draw with the orb's state. True while an idle orb should still look awake; `redraw` is called
 *  once when the moment has passed, so the rings then go back into the sphere (over 500 ms, orb.css). */
export function stillAwake(state, key, redraw, now = performance.now()) {
  if (state !== "idle" && state !== "standby") { lastActive = now; return true; }
  const left = lastActive + REST_LINGER_MS - now;
  clearTimeout(lingerTimers.get(key));
  if (left <= 0) return false;
  lingerTimers.set(key, setTimeout(redraw, left + 30));
  return true;
}
