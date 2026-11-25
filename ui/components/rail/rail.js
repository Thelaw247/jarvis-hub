// <jv-rail>: the Rail as Huw's icon row (HUD v3 §14 decision 2; HUD v2 §6.2–6.3). Six fixed slots at the
// bottom centre of every screen (the hub, the ambient screen and the Stage) that track **things, not
// windows**: Your yes · Today · Homework · Messages · Jarvis · Parked. Each slot is a tiny monochrome line
// icon between thin dividers with a small count badge. A slot holding something that wants him shows that
// thing's glance shape as its badge (amber hollow square = your yes, amber diamond = soon, red triangle =
// critical: shape + colour + the slot's name, never colour alone). A static cyan notch under the icon means
// "new since you looked" (never a badge count). After the slots: a search glyph (the command bar, as
// Ctrl+K) and, on the calm home while windows are up, the Stage glyph with its count. Under the row: the
// page dots for the five views (Now · Today · Life · Activity · Controls; keys 1–5 still work).
//
//   Data   .rail (contracts/rail) · .marks (contracts/marks) · .focus (contracts/focus) · .presence · .ambient
//          · .now (Date) · .stage (windows up on the Stage, set by the Now view; null hides the glyph).
//          The shell's <jv-rail id="rail"> reads the store and the router itself; a gallery copy has the
//          `static` attribute and is given them.
//   Open   click / Enter / Space on a slot (or Alt+1…6 anywhere) fans its items out above it, 40 ms apart, as
//          small cards in one glass panel (HUD v2 §14.2): a page preview or the kind's line icon, one title line,
//          at most one short line, and the state's glance mark (with its word only when it wants him). "Mark all
//          seen" and "Close" show only on hover or keyboard focus. The open fan sits above every window (the
//          canvas is its own stacking layer, canvas.css), which dim a step and let the pointer pass while it is
//          open (data-open). A card with a docked window is recalled: `recall`, and the window grows out of the
//          slot (the Now view listens for `jv-rail-recall`). A card without one opens where that thing lives
//          (Activity, Today, its branch). Esc (from anywhere) or a click outside closes it; Esc gives focus back
//          to the slot.
//   Tools  the search glyph fires jv-act "search" (the shell opens the command bar); the Stage glyph fires
//          `jv-rail-stage` (the Now view brings the Stage to the front).
//   Marks  a slot's notch shows while any of its things has a mark. A thing's mark clears (`seen`) when it is
//          opened, focused by keyboard, or hovered for 800 ms; "Mark all seen" clears every mark. Being shown,
//          on the ambient screen or anywhere, never clears one. Screen readers hear at most one polite
//          "new since you looked" line a minute.
//   Focus  while Jarvis names a slot or a thing on it (state.focus), corner brackets snap onto the slot
//          (250 ms), until `until`. Reduced motion: instant.
//   Ambient only filled slots, static; an empty slot (and the tools) keep their place unseen (data-vacant), so
//          the row never jumps. Elsewhere all six always show; an empty one has no badge. Tier-2 items are
//          hidden when others are present (and on ambient).
//   Keys   the row is one Tab stop (← → Home End move along it, slots then tools); the page dots follow it.
// Emits jv-act (recall, seen, search), jv-nav and jv-rail-stage; never calls the backend itself.
import { announce } from "../../core/a11y.js";
import { asDate, css, html, icon, raw, whenWords } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { glance, GLANCE, WANTS_YOU } from "../glance/glance.js";
import { router } from "../../core/router.js";
import { store } from "../../core/store.js";
import "../tabs/tabs.js";  // <jv-page-dots>: the five views under the row

css(import.meta.url);

export const SLOTS = ["yes", "today", "homework", "messages", "jarvis", "parked"];
export const SLOT_WORD = { yes: "Your yes", today: "Today", homework: "Homework", messages: "Messages", jarvis: "Jarvis", parked: "Parked" };
const SLOT_ICON = { yes: "you", today: "calendar", homework: "book", messages: "mail", jarvis: "spark", parked: "folder" };
const KIND_ICON = { approval: "you", due: "book", event: "calendar", thread: "file", file: "file", message: "mail", job: "spark", fact: "spark", branch: "map", notice: "help" };
const SEVERITY = { done: 0, parked: 1, progress: 2, jarvis: 3, soon: 4, yes: 5, critical: 6 };  // jarvis_hub/rail.py
export const GLANCE_WORD = { done: "Done", progress: "In progress", jarvis: "Jarvis", soon: "Soon", yes: "Your yes", critical: "Now", parked: "Parked" };
export const HOVER_MS = 800;  // a deliberate hover, not a pass-over
export const ANNOUNCE_MS = 60_000;  // at most one polite "new since you looked" a minute
export const FAN_STEP_MS = 0;  // cards fan out this far apart (after the fan itself rises, 60 ms)
const SAID_REF = "jarvis:said";
const FAN_ID = "jv-rail-fan";
// thumbnails only where the picture is the thing's own content; anything else gets its kind's line icon
const REAL_THUMB = new Set(["page", "slide", "video", "design"]);
let copies = 0;

