// Calm messages (plan §3: errors say what to do next and never blame; empties are friendly).
//   <jv-notice kind="info|notice|error|empty" heading="…" text="…" action-label="…" action="…" target="…">
//   <jv-toast>.toast = toast contract      <jv-toasts>.toasts = [toast]  (at most 2; each leaves by itself, but
//   waits while hovered or focused; Esc dismisses; focus goes back where it was)
import { css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const ICON = { info: "spark", success: "check", notice: "alert", error: "alert", empty: "leaf" };

class Notice extends Jv {
  static attrs = ["kind", "heading", "text", "action-label", "action", "target"];
  render() {
    const kind = ICON[this.getAttribute("kind")] ? this.getAttribute("kind") : "info";
    const a = (n) => this.getAttribute(n);
    return html`<div class="jv-notice jv-notice--${kind}" role="${kind === "error" ? "alert" : "note"}">
      <span class="jv-notice__icon">${icon(ICON[kind])}</span>
      <div class="jv-notice__text">
        ${a("heading") ? html`<h3 class="jv-notice__heading">${a("heading")}</h3>` : ""}
        ${a("text") ? html`<p>${a("text")}</p>` : ""}
        ${a("action-label") ? html`<button type="button" class="jv-btn jv-btn--small jv-notice__action" data-act="${a("action") || "open"}" data-target="${a("target") || ""}" data-key="action">${a("action-label")}</button>` : ""}
      </div></div>`;
  }
}
Notice.define("jv-notice");

class Toast extends Jv {
  static props = ["toast"];
  render() {
    const t = this.toast;
    if (!t) return "";
    return html`<div class="jv-toast jv-toast--${t.kind}" ${t.kind === "error" ? html`role="alert"` : ""}>
      ${icon(ICON[t.kind] || "spark")}<span class="jv-toast__text">${t.text}</span>
      ${t.action ? html`<button type="button" class="jv-link" data-act="${t.action.action}" data-target="${t.action.target}" ${t.action.args ? html`data-args="${JSON.stringify(t.action.args)}"` : ""} data-key="act">${t.action.label}</button>` : ""}
      <button type="button" class="jv-toast__close" data-act="dismiss-toast" data-target="${t.id}" data-key="close">${icon("close")}<span class="jv-sr">Dismiss: ${t.text}</span></button>
    </div>`;
  }
}
Toast.define("jv-toast");

/** Where focus goes when the toast it was in leaves: back where it came from (or, if a redraw replaced that
 *  element, its stand-in with the same data-id and data-key), else the view's heading, else the main area. */
export function focusFallback(from) {
  const ok = (el) => el && el.isConnected && el !== document.body && !el.closest("[hidden], [inert]") && el.getClientRects().length;
  const tryFocus = (el) => { if (!ok(el)) return false; el.focus({ preventScroll: true }); return document.activeElement === el; };
  if (from && tryFocus(from.el)) return from.el;
  if (from?.id) {
    const host = document.querySelector(`#stage [data-id="${CSS.escape(from.id)}"]`);
    const twin = host && ((from.key && host.querySelector(`[data-key="${CSS.escape(from.key)}"]`)) || host.querySelector("[tabindex='-1']"));
    if (tryFocus(twin)) return twin;
  }
  const h1 = document.querySelector("#stage h1");
  if (h1 && !h1.hasAttribute("tabindex")) h1.setAttribute("tabindex", "-1");
  if (tryFocus(h1)) return h1;
  const stage = document.getElementById("stage");
  stage?.focus({ preventScroll: true });
  return stage;
}

export const MAX_TOASTS = 2;

/** Short notices that leave on their own (at most two at a time). The timer pauses while a toast is hovered
 *  or has focus (WCAG 2.2.1); Esc dismisses the focused one; using its action dismisses it too. When a
 *  toast that holds focus leaves for any reason, focus goes back where it was before (or the view's h1).
 *  Existing toasts are kept, not re-created, so focus and the entry motion are never disturbed. */
class Toasts extends Jv {
  static props = ["toasts"];
  setup() {
    this.timers = new Map();  // id -> { timer, left, started, hover, focus }
    this.nodes = new Map();   // id -> <jv-toast>
    this.gone = new Set();    // ids already asked to leave
    this.returnTo = null;
    this._focusin = (e) => {
      if (this.contains(e.target)) return;
      const t = e.target;
      this.returnTo = { el: t, id: t.closest?.("[data-id]")?.dataset.id, key: t.dataset?.key };
    };
    document.addEventListener("focusin", this._focusin);
    this.addEventListener("keydown", (e) => {
      const node = e.target.closest?.("jv-toast");
      if (e.key === "Escape" && node) { e.preventDefault(); e.stopPropagation(); this.dismiss(node.dataset.id); }
    });
    this.addEventListener("jv-act", (e) => {  // using a toast's action (e.g. Undo) also sends the toast away
      const node = e.target.closest?.("jv-toast");
      if (node && e.detail.action !== "dismiss-toast") queueMicrotask(() => this.dismiss(node.dataset.id));
    });
  }
  teardown() {
    this.timers.forEach((t) => clearTimeout(t.timer)); this.timers.clear();
    document.removeEventListener("focusin", this._focusin);
  }
  dismiss(id) {
    if (!id || this.gone.has(id)) return;
    this.gone.add(id);
    const t = this.timers.get(id);
    if (t) clearTimeout(t.timer);
    this.timers.delete(id);
    this.emit("jv-act", { action: "dismiss-toast", target: id });
  }
  _start(t) {
    if (!t.ttl_ms || this.timers.has(t.id)) return;
    const entry = { timer: null, left: t.ttl_ms, started: 0, hover: false, focus: false };
    this.timers.set(t.id, entry);
    this._resume(t.id);
  }
  _pause(id) {
    const e = this.timers.get(id);
    if (!e || !e.timer) return;
    clearTimeout(e.timer); e.timer = null;
    e.left = Math.max(0, e.left - (performance.now() - e.started));
  }
  _resume(id) {
    const e = this.timers.get(id);
    if (!e || e.timer || e.hover || e.focus) return;
    e.started = performance.now();
    e.timer = setTimeout(() => this.dismiss(id), Math.max(e.left, 0));
  }
  _hold(id, key, on) {
    const e = this.timers.get(id);
    if (!e) return;
    e[key] = on;
    if (e.hover || e.focus) this._pause(id); else this._resume(id);
  }
  _make(t) {
    const node = document.createElement("jv-toast");
    node.dataset.id = t.id;
    node.addEventListener("pointerenter", () => this._hold(t.id, "hover", true));
    node.addEventListener("pointerleave", () => this._hold(t.id, "hover", false));
    node.addEventListener("focusin", () => this._hold(t.id, "focus", true));
    node.addEventListener("focusout", (e) => { if (!node.contains(e.relatedTarget)) this._hold(t.id, "focus", false); });
    return node;
  }
  render() {
    let box = this.querySelector(":scope > .jv-toasts");
    if (!box) { box = document.createElement("div"); box.className = "jv-toasts"; this.replaceChildren(box); }
    const all = this.toasts || [];
    const list = all.slice(-MAX_TOASTS);
    const keep = new Set(list.map((t) => t.id));
    for (const t of all) if (!keep.has(t.id)) queueMicrotask(() => this.dismiss(t.id));  // older ones make room
    for (const id of [...this.gone]) if (!all.some((t) => t.id === id)) this.gone.delete(id);
    // remove the ones that left, handing focus back if it was inside
    let lostFocus = false;
    for (const [id, node] of this.nodes) {
      if (keep.has(id)) continue;
      if (node.contains(document.activeElement)) lostFocus = true;
      node.remove(); this.nodes.delete(id);
      const e = this.timers.get(id); if (e) clearTimeout(e.timer); this.timers.delete(id);
    }
    for (const t of list) {
      let node = this.nodes.get(t.id);
      if (!node) { node = this._make(t); this.nodes.set(t.id, node); }
      box.append(node);  // keeps order; moving a node that is already in place is a no-op
      if (node.toast !== t) node.toast = t;
      this._start(t);
    }
    if (lostFocus) focusFallback(this.returnTo);
    return null;  // the DOM is managed above
  }
}
Toasts.define("jv-toasts");

const notice = (attrs) => el("jv-notice", {}, attrs);
const toast = (t) => el("jv-toast", { toast: t });
registerGallery("notice", [
  { label: "Empty state", build: () => notice({ kind: "empty", heading: "Nothing waiting for you", text: "When Jarvis needs a yes, it shows up here." }) },
  { label: "Info", build: () => notice({ kind: "info", text: "Jarvis learned 3 things today.", "action-label": "See them", target: "/life/memory" }) },
  { label: "Notice", build: () => notice({ kind: "notice", heading: "Gmail needs you to sign in again", text: "Until then, schedule changes sent by email won't show up.", "action-label": "Open data sources", target: "/controls" }) },
  { label: "Error (says what to do)", build: () => notice({ kind: "error", heading: "Can't reach the hub", text: "Check that Laptop B is on. This window will reconnect on its own." }) },
  { label: "Toast", build: () => toast({ id: "t-1", kind: "info", text: "Jarvis learned 3 things today.", action: { label: "See them", action: "open", target: "/life/memory" } }) },
  { label: "Toast: done", build: () => toast({ id: "t-2", kind: "success", text: "Undone." }) },
  { label: "Toast: problem", build: () => toast({ id: "t-3", kind: "error", text: "That didn't go through. Try again in a moment." }) },
], { about: "Friendly empties, plain errors that say what to do next, and short toasts that leave on their own." });
