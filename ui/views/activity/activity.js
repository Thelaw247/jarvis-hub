// Activity (V04): receipts. "Waiting for you" is at the top (every write that needs a yes, plus the ones he
// asked to change, shown as "Changing…"), then the timeline of what Jarvis did, newest first, each with Undo
// and how long it still works, with his "no"s as quiet rows; then what it held back and why.
// Focus never drops to <body>: after Yes it lands on the new receipt, after No on the quiet row, after
// Change it on the "Changing…" card, after Undo on the undone row; otherwise the next card or row, or the h1.
// Saying yes (here, in a window or by voice) shows a receipt with Undo in a toast: what was done, in plain past
// tense ("Added 9 study blocks to your Google Calendar this week"), never a jingle like "Booked." and never
// system-speak like "… · Done" (HUD v2 §9.2, §9.3).
// Night HUD (N5b): panel headings are kickers ("WAITING // 1", "RECEIPTS // 5", "HELD BACK // 1"); approval cards
// lead with the amber "your yes" square; receipts are an instrument log with Undo; declines are quiet rows.
import { asDate, css, html, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const FILTERS = [["all", "All"], ["calendar", "Calendar"], ["files", "Files"], ["messages", "Messages"], ["memory", "Memory"], ["tree", "Life Map"], ["skills", "Skills"]];
const CATEGORIES = FILTERS.slice(1).map(([id]) => id);
const PAGE = 6;
const WAIT_MS = 2500;   // how long focus waits for the hub to confirm an answer
const STALE_MS = 6000;  // an answer older than this no longer moves focus

const localIso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 19);  // hub times are local

const PAST = { Adds: "Added", Moves: "Moved", Opens: "Opened", Books: "Booked", Sends: "Sent", Sets: "Set", Saves: "Saved", Creates: "Created",
  Removes: "Removed", Updates: "Updated", Turns: "Turned", Files: "Filed", Renames: "Renamed", Starts: "Started", Keeps: "Kept", Puts: "Put" };
/** The receipt for a yes, as a person would say it: the first thing that changed, in the past tense
    ("Adds 9 study blocks…" → "Added 9 study blocks…"). When the hub didn't say what changed, the thing's name. */
export const receiptText = (row) => {
  const did = String(row.result || "").replace(/^Done\.\s*/, "").replace(/\.$/, "");
  const [first, ...rest] = did.split(" ");
  return PAST[first] && rest.length ? [PAST[first], ...rest].join(" ") : row.what;
};

// ---- what happened to his answers (kept for the whole session, whichever view is open) -----------------
const answeredAt = new Map();  // approval id -> time he answered (from the event)
const awaiting = new Map();    // approval title -> { id, category, at }: said yes, receipt not here yet
store.onEvent((event) => {
  const d = event.data || {};
  if (event.type === "approval.resolved") {
    answeredAt.set(d.id, event.ts || localIso(store.now()));
    const a = store.byId("approvals", d.id);
    if (d.status === "approved" && a) awaiting.set(a.title, { id: a.id, category: a.category || "calendar", at: performance.now() });
  }
  if (event.type === "activity.added" && d.kind === "done" && !d.undone && awaiting.has(d.what)) {
    const yes = awaiting.get(d.what);
    awaiting.delete(d.what);
    if (performance.now() - yes.at > 15000) return;
    const toast = { id: `t-yes-${yes.id}`, kind: "success", text: receiptText(d), ttl_ms: 8000 };
    if (d.undo) toast.action = { label: `Undo (${d.undo.label})`, action: "undo", target: d.id };
    queueMicrotask(() => store.apply({ v: 1, type: "toast", ts: localIso(store.now()), data: toast }));
  }
});

/** A "no" as a quiet receipt, for a decline the hub sent no receipt for (the hub's own has the same id). */
const declinedRow = (a) => ({
  id: `declined-${a.id}`, ts: answeredAt.get(a.id) || a.asked, kind: "done", what: a.title,
  why: "You said no. Nothing was changed.", category: CATEGORIES.includes(a.category) ? a.category : "calendar",
});