export const worstOf = (items) => items.reduce((w, i) => (SEVERITY[i.state] > (SEVERITY[w] ?? -1) ? i.state : w), null);

/** What one slot shows, from the Rail as the server sent it. Tier-2 things are hidden when `shared`. */
export function slotView(name, rail, marks = {}, { shared = false } = {}) {
  const slot = rail?.slots?.[name] || { items: [] };
  const all = slot.items || [];
  const items = shared ? all.filter((i) => i.tier !== 2) : all;
  const said = name === "jarvis" ? slot.said || [] : [];
  const marked = items.filter((i) => marks[i.ref]).map((i) => i.ref);
  if (name === "jarvis" && marks[SAID_REF] && said.length) marked.push(SAID_REF);
  return {
    name, items, said, marked,
    count: shared && items.length !== all.length ? items.length : slot.count ?? items.length,
    worst: shared && items.length !== all.length ? worstOf(items) : slot.worst || worstOf(items),
    done: typeof slot.done === "number" ? slot.done : null,
    filled: items.length > 0 || said.length > 0 || (slot.count || 0) > 0,
  };
}

/** The slot a focus cue lands on: a slot name ("homework" or "rail:homework") or a thing's ref. */
export function focusSlot(ref, rail) {
  if (!ref) return null;
  const name = String(ref).replace(/^rail:/, "");
  if (SLOTS.includes(name)) return name;
  return SLOTS.find((s) => (rail?.slots?.[s]?.items || []).some((i) => i.ref === ref || i.window?.id === ref)) || null;
}

/** Where a thing without a docked window lives, so opening it still takes him there. `cards`: state.cards;
 *  `threads`: state.threads (a PDF work thread opens in the reader, at his spot: HUD v2 §10). */
export function homeOf(item, cards = {}, threads = []) {
  const thread = item.kind === "thread" && (threads || []).find((t) => t.ref === item.ref || t.id === item.ref);
  if (thread) return thread.kind === "pdf" ? `/read/${thread.id}` : thread.branch ? `/life/${thread.branch}` : "/life";
  switch (item.kind) {
    case "approval": case "job": case "notice": case "message": return "/activity";  // (an email catch has no branch)
    case "event": return "/today";
    case "branch": return `/life/${item.ref}`;
    case "fact": return "/life/memory";
    default: {  // a due item, file or work thread: its branch page
      const due = Object.values(cards || {}).flatMap((c) => c?.due || []).find((d) => d.id === item.ref);
      return due?.branch_id ? `/life/${due.branch_id}` : "/life";
    }
  }
}

const label = (v) => {
  const bits = [`${SLOT_WORD[v.name]}: ${v.count} ${v.count === 1 ? "thing" : "things"}`];
  if (v.worst) bits.push(`worst: ${GLANCE_WORD[v.worst]}`);
  if (v.done !== null) bits.push(`${Math.round(v.done * 100)}% done`);
  if (v.marked.length) bits.push(`${v.marked.length} new since you looked`);
  return bits.join(", ");
};

// The badge's shape for a slot whose worst thing wants him (glance codes, HUD v2 §5), drawn small and bare (the
// glance component's corner brackets would blur into the shape at badge size): your yes = hollow square,
// soon = diamond, critical = triangle. Its colour is the glance colour; the slot's label says it in words.
const BADGE_SHAPE = {
  yes: '<path class="jv-rail__mark jv-rail__mark--line" d="M2 2h8v8H2Z"/>',
  soon: '<path class="jv-rail__mark" d="M6 .8 11.2 6 6 11.2.8 6Z"/>',
  critical: '<path class="jv-rail__mark" d="M6 1 11.4 10.6H.6Z"/>',
};
/** The badge: the count, led by the glance shape when the slot's worst thing wants him (pure markup). */
export function badge(v) {
  if (!v.filled) return html``;
  const wants = WANTS_YOU.has(v.worst) ? v.worst : "";
  return html`${wants ? raw(`<svg class="jv-rail__shape" data-glance="${wants}" viewBox="0 0 12 12" aria-hidden="true" focusable="false">${BADGE_SHAPE[wants]}</svg>`) : ""}${v.count ? html`<span class="jv-rail__count">${v.count}</span>` : ""}`;
}
// the Stage glyph: four small panes (the windows up on the Stage)
const STAGE_GLYPH = raw('<svg class="jv-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 5h7v6H4zM13 5h7v6h-7zM4 13h7v6H4zM13 13h7v6h-7z"/></svg>');

