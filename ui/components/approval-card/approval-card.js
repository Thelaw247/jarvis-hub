// <jv-approval-card>: a write that is waiting for his yes. Consequences come first, then the words Jarvis
// will say (read-back), then the sources, then Yes / No / Change it.   .approval = approval contract   .now = Date
// The footer says "Say yes or no, or tap." only while the orb's yes window is open; after it, "Tap to answer, or
// wake Jarvis and say it." (voice then needs a fresh wake).
// Yes is the one accent button. Emits jv-act: approve, decline, change (args.text = his tweak, in his words).
// - The first answer locks the buttons (aria-disabled) so a double click can't answer twice.
// - "Change it" opens an inline field (Enter sends, Shift+Enter is a new line, Esc cancels); the item stays on
//   screen and, once sent, reads "Changing…".
//   His draft and the field survive a re-render (Activity redraws when receipts arrive).
// - Wide cards (≥ 680 px) put what will happen on the left and the question and answers on the right.
// Night HUD (N5b): one kicker row, all caps: the kind of change, then the glance mark (the amber hollow square +
// "YOUR YES" while it waits; DONE, CHANGING, RAN OUT after), and how long it waits on the right ("UNTIL 9:00 PM");
// the title is condensed caps.
import { asDate, clockTime, css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const DONE = {
  approved: ["check", "You said yes."],
  declined: ["close", "You said no. Nothing was done."],
  changed: ["edit", "Changing…"],
  expired: ["clock", "This offer ran out. Nothing was done."],
};
const MARK = { pending: ["yes", "Your yes"], approved: ["done", "Done"], changed: ["progress", "Changing"], declined: ["parked", "Declined"], expired: ["parked", "Ran out"] };
const KIND = { calendar: "Calendar", files: "Files", messages: "Messages", memory: "Memory", tree: "Life Map", skills: "Skills" };
const BUSY_MS = 4000;  // if the hub never answers, the buttons come back (the shell shows what went wrong)

/** Answers by approval category (R3). A category may name its own: fn(approval) → { yes?, no?, kind?, extra? }.
 *  `extra` takes the place of "Change it": { label, args, key } (an approve with args), or null for no third answer.
 *  Without a hook the answers are Yes, do it · No · Change it. */
const ANSWERS = new Map();
export const registerAnswers = (category, fn) => { ANSWERS.set(category, fn); };

const drafts = new Map();  // approval id -> { open, text, sent }   (UI only; survives the card being re-created)
const busy = new Map();    // approval id -> { status, until }   answered here, waiting for the hub to confirm
/** The tweak he sent for an approval, if he typed one in this window. */
export const tweakFor = (id) => drafts.get(id)?.sent || "";

class ApprovalCard extends Jv {
  static props = ["approval", "now"];
  static attrs = ["clean"];
  setup() {
    // capture: runs before the base class turns the click into jv-act
    this.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || !this.contains(b)) return;
      if (b.getAttribute("aria-disabled") === "true" || (this.approval && this._isBusy(this.approval))) { e.stopImmediatePropagation(); e.preventDefault(); return; }
      if (b.dataset.tweak === "open") { e.stopImmediatePropagation(); this._draft({ open: true }); this._focusKey = "tweak-box"; this.update(); return; }
      if (b.dataset.tweak === "cancel") { e.stopImmediatePropagation(); this._draft({ open: false }); this._focusKey = "change"; this.update(); return; }
      if (b.dataset.act === "approve" || b.dataset.act === "decline") this._lock();
    }, true);
    this.addEventListener("input", (e) => { if (e.target.name === "tweak") this._draft({ text: e.target.value }); });
    this.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && e.target.name === "tweak") { e.preventDefault(); e.target.form?.requestSubmit(); return; }
      if (e.key === "Escape" && e.target.name === "tweak") { e.preventDefault(); e.stopPropagation(); this._draft({ open: false }); this._focusKey = "change"; this.update(); }
    });
    this.addEventListener("submit", (e) => {
      e.preventDefault();
      const a = this.approval, text = (e.target.elements.tweak?.value || "").trim();
      if (!a || this._isBusy(a)) return;
      if (!text) { this._focusKey = "tweak-box"; this._hint = true; this.update(); return; }
      this._draft({ open: false, text: "", sent: text });
      this._lock();
      this.emit("jv-act", { action: "change", target: a.id, args: { text } });
    });
  }
  teardown() { clearTimeout(this._unlock); this._stopOrb?.(); this._stopOrb = null; }
  /** Voice can answer only while the orb is in its yes window; after that he taps (or wakes Jarvis first). */
  _voiceOpen() { return store.state.orb?.state === "waiting"; }
  _draft(patch) { const id = this.approval?.id; if (id) drafts.set(id, { ...(drafts.get(id) || {}), ...patch }); }
  _isBusy(a) {
    const b = busy.get(a.id);
    if (b && (b.status !== a.status || performance.now() > b.until)) { busy.delete(a.id); return false; }
    return !!b;
  }
  _lock() {
    const a = this.approval;
    if (!a) return;
    busy.set(a.id, { status: a.status, until: performance.now() + BUSY_MS });
    this.update();
  }
  render() {
    const a = this.approval;
    if (!a) return html``;
    const now = asDate(this.now || store.now());
    const status = a.status === "pending" && a.expires && asDate(a.expires) <= now ? "expired" : a.status;
    const draft = drafts.get(a.id) || {};
    const locked = this._isBusy(a), lock = locked ? html`aria-disabled="true"` : "";
    clearTimeout(this._unlock);
    if (locked) this._unlock = setTimeout(() => this.update(), busy.get(a.id).until - performance.now() + 20);
    this._sources = a.sources || [];
    this._voice = this._voiceOpen();
    const ans = ANSWERS.get(a.category)?.(a) || {}, yes = ans.yes || "Yes, do it", no = ans.no || "No";
    const third = (small) => (ans.extra === undefined
      ? html`<button type="button" class="jv-btn ${small}jv-btn--quiet" data-tweak="open" data-key="change" ${lock}>Change it</button>`
      : ans.extra ? html`<button type="button" class="jv-btn ${small}jv-btn--quiet" data-act="approve" data-target="${a.id}" data-args="${JSON.stringify(ans.extra.args || {})}" data-key="${ans.extra.key || "extra"}" ${lock}>${ans.extra.label}</button>` : "");
    let answer;
    if (status === "pending" && draft.open) {
      answer = html`<form class="jv-approval-card__form" data-form="tweak">
        <label class="jv-title" for="tweak-${a.id}">What should change?</label>
        <textarea id="tweak-${a.id}" name="tweak" rows="2" data-key="tweak-box" aria-describedby="tweak-hint-${a.id}" placeholder="For example: not before 10 am, and keep Friday free">${draft.text || ""}</textarea>
        <p class="jv-muted jv-approval-card__wait" id="tweak-hint-${a.id}">${this._hint ? "Type what to change first, or press Cancel." : "Jarvis keeps this waiting and asks again with your change. Nothing happens until you say yes."}</p>
        <p class="jv-approval-card__buttons"><button class="jv-btn jv-btn--primary" data-key="send" ${lock}>Send the change</button>
          <button type="button" class="jv-btn jv-btn--quiet" data-tweak="cancel" data-key="cancel">Cancel</button></p></form>`;
    } else if (status === "pending") {
      answer = html`<p class="jv-approval-card__buttons ${locked ? "jv-approval-card__buttons--busy" : ""}">
          <button type="button" class="jv-btn jv-btn--primary" data-act="approve" data-target="${a.id}" data-key="yes" ${lock}>${yes}</button>
          <button type="button" class="jv-btn" data-act="decline" data-target="${a.id}" data-key="no" ${lock}>${no}</button>
          ${third("")}</p>
        <p class="jv-muted jv-approval-card__wait" ${locked ? html`role="status"` : ""}>${locked ? "Sending your answer…" : html`${this._voice ? "Say yes or no, or tap." : "Tap to answer, or wake Jarvis and say it."}${a.expires ? ` It waits until ${clockTime(a.expires)}, then nothing happens.` : ""}`}</p>`;
    } else {
      const [glyph, words] = DONE[status] || DONE.expired;
      const sent = status === "changed" ? (draft.sent || "") : "";
      answer = html`<p class="jv-approval-card__done">${icon(glyph)}${words}</p>
        ${status === "changed" ? html`<p class="jv-muted">${sent ? html`Jarvis will ask again with your change: “${sent}”` : "Jarvis will ask again with your change."}</p>` : ""}`;
    }
    this._hint = false;
    if (this.hasAttribute("clean")) {
      // In a window (HUD v2 §14.2): the title is the hero and one line says what a yes would do. No buttons on the
      // resting window: Yes / No, what will happen in full, Jarvis's words, the sources and "Change it" wait in the
      // "Why?" drawer (.jv-more: hover or keyboard focus), and voice still answers. Clicking the window only OPENS
      // the question in Activity (data-key="open"); it never answers it. The window's kicker says the kind of
      // change and how long it waits.
      const first = a.consequences[0] || "";
      const line = `${a.reversible === false ? "Can't be undone · " : ""}${first}`;
      const pending = status === "pending", form = pending && draft.open;
      const words = (DONE[status] || DONE.expired)[1];
      const sent = status === "changed" ? (draft.sent || "") : "";
      return html`<article class="jv-approval-card jv-approval-card--clean jv-approval-card--${status}" tabindex="-1" aria-label="${pending ? "Waiting for your yes" : status === "changed" ? "Changing" : "Answered"}: ${a.title}">
        <h3 class="jv-approval-card__title" title="${a.title}"><span>${a.title}</span></h3>
        <p class="jv-pane__line" title="${line}">${pending ? line : sent ? `${words} Jarvis will ask again with your change: “${sent}”` : words}</p>
        <div class="jv-more" role="group" aria-label="Answer: yes or no, what will happen, and the sources">
          <p class="jv-more__kicker jv-kicker" aria-hidden="true">Your answer</p>
          ${form ? answer : pending ? html`<p class="jv-approval-card__buttons ${locked ? "jv-approval-card__buttons--busy" : ""}">
            <button type="button" class="jv-btn jv-btn--small jv-btn--primary" data-act="approve" data-target="${a.id}" data-key="yes" ${lock}>${yes}</button>
            <button type="button" class="jv-btn jv-btn--small" data-act="decline" data-target="${a.id}" data-key="no" ${lock}>${no}</button>
            ${third("jv-btn--small ")}
            ${locked ? html`<span class="jv-sr" role="status">Sending your answer…</span>` : ""}</p>
            <p class="jv-muted jv-approval-card__wait">${this._voice ? "Say yes or no, or tap." : "Tap to answer, or wake Jarvis and say it."}${a.expires ? ` It waits until ${clockTime(a.expires)}, then nothing happens.` : ""}</p>` : ""}
          <div><h4 class="jv-title">What will happen</h4>
            <ul class="jv-approval-card__list">${a.consequences.slice(0, 4).map((c) => html`<li>${c}</li>`)}</ul></div>
          ${a.reversible === false ? html`<p class="jv-approval-card__warn">${icon("alert")}This can't be undone.</p>` : ""}
          <p class="jv-approval-card__say"><span class="jv-label">Jarvis asks</span> “${a.read_back}”</p>
          ${this._sources.length ? html`<p class="jv-approval-card__sources"><span class="jv-label">Based on</span>${this._sources.map(() => html`<jv-source-chip></jv-source-chip>`)}</p>` : ""}
          <p class="jv-approval-card__open"><button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-nav="/activity" data-key="open">Open it<span class="jv-sr">: ${a.title}, in Activity</span></button></p>
        </div>
      </article>`;
    }
    return html`<article class="jv-approval-card jv-approval-card--${status}" tabindex="-1" aria-label="${status === "pending" ? "Waiting for your yes" : status === "changed" ? "Changing" : "Answered"}: ${a.title}">
      <div class="jv-kicker-row jv-approval-card__kicker"><span class="jv-approval-card__mark"><span class="jv-kicker">${ans.kind || KIND[a.category] || "Change"} //</span><jv-glance state="${(MARK[status] || MARK.expired)[0]}" label="${(MARK[status] || MARK.expired)[1]}"></jv-glance></span>
        ${status === "pending" && a.expires ? html`<span class="jv-kicker">Until ${clockTime(a.expires)}</span>` : ""}</div>
      <h3 class="jv-approval-card__title">${a.title}</h3>
      <div class="jv-approval-card__cols">
        <div class="jv-approval-card__col">
          <div><h4 class="jv-title">What will happen</h4>
            <ul class="jv-approval-card__list">${a.consequences.slice(0, 4).map((c) => html`<li>${c}</li>`)}</ul></div>
          ${a.reversible === false ? html`<p class="jv-approval-card__warn">${icon("alert")}This can't be undone.</p>` : ""}
        </div>
        <div class="jv-approval-card__col">
          <p class="jv-approval-card__say"><span class="jv-label">Jarvis asks</span> “${a.read_back}”</p>
          ${this._sources.length ? html`<p class="jv-approval-card__sources"><span class="jv-label">Based on</span>${this._sources.map(() => html`<jv-source-chip></jv-source-chip>`)}</p>` : ""}
          ${answer}
        </div>
      </div>
    </article>`;
  }
  rendered() {
    // the footer's "Say yes or no" follows the orb's yes window (walkthrough: it stayed after the window closed)
    this._stopOrb ||= store.subscribe((s, keys) => { if (keys.has("orb") && this._voice !== this._voiceOpen()) this.update(); });
    this.querySelectorAll("jv-source-chip").forEach((chip, i) => { chip.source = this._sources[i]; });
    if (this._focusKey) {
      const target = this.querySelector(`[data-key="${this._focusKey}"]`);
      this._focusKey = null;
      if (target) { target.focus({ preventScroll: true }); if (target.setSelectionRange) target.setSelectionRange(target.value.length, target.value.length); }
    }
  }
}
ApprovalCard.define("jv-approval-card");

const card = (change, draft) => (s) => {
  const a = s.approvals[0]; change?.(a);
  if (draft) drafts.set(a.id, draft);
  return el("jv-approval-card", { approval: a, now: s.now });
};
registerGallery("approval-card", [
  { label: "Waiting for your yes", build: card() },
  { label: "Can't be undone", build: card((a) => { Object.assign(a, { id: "ap-send", title: "Send lab report 3 to Prof. Smith", consequences: ["Sends an email from your USask address", "Attaches Lab report 3.pdf", "Can't be unsent"], read_back: "Shall I send lab report three to Professor Smith now?", reversible: false, sources: [{ kind: "file", label: "Lab report 3.pdf" }] }); }) },
  { label: "Change it (typing)", build: card((a) => { a.id = "ap-tweak"; }, { open: true, text: "Not before 10 am, please" }) },
  { label: "Changing", build: card((a) => { a.id = "ap-changing"; a.status = "changed"; }, { sent: "Not before 10 am, please" }) },
  { label: "After yes", build: card((a) => { a.status = "approved"; }) },
  { label: "After no", build: card((a) => { a.status = "declined"; }) },
  { label: "Ran out", build: card((a) => { a.expires = "2026-11-16T15:00:00"; }) },
], { about: "Consequences first, the read-back, then one clear Yes. Change it opens a field and keeps the item in view.", columns: "400px" });
