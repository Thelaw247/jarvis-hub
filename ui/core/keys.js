// Keyboard and focus (B01). Every place and action has a key; nothing is mouse-only or voice-only.
//   Ctrl+K or /   command bar          1–5   tabs            Esc   close, then back (always safe)
//   ?             this list            L     Life: map/list   M     mute or unmute the mic
// Keys are ignored while typing in a field (except Esc and Ctrl+K). The shortcuts sheet is a small dialog
// that traps focus and returns it where it was.
import { html, radioKey } from "./dom.js";
import { rest } from "./presence.js";
import { router, TABS } from "./router.js";
import { store } from "./store.js";

export const SHORTCUTS = [
  ["Ctrl K  or  /", "Go anywhere, or ask Jarvis"],
  ["1 2 3 4 5", "Now · Today · Life · Activity · Controls"],
  ["Esc", "Close what's open, then go back"],
  ["L", "Life: switch between the map and the list"],
  ["M", "Mute or unmute the mic"],
  ["← → ↑ ↓", "Move around the Life Map or list"],
  ["Enter", "Open the branch · Backspace goes back up"],
  ["?", "Show this list"],
];

let sheet = null;
let returnTo = null;
const typing = (el) => !!el?.closest?.("input, textarea, select, [contenteditable]");
const bar = () => document.getElementById("command-bar");

export function showShortcuts() {
  if (sheet) return;
  returnTo = document.activeElement;
  sheet = document.createElement("div");
  sheet.className = "jv-keys__scrim";
  sheet.innerHTML = String(html`<div class="jv-keys jv-card" role="dialog" aria-modal="true" aria-labelledby="jv-keys-title">
    <h2 id="jv-keys-title">Keyboard shortcuts</h2>
    <dl class="jv-keys__list">${SHORTCUTS.map(([keys, what]) => html`<div><dt><kbd>${keys}</kbd></dt><dd>${what}</dd></div>`)}</dl>
    <p class="jv-muted">Everything here also works by voice and by clicking.</p>
    <p><button type="button" class="jv-btn" data-close>Close</button></p></div>`);
  sheet.addEventListener("click", (e) => { if (e.target === sheet || e.target.closest("[data-close]")) hideShortcuts(); });
  sheet.addEventListener("keydown", (e) => { if (e.key === "Tab") { e.preventDefault(); sheet.querySelector("[data-close]").focus(); } });
  document.body.append(sheet);
  sheet.querySelector("[data-close]").focus();
}
export function hideShortcuts() {
  if (!sheet) return false;
  sheet.remove(); sheet = null;
  returnTo?.focus?.({ preventScroll: true });
  return true;
}

function onKey(e) {
  if (e.defaultPrevented) return;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); hideShortcuts(); bar()?.open(); return; }
  if (e.key === "Escape") {
    if (hideShortcuts()) return;
    if (bar()?.isOpen && !bar().hasAttribute("inline")) { bar().close(); return; }
    if (typing(e.target)) { e.target.blur(); return; }
    const open = document.querySelector("#stage details[open] > summary:focus");
    if (open) { open.parentElement.open = false; return; }
    if (router.current.path === "/now" && !store.state.ui.ambient && !store.state.windows.length && router.depth <= 1) { rest(); return; }
    router.back();
    return;
  }
  if (mod || e.altKey || typing(e.target) || sheet || bar()?.isOpen) return;
  if (e.key === "/") { e.preventDefault(); bar()?.open(); }
  else if (e.key === "?") { e.preventDefault(); showShortcuts(); }
  else if (/^[1-5]$/.test(e.key)) { e.preventDefault(); router.go(TABS[Number(e.key) - 1].path); }
  else if (e.key.toLowerCase() === "l" && router.current.tab === "life") { e.preventDefault(); document.dispatchEvent(new CustomEvent("jv-life-toggle")); }
  else if (e.key.toLowerCase() === "m") {
    e.preventDefault();
    const muted = store.state.settings.muted || store.state.orb.state === "muted";
    document.dispatchEvent(new CustomEvent("jv-act", { detail: { action: muted ? "unmute" : "mute", target: "mic" } }));
  }
}

export function startKeys() {
  document.addEventListener("keydown", radioKey);  // radio groups: arrows move and choose (before the view keys)
  document.addEventListener("keydown", onKey);
  // after a view change, focus moves to the main area so keyboard and screen-reader users land in the new view,
  // unless the view has already put focus somewhere inside it (a deep link to a setting, a Life Map node)
  let first = true;
  router.onChange(() => {
    if (first) { first = false; return; }
    if (bar()?.isOpen && !bar().hasAttribute("inline")) return;
    const stage = document.getElementById("stage");
    if (stage && stage !== document.activeElement && stage.contains(document.activeElement)) return;
    stage?.focus({ preventScroll: true });
  });
}