class Rail extends HTMLElement {
  connectedCallback() {
    if (!this._built) this.build();
    if (!this.hasAttribute("static")) {
      this.stop = store.watch(["rail", "marks", "focus", "presence", "ui"], (s) => this.take(s));
      this.stopEvents = store.onEvent((e) => { if (e.type === "marks.updated") this.noticeNew(e.data.marks || {}); });
      this.onKeys = (e) => this.altKey(e);
      document.addEventListener("keydown", this.onKeys);
      this.stopRoute = router.onChange(() => this.drawDots());
    }
    this.onOutside = (e) => { if (this.openSlot && !this.contains(e.target)) this.close(false); };
    document.addEventListener("pointerdown", this.onOutside, true);
    // Esc closes the fan wherever focus is (before the Stage's "Esc docks the window" or the router's back),
    // unless the command bar or the shortcuts sheet is open over it
    this.onEsc = (e) => {
      if (e.key !== "Escape" || !this.openSlot || e.defaultPrevented || document.getElementById("command-bar")?.isOpen || document.querySelector(".jv-keys__scrim")) return;
      e.preventDefault(); e.stopPropagation();
      this.close(this.contains(document.activeElement) || document.activeElement === document.body);
    };
    document.addEventListener("keydown", this.onEsc, true);
    this.draw();
  }
  disconnectedCallback() {
    this.stop?.(); this.stopEvents?.(); this.stopRoute?.();
    document.removeEventListener("keydown", this.onKeys);
    document.removeEventListener("pointerdown", this.onOutside, true);
    document.removeEventListener("keydown", this.onEsc, true);
    clearTimeout(this.focusTimer); clearTimeout(this.sayTimer); clearTimeout(this.hoverTimer);
  }

  // ---- data ------------------------------------------------------------------------------------------------
  /** Take the store's state (the shell's copy). */
  take(s) {
    Object.assign(this._p, { rail: s.rail, marks: s.marks || {}, focus: s.focus, presence: s.presence || {}, ambient: !!s.ui?.ambient,
      waiting: (s.approvals || []).filter((a) => a.status === "pending").length });
    this.known = new Set(Object.keys(s.marks || {}));  // marks that came with a (re)load aren't "new"; events say what is
    if (s.ui?.railOpen !== this.askedOpen) {  // a scene (or a view) can open a slot through the UI slice
      this.askedOpen = s.ui?.railOpen;
      if (SLOTS.includes(this.askedOpen)) this.openSlot = this.askedOpen;
    }
    this.draw();
  }
  get _p() { return (this.__p ||= { rail: null, marks: {}, focus: null, presence: {}, ambient: false, now: null, stage: null, waiting: 0 }); }
  set rail(v) { this._p.rail = v; this.draw(); }
  get rail() { return this._p.rail; }
  set marks(v) { this._p.marks = v || {}; this.draw(); }
  get marks() { return this._p.marks; }
  set focus(v) { this._p.focus = v; this.draw(); }
  get focus() { return this._p.focus; }
  set presence(v) { this._p.presence = v || {}; this.draw(); }
  get presence() { return this._p.presence; }
  set ambient(v) { this._p.ambient = !!v; this.draw(); }
  get ambient() { return this._p.ambient; }
  set now(v) { this._p.now = v; this.draw(); }
  /** Windows up on the Stage (the Now view sets it on the calm home); null or 0 hides the Stage glyph. */
  set stage(v) { this._p.stage = v || null; this.draw(); }
  get stage() { return this._p.stage; }
  now_() { return this._p.now ? asDate(this._p.now) : this.hasAttribute("static") ? new Date() : store.now(); }
  get shared() { return !!this._p.presence?.others || this._p.ambient; }