class ActivityView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.filter = "all"; this.limit = PAGE; this.intent = null; this._prev = null;
    this.stop = store.subscribe((_s, keys) => { if (keys.has("actions") || keys.has("approvals")) this.update(); });
    this.addEventListener("click", (e) => {
      const f = e.target.closest("[data-filter]");
      if (f) { this.filter = f.dataset.filter; this.limit = PAGE; this.update(); }
      if (e.target.closest("[data-more]")) { this.limit += PAGE; this.update(); }
    });
    this.addEventListener("jv-act", (e) => {
      const { action, target } = e.detail;
      if (action === "filter-all") {  // "Show all" in the filtered-empty notice stays in this view
        e.stopPropagation(); this.filter = "all"; this.limit = PAGE; this._prev = { key: "f-all", at: performance.now() }; this.update(); return;
      }
      if (!["approve", "decline", "change", "undo"].includes(action)) return;
      // remember what he just answered so focus can follow it once the hub confirms
      this.intent = { action, target, title: store.byId("approvals", target)?.title, index: this._waiting?.findIndex((x) => x.id === target) ?? 0, at: performance.now() };
    });
  }
  teardown() { this.stop?.(); clearTimeout(this._recheck); }

  render() {
    this._prev = this._focusNow();
    const s = store.state, now = store.now();
    const pending = s.approvals.filter((a) => a.status === "pending");
    const waiting = s.approvals.filter((a) => a.status === "pending" || a.status === "changed");
    const match = (a) => this.filter === "all" || a.category === this.filter;
    const declined = s.approvals.filter((a) => a.status === "declined" && !s.actions.some((x) => x.id === `declined-${a.id}`)).map(declinedRow);
    const allDone = [...s.actions.filter((a) => a.kind === "done"), ...declined].sort((x, y) => asDate(y.ts) - asDate(x.ts));
    const done = allDone.filter(match);
    const held = s.actions.filter((a) => a.kind === "held" && match(a));
    this._waiting = waiting.slice(0, 4); this._done = done.slice(0, this.limit); this._held = held.slice(0, 4);
    this._now = now;
    const head = html`<header class="jv-view__head">
        <nav class="jv-crumbs" aria-label="Where you are"><a href="#/now" data-nav="/now" data-key="crumb-now">Now</a><span aria-hidden="true">›</span><span aria-current="page">Activity</span></nav>
        <h1 tabindex="-1">Activity</h1><p class="jv-view__sub">Everything Jarvis did, and what's waiting for you. <a href="#/activity/tasks" data-nav="/activity/tasks" data-key="tasks">Claude tasks</a></p></header>`;
    if (!waiting.length && !allDone.length && !s.actions.length) {  // a brand-new day: one plain card, one action
      return html`<div class="jv-view">${head}
        <jv-notice kind="empty" heading="Nothing yet today" text="When Jarvis does something, its receipt shows up here with an Undo. Anything that needs your yes waits at the top." action-label="See what Jarvis can do" action="open" target="/controls"></jv-notice></div>`;
    }
    return html`<div class="jv-view">${head}
      <section aria-labelledby="act-wait"><h2 id="act-wait" class="jv-view__kicker"><span class="jv-kicker">Waiting for you</span>${pending.length ? html`<span class="jv-view__count jv-view__count--waiting">${pending.length}</span>` : ""}</h2>
        ${waiting.length ? html`<div class="jv-activity__waiting">${this._waiting.map((a, i) => html`<jv-window heading="${a.status === "changed" ? "Changing" : "Needs your yes"}" class="jv-activity__approval"><jv-approval-card data-i="${i}" data-id="${a.id}"></jv-approval-card></jv-window>`)}</div>`
          : html`<p class="jv-muted jv-activity__none">Nothing waiting for you. When Jarvis needs a yes before it changes something, it shows up here.</p>`}
      </section>
      <section class="jv-sheet" aria-labelledby="act-done">
        <div class="jv-activity__bar"><h2 id="act-done" class="jv-view__kicker"><span class="jv-kicker">What Jarvis did // ${done.length}</span></h2>
          ${allDone.length ? html`<div class="jv-chips" role="group" aria-label="Filter by kind">${FILTERS.map(([id, label]) => html`<button type="button" class="jv-chip" data-filter="${id}" aria-pressed="${this.filter === id ? "true" : "false"}" data-key="f-${id}">${label}</button>`)}</div>` : ""}</div>
        ${this._done.length ? html`<div class="jv-activity__list">${this._done.map((a, i) => html`<jv-action-row data-kind="done" data-i="${i}" data-id="${a.id}" ${a.id.startsWith("declined-") ? html`quiet` : ""}></jv-action-row>`)}</div>
          ${done.length > this.limit ? html`<p><button type="button" class="jv-btn jv-btn--small" data-more data-key="more">Show ${Math.min(PAGE, done.length - this.limit)} more</button></p>` : ""}`
          : allDone.length ? html`<jv-notice kind="empty" heading="Nothing of this kind yet" text="Everything else is under All." action-label="Show all" action="filter-all"></jv-notice>`
          : html`<jv-notice kind="empty" heading="Nothing done yet today" text="Receipts appear here as Jarvis does things, each with an Undo."></jv-notice>`}
      </section>
      ${this._held.length ? html`<section class="jv-sheet jv-activity__held" aria-labelledby="act-held"><h2 id="act-held" class="jv-view__kicker"><span class="jv-kicker">Held back // ${held.length}</span></h2>
        <p class="jv-muted">Things Jarvis chose not to interrupt you with.</p>
        <div class="jv-activity__list">${this._held.map((a, i) => html`<jv-action-row data-kind="held" data-i="${i}" data-id="${a.id}"></jv-action-row>`)}</div></section>` : ""}
    </div>`;
  }

  rendered() {
    const now = this._now;
    this.querySelectorAll("jv-approval-card").forEach((c) => Object.assign(c, { approval: this._waiting[c.dataset.i], now }));
    this.querySelectorAll("jv-action-row").forEach((r) => Object.assign(r, { action: (r.dataset.kind === "held" ? this._held : this._done)[r.dataset.i], now }));
    queueMicrotask(() => this._placeFocus());  // the cards and rows draw in a microtask; place focus after them
  }

  // ---- focus -------------------------------------------------------------------------------------------
  /** Where focus is now, as something that survives a redraw (host id + data-key). */
  _focusNow() {
    const el = document.activeElement;
    if (!el || el === document.body) return this._prev && performance.now() - this._prev.at < STALE_MS ? this._prev : null;  // lost in a recent redraw: keep what we knew
    if (!this.contains(el)) return null;
    return { id: el.closest("[data-id]")?.dataset.id || null, key: el.dataset?.key || null, h1: el.tagName === "H1", at: performance.now() };
  }
  _article(host) { return host?.querySelector(".jv-action-row, .jv-approval-card"); }
  _try(el) {
    if (!el || !el.isConnected) return false;
    el.focus();
    return document.activeElement === el;
  }
  _fallback(index = 0) {
    const cards = [...this.querySelectorAll("jv-approval-card")];
    if (cards.length && this._try(this._article(cards[Math.min(Math.max(index, 0), cards.length - 1)]))) return;
    if (this._try(this.querySelector(".jv-action-row"))) return;
    this._try(this.querySelector("h1"));
  }
  _placeFocus() {
    if (!this.isConnected) return;
    const active = document.activeElement;
    const inside = active && active !== document.body && this.contains(active);
    const it = this.intent;
    if (it && performance.now() - it.at > STALE_MS) this.intent = null;
    else if (it) {
      const age = performance.now() - it.at;
      const q = (sel) => this.querySelector(sel);
      let target = null, settled;
      if (it.action === "undo") {
        const r = store.byId("actions", it.target);
        settled = !r || r.undone;
        if (r?.undone) target = q(`jv-action-row[data-id="${CSS.escape(it.target)}"]`);
      } else {
        const a = store.byId("approvals", it.target);
        settled = !a || a.status !== "pending";
        if (a?.status === "approved") {
          const row = this._done.find((x) => x.what === it.title && !x.undone && !x.id.startsWith("declined-"));
          if (row) target = q(`jv-action-row[data-id="${CSS.escape(row.id)}"]`);
          else if (age < WAIT_MS) settled = false;  // the receipt is on its way
        } else if (a?.status === "declined") target = q(`jv-action-row[data-id="declined-${CSS.escape(it.target)}"]`);
        else if (a?.status === "changed") target = q(`jv-approval-card[data-id="${CSS.escape(it.target)}"]`);
      }
      if (!settled && age < WAIT_MS) {  // wait for the hub; look again when it answers or the wait is over
        clearTimeout(this._recheck);
        this._recheck = setTimeout(() => this._placeFocus(), WAIT_MS - age + 20);
        if (!inside) this._restore();
        return;
      }
      this.intent = null;
      if (settled) {
        if (!this._try(this._article(target))) this._fallback(it.index);
        return;
      }
      // still not answered after the wait: it didn't go through (the shell said why); leave focus be
    }
    if (!inside) this._restore();
  }
  _restore() {
    const p = this._prev;
    if (!p) return;
    if (p.h1) { this._try(this.querySelector("h1")); return; }
    const host = p.id ? this.querySelector(`[data-id="${CSS.escape(p.id)}"]`) : this;
    if (!host) { this._fallback(); return; }
    if (p.key && this._try(host.querySelector(`[data-key="${CSS.escape(p.key)}"]`))) return;
    if (!this._try(this._article(host)) && p.id) this._fallback();
  }
}
ActivityView.define("jv-view-activity");

registerScene("activity", { path: "/activity", about: "One approval waiting, today's receipts, one held-back remark" });
registerScene("activity-clear", { path: "/activity", about: "Nothing waiting", patch: (s) => { s.approvals = []; } });
registerScene("activity-empty", { path: "/activity", about: "A brand-new day", patch: (s) => { s.approvals = []; s.actions = []; } });
registerScene("activity-changing", { path: "/activity", about: "He asked for a change; it stays here as Changing… until Jarvis asks again", patch: (s) => { s.approvals[0].status = "changed"; } });
