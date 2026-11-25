// Screen-reader live regions (B05). What Jarvis says, shows and asks is spoken to assistive tech too:
//   polite     spoken captions, short notices, a window appearing, the mic going on or off
//   assertive  something waiting for his yes, and the hub going offline
// The visual caption and toasts stay aria-hidden / role-less so nothing is read twice.
//
// Messages never cut each other off: anything said within BATCH_MS is merged into one announcement, and a
// region keeps each announcement for at least HOLD_MS before the next one replaces it (later messages wait
// and are merged). "Showing X" is skipped on the strip, which never shows windows.
import { store } from "./store.js";

export const BATCH_MS = 120;
export const HOLD_MS = 1200;

const regions = {};
const queues = { polite: [], assertive: [] };
const timers = {};
const lastAt = { polite: -Infinity, assertive: -Infinity };

function region(level) {
  const el = document.createElement("div");
  el.className = "jv-sr";
  el.setAttribute("aria-live", level);
  el.setAttribute("aria-atomic", "true");
  el.id = `jv-live-${level}`;
  document.body.append(el);
  return el;
}

const join = (parts) => parts.map((p) => p.trim()).filter(Boolean)
  .map((p) => (/[.!?…”"]$/.test(p) ? p : `${p}.`)).join(" ").replace(/\.{2,}/g, ".");

function flush(level) {
  timers[level] = null;
  const el = regions[level], parts = [...new Set(queues[level])];
  queues[level] = [];
  if (!el || !parts.length) return;
  lastAt[level] = performance.now();
  el.textContent = "";  // clearing first makes a repeat announce again
  requestAnimationFrame(() => { el.textContent = join(parts); });
}

/** Say something to screen readers. Close-together messages are merged; none replaces another too soon. */
export function announce(text, level = "polite") {
  if (!text || !regions[level]) return;
  queues[level].push(String(text));
  if (timers[level]) return;
  const wait = Math.max(BATCH_MS, lastAt[level] + HOLD_MS - performance.now());
  timers[level] = setTimeout(() => flush(level), wait);
}

const onStrip = () => document.documentElement.dataset.size === "strip" || !!document.querySelector("#stage jv-view-strip");

export function describe(event, state) {
  const d = event.data || {};
  switch (event.type) {
    case "caption.show":
      if (!d.text) return null;  // an empty line is the "clear the caption" signal, not something to read out
      return [/^[“"]/.test(d.text) ? `You said: ${d.text}` : join([`Jarvis: ${d.text}`, d.source ? `Source: ${d.source.label}` : ""]), "polite"];
    case "toast": return d.kind === "error" ? null : [join([d.text || "", d.action ? `${d.action.label} is available` : ""]), "polite"];
    case "approval.pending": return [`Waiting for your yes: ${d.title}. ${(d.consequences || [])[0] || ""}. Open Activity to answer.`, "assertive"];
    case "approval.resolved": return [{ approved: "Approved.", declined: "Declined.", changed: "Change requested.", expired: "That offer ran out." }[d.status] || "", "polite"];
    case "window.push":
      if (onStrip()) return null;  // the strip never shows windows, so it never says "Showing …"
      return state.windows.some((w) => w.id === d.id && w !== d) && d.pinned !== undefined ? null : [`Showing ${d.title}.`, "polite"];
    case "orb.state":
      if (d.state === "offline") return [`Jarvis is offline. ${d.message || ""}`, "assertive"];
      if (d.state === "muted") return ["Microphone off.", "polite"];
      return null;
    default: return null;
  }
}

export function startA11y() {
  regions.polite = region("polite"); regions.assertive = region("assertive");
  let lastOrb = store.state.orb.state;
  store.onEvent((event) => {
    if (event.type === "orb.state") {
      const was = lastOrb; lastOrb = event.data.state;
      if (was === event.data.state) return;
      if (was === "muted" && event.data.state !== "offline") { announce("Microphone on.", "polite"); return; }
    }
    const said = describe(event, store.state);
    if (said && said[0]) announce(said[0], said[1]);
  });
}