  // ---- the six slots and the tools (built once; only their insides change, so focus and hover are never lost)
  build() {
    this._built = true;
    this.classList.add("jv-rail");
    const fanId = this.id === "rail" ? FAN_ID : `${FAN_ID}-${++copies}`;  // ids stay unique when a gallery shows several
    this.innerHTML = String(html`<div class="jv-rail__bar" role="toolbar" aria-label="The Rail: what's waiting, by kind. Alt 1 to 6 jumps to a slot">
      ${SLOTS.map((name, i) => html`<button type="button" class="jv-rail__slot" data-slot="${name}" tabindex="${i ? -1 : 0}" title="${SLOT_WORD[name]}"
        aria-expanded="false" aria-controls="${fanId}" aria-keyshortcuts="Alt+${i + 1}">
        <span class="jv-rail__word">${icon(SLOT_ICON[name])}<span class="jv-rail__name">${SLOT_WORD[name]}</span></span>
        <span class="jv-rail__badge" aria-hidden="true"></span>
        <span class="jv-rail__notch" aria-hidden="true" hidden></span>
        <span class="jv-rail__brackets" aria-hidden="true"><i></i><i></i><i></i><i></i></span></button>`)}
      <button type="button" class="jv-rail__tool" data-tool="search" tabindex="-1" aria-label="Go anywhere or ask Jarvis"
        aria-keyshortcuts="Control+K" title="Go anywhere or ask Jarvis (Ctrl K)">${icon("search")}</button>
      <button type="button" class="jv-rail__tool" data-tool="stage" tabindex="-1" hidden>${STAGE_GLYPH}<span class="jv-rail__badge" aria-hidden="true"></span></button></div>
      <jv-page-dots class="jv-rail__dots"></jv-page-dots>
      <section class="jv-rail__fan" id="${fanId}" hidden></section>`);
    this.bar = this.querySelector(".jv-rail__bar");
    this.fan = this.querySelector(".jv-rail__fan");
    this.dots = this.querySelector(".jv-rail__dots");
    this.stageTool = this.bar.querySelector("[data-tool=stage]");
    // a click makes the slot the Rail's one tab stop (roving), so Esc later gives focus back to a slot that shows its ring
    this.bar.addEventListener("click", (e) => {
      const b = e.target.closest(".jv-rail__slot, .jv-rail__tool");
      if (!b) return;
      this.rove(b);
      if (b.dataset.slot) this.toggle(b.dataset.slot, true); else this.tool(b.dataset.tool);
    });
    this.bar.addEventListener("keydown", (e) => this.barKey(e));
    this.fan.addEventListener("click", (e) => this.fanClick(e));
    this.fan.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.close(true); } });
    this.fan.addEventListener("focusin", (e) => this.seenAt(e.target.closest("[data-ref]")));
    this.fan.addEventListener("pointerover", (e) => this.hover(e.target.closest("[data-ref]")));
    this.fan.addEventListener("pointerleave", () => this.hover(null));
    if (this.getAttribute("open")) this.openSlot = this.getAttribute("open");
  }

  draw() {
    if (!this._built || this._drawing) return;
    this._drawing = true;
    queueMicrotask(() => { this._drawing = false; if (this.isConnected) this.paint(); });
  }

  paint() {
    const { rail, marks, focus, ambient } = this._p;
    const lit = focus?.ref && (!focus.until || asDate(focus.until) > this.now_()) ? focusSlot(focus.ref, rail) : null;
    this.toggleAttribute("data-ambient", ambient);
    this.toggleAttribute("data-open", !!this.openSlot);  // the canvas dims a step and lets the pointer pass (canvas.css)
    this.views = Object.fromEntries(SLOTS.map((name) => [name, slotView(name, rail, marks, { shared: this.shared })]));
    for (const button of this.bar.querySelectorAll(".jv-rail__slot")) {
      const v = this.views[button.dataset.slot];
      const sig = JSON.stringify([v.filled, v.count, v.worst]);
      if (button.dataset.sig !== sig) {
        button.dataset.sig = sig;
        // an empty slot has no badge and no "0" (the count is in its label for screen readers)
        button.querySelector(".jv-rail__badge").innerHTML = String(badge(v));
      }
      button.dataset.worst = v.worst || "";
      button.toggleAttribute("data-wants", WANTS_YOU.has(v.worst) && v.filled);
      button.toggleAttribute("data-empty", !v.filled);
      // ambient shows only filled slots, but an empty one keeps its place (data-vacant: unseen, not removed), so the
      // row never re-centres when a thing arrives or the screen wakes (film review S7)
      button.toggleAttribute("data-vacant", ambient && !v.filled);
      button.querySelector(".jv-rail__notch").hidden = !v.marked.length;
      button.setAttribute("aria-label", label(v));
      button.setAttribute("aria-expanded", String(this.openSlot === button.dataset.slot));
      const was = button.hasAttribute("data-focus");
      button.toggleAttribute("data-focus", lit === button.dataset.slot);
      if (!was && lit === button.dataset.slot) this.snap(button);
    }
    this.paintTools();
    this.drawDots();
    this.armRelease(focus);
    this.paintFan();
  }

  /** The search glyph (always) and the Stage glyph (only with windows up on the Stage); on ambient both keep
   *  their place unseen, like an empty slot. */
  paintTools() {
    const { stage, ambient } = this._p, n = Number(stage) || 0;
    for (const tool of this.bar.querySelectorAll(".jv-rail__tool")) tool.toggleAttribute("data-vacant", ambient);
    const t = this.stageTool;
    if (t.dataset.n !== String(n)) {
      t.dataset.n = String(n);
      t.hidden = !n;
      t.setAttribute("aria-label", `Show the Stage: ${n} ${n === 1 ? "window" : "windows"} up`);
      t.title = `Show the Stage (${n} up)`;
      t.querySelector(".jv-rail__badge").innerHTML = n ? String(html`<span class="jv-rail__count">${n}</span>`) : "";
      if (!n && t.tabIndex === 0) this.rove(this.bar.querySelector(".jv-rail__slot"), false);  // the tab stop never sits on a hidden glyph
    }
  }

  /** The page dots under the row: where he is (the router), and the waiting count for screen readers. */
  drawDots() {
    if (!this.dots) return;
    const current = this.hasAttribute("static") ? "now" : router.current.tab;
    if (this.dots.current !== current) this.dots.current = current;
    if (this.dots.badge !== this._p.waiting) this.dots.badge = this._p.waiting;
  }

  tool(name) {
    if (name === "search") { if (this.openSlot) this.close(false); this.act("search", "command-bar"); }
    else if (name === "stage") this.emit("jv-rail-stage", { count: this._p.stage });
  }

  /** Corner brackets snap on (CSS plays the 250 ms snap each time the attribute is set; reduced motion: none). */
  snap(node) { node.classList.remove("jv-rail__snap"); void node.offsetWidth; node.classList.add("jv-rail__snap"); }

  /** Let go of the focus cue when its `until` passes on the hub clock. */
  armRelease(focus) {
    clearTimeout(this.focusTimer);
    if (!focus?.ref || !focus.until || this.hasAttribute("static")) return;
    const left = asDate(focus.until) - this.now_();
    if (left > 0) this.focusTimer = setTimeout(() => this.paint(), left + 10);
  }

  // ---- the fan ------------------------------------------------------------------------------------------------
  toggle(name, fromUser) {
    if (this.openSlot === name) { this.close(true); return; }
    clearTimeout(this._closeT); this.fan.classList.remove("jv-rail__fan--closing");
    this.openSlot = name;
    this.emit("jv-rail-open", { slot: name });  // he opened an icon (the home's return offer takes that as his answer)
    this.opening = true;  // the cards fan out once, when the slot opens (not on every update)
    this.paint();
    const first = fromUser && this.fan.querySelector("[data-ref]");
    if (first) { this.placed = first; first.focus({ preventScroll: true }); }  // put there for him: not "he looked at it"
  }
  close(giveBack) {
    const name = this.openSlot;
    this.openSlot = null;
    // it settles away (160 ms) before it goes; reopening in that time just takes it back
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches || this._p?.ambient;
    if (!reduce && !this.fan.hidden && this.fan.animate) {
      this.fan.classList.remove("jv-rail__fan--opening"); this.fan.classList.add("jv-rail__fan--closing");
      clearTimeout(this._closeT);
      this._closeT = setTimeout(() => { this.fan.classList.remove("jv-rail__fan--closing"); if (!this.openSlot) this.paint(); }, 120);
      this.toggleAttribute("data-open", false);
      for (const s of this.bar.querySelectorAll("[aria-expanded=true]")) s.setAttribute("aria-expanded", "false");
    } else this.paint();
    // give focus back through rove(): the slot becomes the tab stop (tabindex 0), so base.css's
    // [tabindex="-1"]:focus rule can't hide its ring
    const b = giveBack && name && this.bar.querySelector(`[data-slot="${name}"]`);
    if (b) this.rove(b);
  }

  paintFan() {
    const name = this.openSlot, v = name && this.views[name];
    this.fan.hidden = !v;
    if (!v) { this.fan.dataset.sig = ""; this.fan.replaceChildren(); return; }
    const { marks } = this._p, now = this.now_();
    const anyMarks = Object.keys(marks || {}).length > 0;
    const sig = JSON.stringify([name, v.items, v.said, v.marked, anyMarks, v.items.map((i) => marks[i.ref]?.what)]);
    if (this.fan.dataset.sig === sig && !this.opening) return;
    this.fan.dataset.sig = sig;
    const active = document.activeElement?.closest?.(".jv-rail__fan [data-ref]")?.dataset.ref;
    const card = (item, i) => {
      const mark = marks[item.ref];
      const word = item.state ? GLANCE_WORD[item.state] : "";
      const line = mark ? mark.what : item.from ? `From ${SLOT_WORD[item.from]}${item.detail ? ` · ${item.detail}` : ""}` : item.detail || "";
      const thumb = item.thumb && REAL_THUMB.has(item.thumb.kind || "page") ? item.thumb : null;
      return html`<li style="--i:${i}"><button type="button" class="jv-rail__card" data-ref="${item.ref}" data-state="${item.state || ""}"
        aria-label="${[item.title, word, mark ? `New since you looked: ${mark.what}` : line, item.window ? "Brings its window back" : ""].filter(Boolean).join(". ")}">
        <span class="jv-rail__thumb${thumb ? " jv-rail__thumb--media" : ""}" aria-hidden="true">${thumb ? html`<img src="${thumb.src}" alt="" width="32" height="32" loading="lazy" decoding="async">` : icon(KIND_ICON[item.kind] || "help")}</span>
        <span class="jv-rail__title">${item.title}</span>
        ${item.state ? html`<span class="jv-rail__state" data-wants="${WANTS_YOU.has(item.state) ? "yes" : ""}">${glance(item.state, { size: "rail", word, bare: !WANTS_YOU.has(item.state) })}</span>` : ""}
        ${line ? html`<span class="jv-rail__line${mark ? " jv-rail__line--new" : ""}">${line}</span>` : ""}
        ${mark ? html`<span class="jv-rail__notch" aria-hidden="true"></span>` : ""}</button></li>`;
    };
    const saidMarked = v.marked.includes(SAID_REF);
    this.fan.setAttribute("aria-label", SLOT_WORD[name]);
    this.fan.innerHTML = String(html`<span class="jv-rail__ghost" aria-hidden="true"></span><span class="jv-rail__ghost jv-rail__ghost--2" aria-hidden="true"></span>
      <header class="jv-rail__fanhead">
        <h2 class="jv-kicker">${SLOT_WORD[name]} // ${v.count}</h2>
        ${anyMarks ? html`<button type="button" class="jv-rail__do" data-all-seen>Mark all seen</button>` : ""}
        <button type="button" class="jv-rail__do" data-close aria-label="Close ${SLOT_WORD[name]}">Close</button></header>
      <div class="jv-rail__fanbody">
      ${v.items.length ? html`<ul class="jv-rail__cards">${v.items.map(card)}</ul>`
        : !v.said.length ? html`<p class="jv-rail__empty">${name === "parked" ? "Nothing parked. Things idle for a week fold in here." : "Nothing here right now."}</p>` : ""}
      ${v.said.length ? html`<section class="jv-rail__said" data-ref="${SAID_REF}" tabindex="0" aria-label="What Jarvis said, newest first">
          <h3 class="jv-kicker">Said // last ${v.said.length}${saidMarked ? html`<span class="jv-rail__notch" aria-hidden="true"></span><span class="jv-sr">, new since you looked</span>` : ""}</h3>
          <ol>${v.said.map((line) => html`<li><span class="jv-rail__when">${whenWords(line.at, now)}</span> ${line.text}</li>`)}</ol></section>` : ""}</div>`);
    this.fan.classList.toggle("jv-rail__fan--opening", !!this.opening && !this._p.ambient);
    this.opening = false;
    if (active) this.fan.querySelector(`[data-ref="${CSS.escape(active)}"]`)?.focus({ preventScroll: true });
  }

  fanClick(e) {
    if (e.target.closest("[data-close]")) { this.close(true); return; }
    if (e.target.closest("[data-all-seen]")) { this.act("seen", "all"); return; }
    const b = e.target.closest(".jv-rail__card");
    if (!b) return;
    const item = this.views[this.openSlot]?.items.find((i) => i.ref === b.dataset.ref);
    if (!item) return;
    if (item.window) {  // recall: the window grows out of this slot
      const from = this.bar.querySelector(`[data-slot="${this.openSlot}"]`).getBoundingClientRect();
      document.dispatchEvent(new CustomEvent("jv-rail-recall", { detail: { id: item.window.id, ref: item.ref, rect: from } }));
      this.act("recall", item.ref);
      this.emit("jv-nav", { path: "/now" });
    } else {  // opening the thing where it lives
      if (this._p.marks[item.ref]) this.act("seen", item.ref);
      this.emit("jv-nav", { path: homeOf(item, store.state.cards, store.state.threads) });
    }
    this.close(false);
  }

  // ---- marks: seen on keyboard focus or an 800 ms hover on the thing, never just by being shown ----------
  seenAt(node) {
    if (node && node === this.placed) { this.placed = null; return; }  // focus we moved there on opening doesn't count
    this.placed = null;
    const ref = node?.dataset.ref;
    if (ref && this._p.marks[ref]) this.act("seen", ref);
  }
  hover(node) {
    if (node === this.hovered) return;
    this.hovered = node;
    clearTimeout(this.hoverTimer);
    if (!node || this._p.ambient) return;
    this.hoverTimer = setTimeout(() => { if (this.hovered === node && node.isConnected) this.seenAt(node); }, HOVER_MS);
  }

  /** New marks on Rail things: one polite line at most a minute ("New since you looked: Homework 1, Jarvis 1"). */
  noticeNew(marks) {
    const fresh = Object.keys(marks).filter((ref) => !this.known?.has(ref));
    this.known = new Set(Object.keys(marks));
    if (!fresh.length) return;
    this.pending = new Set([...(this.pending || []), ...fresh]);
    if (this.sayTimer) return;
    const wait = Math.max(0, (this.saidAt ?? -Infinity) + ANNOUNCE_MS - performance.now());
    this.sayTimer = setTimeout(() => this.say(), wait);
  }
  say() {
    this.sayTimer = null;
    const refs = this.pending || new Set();
    this.pending = null;
    const counts = SLOTS.map((name) => [name, this.views?.[name]?.marked.filter((r) => refs.has(r)).length || 0]).filter(([, n]) => n);
    if (!counts.length) return;
    this.saidAt = performance.now();
    announce(`New since you looked: ${counts.map(([name, n]) => `${SLOT_WORD[name]} ${n}`).join(", ")}.`, "polite");
  }

  // ---- keys ---------------------------------------------------------------------------------------------------
  barKey(e) {
    const slots = [...this.bar.querySelectorAll(":is(.jv-rail__slot, .jv-rail__tool):not([hidden], [data-vacant])")];
    const i = slots.indexOf(e.target.closest(".jv-rail__slot, .jv-rail__tool"));
    if (i < 0) return;
    const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: slots.length - 1 }[e.key];
    if (to !== undefined) { e.preventDefault(); this.rove(slots[(to + slots.length) % slots.length]); return; }
    if (e.key === "ArrowUp" && this.openSlot) { e.preventDefault(); this.fan.querySelector("[data-ref], button")?.focus(); return; }
    if (e.key === "Escape" && this.openSlot) { e.preventDefault(); e.stopPropagation(); this.close(true); }
  }
  rove(button, focus = true) {
    for (const b of this.bar.children) b.tabIndex = b === button ? 0 : -1;
    if (focus) button.focus({ preventScroll: true });
  }
  /** Alt+1…6 focuses a slot from anywhere (core/keys.js leaves Alt combinations alone). */
  altKey(e) {
    if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || this.closest("[hidden]")) return;
    const n = /^Digit([1-6])$/.exec(e.code)?.[1];
    if (!n) return;
    const button = this.bar.querySelectorAll(".jv-rail__slot")[Number(n) - 1];
    if (!button || button.hidden || button.hasAttribute("data-vacant") || !button.offsetParent) return;
    e.preventDefault();
    this.rove(button);
  }

  act(action, target, args) { this.emit("jv-act", { action, target, args }); }
  emit(name, detail) { this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true })); }
}
if (!customElements.get("jv-rail")) customElements.define("jv-rail", Rail);

// ---- the gallery ----------------------------------------------------------------------------------------------
// A Rail like the one jarvis_hub/rail.py builds from the demo day at 3:40 pm Monday, plus a docked window,
// a running and a finished job, what Jarvis said, a folded thing in Parked and a tier-2 item.
export function sampleRail() {
  const at = "2026-11-16T15:40:00";
  return { slots: {
    yes: { items: [{ ref: "ap-week", slot: "yes", kind: "approval", title: "Book this week's study plan", at: "2026-11-16T15:41:00", state: "yes", detail: "Adds 9 blocks to your Google Calendar, Mon to Fri",
      window: { id: "w-ap-week", type: "approval", title: "Waiting for your yes", ref: "ap-week", size: "2x2", docked: true, slot: "yes" } }], worst: "yes" },
    today: { items: [
      { ref: "d-review", slot: "today", kind: "event", title: "Review GE 122 lecture 21", at: "2026-11-16T16:00:00", state: "soon", detail: "4 pm" },
      { ref: "d-chemrev", slot: "today", kind: "event", title: "CHEM review", at: "2026-11-16T08:00:00", state: "parked", detail: "Moved to 4 pm tomorrow" },
      { ref: "d-pps", slot: "today", kind: "event", title: "PPS 7, questions 7 to 12", at: "2026-11-16T19:00:00", detail: "7 pm" },
      { ref: "d-math", slot: "today", kind: "event", title: "MATH 133 lecture", at: "2026-11-16T08:30:00", state: "done", detail: "8:30 am · ARTS 101" },
      { ref: "d-ge", slot: "today", kind: "event", title: "GE 122 lecture 21 · Frames", at: "2026-11-16T10:00:00", state: "done", detail: "10 am · ENGR 1A10" },
    ], done: 0.67, worst: "soon" },
    homework: { items: [
      { ref: "due-pps7", slot: "homework", kind: "due", title: "GE 122 · PPS 7", at, state: "progress", detail: "Due Wed 8 pm · 50% done",
        window: { id: "w-due-pps7", type: "countdown", title: "Due", ref: "due-pps7", size: "1x1", docked: true, slot: "homework" } },
      { ref: "due-lab4", slot: "homework", kind: "due", title: "CHEM 142 · Lab report 4", at, state: "progress", detail: "Due Thu 5 pm · 40% done" },
      { ref: "due-webwork", slot: "homework", kind: "due", title: "MATH 133 · WeBWorK 9", at, detail: "Due Sun 11:59 pm" },
      { ref: "due-memo", slot: "homework", kind: "due", title: "Design memo 3", at, detail: "Due Wed 11:59 pm" },
    ], done: 0.23, worst: "progress" },
    messages: { items: [] },
    jarvis: { items: [
      { ref: "j-sync", slot: "jarvis", kind: "job", title: "Checking Canvas", at: "2026-11-16T15:38:00", state: "done" },
      { ref: "f-ge-quiz", slot: "jarvis", kind: "fact", title: "GE 122 quizzes are open book", at: "2026-11-16T15:20:00", tier: 2 },
    ], said: [
      { text: "On track. PPS 7 is half done and due Wednesday at 8.", at: "2026-11-16T15:40:40", kind: "caption", source: { kind: "canvas", label: "Canvas" } },
      { text: "Canvas is up to date. Nothing new since this morning.", at: "2026-11-16T15:38:10", kind: "toast" },
    ], worst: "done" },
    parked: { items: [{ ref: "ge-121", slot: "parked", kind: "branch", title: "GE 121 notes", at: "2026-11-08T20:10:00", state: "parked", from: "homework" }], count: 1, worst: "parked" },
  } };
}
export const SAMPLE_MARKS = {
  "due-pps7": { what: "Due moved Wed 8 pm → Thu 11:59 pm", at: "2026-11-16T15:12:00" },
  "jarvis:said": { what: "Jarvis said: On track. PPS 7 is half done and due Wednesday at 8.", at: "2026-11-16T15:40:40" },
};
const NOW = new Date("2026-11-16T15:40:00");
const sample = (props = {}, attrs = {}) => {
  const node = el("jv-rail", {}, { static: true, ...attrs });
  Object.assign(node, { rail: sampleRail(), marks: {}, presence: { here: true, others: false }, now: NOW, ...props });
  return node;
};
const emptyRail = () => ({ slots: Object.fromEntries(SLOTS.map((s) => [s, s === "jarvis" ? { items: [], said: [] } : { items: [] }])) });
registerGallery("rail", [
  { label: "Empty", wide: true, build: () => sample({ rail: emptyRail() }) },
  { label: "Filled", wide: true, build: () => sample() },
  { label: "Since you looked", wide: true, build: () => sample({ marks: SAMPLE_MARKS }) },
  { label: "Jarvis names Homework", wide: true, build: () => sample({ focus: { ref: "due-pps7", until: "2026-11-16T15:40:44" } }) },
  { label: "Critical", wide: true, build: () => { const r = sampleRail(); r.slots.homework.items[0].state = "critical"; r.slots.homework.items[0].detail = "Overdue since Wed 8 pm"; r.slots.homework.worst = "critical"; return sample({ rail: r }); } },
  { label: "Ambient (only filled slots)", wide: true, build: () => sample({ ambient: true }) },
  { label: "Stage glyph (4 windows up)", wide: true, build: () => sample({ stage: 4 }) },
  { label: "Others present (tier 2 hidden)", wide: true, build: () => sample({ presence: { here: true, others: true } }) },
  { label: "Homework open", wide: true, build: () => sample({ marks: SAMPLE_MARKS }, { open: "homework" }) },
  { label: "Jarvis open", wide: true, build: () => sample({ marks: SAMPLE_MARKS }, { open: "jarvis" }) },
  { label: "Glance codes", wide: true, build: () => {
    const row = el("p", { className: "jv-rail__legend" });
    row.innerHTML = String(html`${Object.keys(GLANCE).map((s) => html`<span class="jv-rail__state" data-state="${s}">${glance(s, { size: "rail", word: GLANCE_WORD[s] })}</span>`)}`);
    return row;
  } },
], { about: "Huw's icon row: six fixed slots that track things, not windows. Number = how many; an amber square, amber diamond or red triangle = something there wants you (your yes, soon, critical); cyan notch = new since you looked. Then search, the Stage, and the page dots." });
