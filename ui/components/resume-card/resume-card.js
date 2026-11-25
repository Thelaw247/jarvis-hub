// <jv-resume-card>: "here's where you stopped" over a reopened work thread (HUD v2 §6.4, §10.1).
//   .thread    a work thread (contracts/thread.schema.json); its resume point decides what the card offers
//   .questions the document's question index ([{ label, page, y }]), for "Another question"
//   .now       the hub clock (ISO); .changed  what changed about the thing since he looked (a mark's `what`)
//   .private   true when others are present or on the ambient screen: "solutions viewed" never shows then
// Shows the page thumbnail, "PPS 7 · Q7 · Tue" and one short line ("1–6 done."). The card never speaks:
// whether Jarvis says anything is decided elsewhere (§9.4). Its words follow the character rules (§9.2):
// short and complete, no system-speak, a lead chosen by context (what changed, then time away) and a rotating
// wording that never repeats one of the last five it showed.
// Emits `jv-resume` { choice: "accept" | "top" | "pick" | "ignore", label?, page?, y? } and lifts itself.
// A weak spot (resume without y) offers the page instead of a question. It never offers two answers that mean the
// same: when the spot is the start of the document (page 1, or the first question), "From the top" isn't shown.
import { asDate, clockTime, css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const FULL_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const RECENT_MAX = 5;
const recent = [];  // the last lines this card showed, newest last (shared by every card on the page)

/** Q1…Q6 → "1–6"; Q1, Q2, Q4 → "1, 2 and 4"; Q7a → "7a". */
export function doneWords(done = []) {
  const items = done.map((l) => String(l).replace(/^Q/, "")).filter(Boolean);
  const nums = items.map((x) => (/^\d+$/.test(x) ? Number(x) : null));
  const runs = [];
  items.forEach((x, i) => {
    const last = runs[runs.length - 1];
    if (nums[i] != null && last && last.end != null && nums[i] === last.end + 1) { last.end = nums[i]; last.to = x; }
    else runs.push({ from: x, to: x, end: nums[i] });
  });
  const parts = runs.map((r) => (r.from === r.to ? r.from : Number(r.to) - Number(r.from) === 1 ? `${r.from}, ${r.to}` : `${r.from}–${r.to}`));
  return parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0] || "";
}

const dayWord = (at, now) => {
  const a = asDate(at), n = asDate(now);
  const days = Math.round((new Date(n.getFullYear(), n.getMonth(), n.getDate()) - new Date(a.getFullYear(), a.getMonth(), a.getDate())) / 864e5);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : days < 7 ? DAYS[a.getDay()] : `${a.getDate()} ${a.toLocaleString("en-CA", { month: "short" })}`;
};
const longDay = (at, now) => { const w = dayWord(at, now); return w === "Today" ? "today" : w === "Yesterday" ? "yesterday" : FULL_DAYS[asDate(at).getDay()] || w; };
const hoursAway = (at, now) => (asDate(now) - asDate(at)) / 36e5;
const isWeak = (resume) => !!resume && (resume.y == null || /^Page /.test(resume.label || ""));
/** The spot is the start of the document: "Carry on" and "From the top" would be the same answer. */
export const atStart = (resume, questions = []) => {
  if (!resume) return false;
  const first = questions.find((q) => !q.part);
  return isWeak(resume) ? (resume.page || 1) === 1 : !!first && first.label === resume.label;
};
const spoken = (label) => (/^Q\d/.test(label) ? `question ${label.slice(1)}` : String(label).toLowerCase());

/** The pools: layer 2 (context) picks the pool, layer 3 (rotation) picks the wording (HUD v2 §9.4). */
export function linePool(thread, { now, changed } = {}) {
  const r = thread.resume;
  const done = doneWords(thread.done);
  if (isWeak(r)) {
    const page = r.page || 1;
    return [`You stopped on page ${page}.`, `Page ${page}, where you stopped.`, `You were on page ${page}.`,
      `Back to page ${page}.`, `Page ${page}, as you left it.`];
  }
  const lead = changed ? `${String(changed).replace(/[.\s]+$/, "")}. ` : "";
  if (done && (lead || hoursAway(r.at, now) >= 24)) {  // away a day or more: a short review of what's behind him
    return [`${lead}${done} done.`, `${lead}Done so far: ${done}.`, `${lead}Questions ${done.replace("–", " to ")} are done.`,
      `${lead}${done} behind you.`, `${lead}${done} finished.`, `${lead}Through question ${done.split(/[–, ]/).pop()}.`];
  }
  if (done) return [`${done} done.`, "As you left it.", "Right where you stopped.", `${done} done, as you left it.`, "Where you left off.", `Done so far: ${done}.`];
  if (lead) return [`${lead}Where you stopped.`, `${lead}As you left it.`, `${lead}Right where you left off.`];
  return ["Where you stopped.", "As you left it.", "Right where you left off.", "Your place, as you left it.", "Where you left off."];
}

/** Pick the first wording not shown in the last five (and never the one just shown). */
export function pickLine(pool) {
  const line = pool.find((l) => !recent.includes(l)) || pool.find((l) => l !== recent[recent.length - 1]) || pool[0];
  recent.push(line);
  while (recent.length > RECENT_MAX) recent.shift();
  return line;
}
export const recentLines = () => [...recent];

class ResumeCard extends Jv {
  static props = ["thread", "questions", "now", "changed", "private"];
  static attrs = ["lifted"];

  setup() {
    this.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); this.choose("ignore"); }
    });
  }

  /** The line is chosen once per resume point, so a redraw never swaps the words under him. */
  get line() {
    const t = this.thread, key = `${t?.id}|${t?.resume?.at}|${t?.resume?.label}|${this.changed || ""}`;
    if (this._lineKey !== key) { this._lineKey = key; this._line = t?.resume ? pickLine(linePool(t, { now: this.now, changed: this.changed })) : ""; }
    return this._line;
  }

  render() {
    const t = this.thread, r = t?.resume;
    if (!t || !r) return html``;
    const weak = isWeak(r);
    const now = this.now || r.at;
    const where = weak ? `Page ${r.page || 1}` : r.label;
    const total = (this.questions || []).filter((q) => !q.part).length;
    const doneCount = (t.done || []).filter((l) => /^Q\d+$/.test(l)).length;
    const arc = total ? Math.min(1, doneCount / total) : 0;
    const why = this._why;
    const viewed = !this.private && (t.viewed || []).length ? doneWords(t.viewed) : "";
    const pick = this._pick;
    const target = weak ? `page ${r.page || 1}` : spoken(r.label);
    return html`<section class="jv-frame jv-resume-card${this.hasAttribute("lifted") ? " jv-resume-card--lifted" : ""}" aria-label="Where you stopped in ${t.title}">
      <div class="jv-resume-card__main">
        ${t.thumb ? html`<img class="jv-resume-card__thumb" src="${t.thumb.src}" alt="${t.thumb.alt}" width="64" height="83" decoding="async">` : ""}
        <span class="jv-resume-card__mono" aria-hidden="true"${t.thumb ? " hidden" : ""}>P${r.page || 1}</span>
        <div class="jv-resume-card__text">
          <p class="jv-kicker jv-resume-card__kicker">
            <svg class="jv-resume-card__ring" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="7.5" pathLength="100"/><circle class="jv-resume-card__arc" cx="10" cy="10" r="7.5" pathLength="100" stroke-dasharray="${Math.round(arc * 100)} 100"/></svg>
            <span>${t.title} · ${where} · ${dayWord(r.at, now)}</span>
          </p>
          <p class="jv-resume-card__line" data-line>${this.line}</p>
        </div>
      </div>
      <div class="jv-resume-card__acts">
        <button type="button" class="jv-btn jv-btn--primary" data-choice="accept" data-key="accept" aria-keyshortcuts="Enter">Carry on at ${weak ? target : where}${weak ? "" : html`<span class="jv-sr">, ${target}</span>`}</button>
        ${atStart(r, this.questions || []) ? "" : html`<button type="button" class="jv-btn jv-btn--quiet" data-choice="top" data-key="top">From the top</button>`}
        ${total ? html`<button type="button" class="jv-btn jv-btn--quiet" data-key="pick" data-toggle="pick" aria-expanded="${!!pick}" aria-controls="rc-pick">Another question</button>` : ""}
        <button type="button" class="jv-link jv-resume-card__why" data-key="why" data-toggle="why" aria-expanded="${!!why}" aria-controls="rc-why">Why?</button>
      </div>
      ${pick ? html`<ul class="jv-resume-card__picks" id="rc-pick" aria-label="Questions in ${t.title}">${(this.questions || []).filter((q) => !q.part).map((q) => html`
        <li><button type="button" class="jv-pill" data-choice="pick" data-label="${q.label}" data-key="q-${q.label}" aria-current="${q.label === r.label}">${(t.done || []).includes(q.label) ? html`<span class="jv-resume-card__done" aria-hidden="true">${icon("check")}</span>` : ""}${q.label}${(t.done || []).includes(q.label) ? html`<span class="jv-sr"> (done)</span>` : ""}</button></li>`)}</ul>` : ""}
      ${why ? html`<div class="jv-resume-card__whybox" id="rc-why">
        <p>${r.source === "confirmed" ? `You chose this spot ${longDay(r.at, now)} at ${clockTime(r.at)}.` : `Noticed when you stopped ${longDay(r.at, now)} at ${clockTime(r.at)}. Likely, not certain.`}</p>
        ${weak ? html`<p>The question wasn't clear from where you stopped, so this keeps to the page.</p>` : ""}
        ${viewed ? html`<p>Solutions you looked at: ${viewed}.</p>` : ""}
      </div>` : ""}
    </section>`;
  }

  rendered() {
    const img = this.$(".jv-resume-card__thumb");
    if (img) img.addEventListener("error", () => { img.hidden = true; this.$(".jv-resume-card__mono").hidden = false; }, { once: true });
  }

  _activate(e) {
    const btn = e.target.closest?.("button");
    if (!btn || !this.contains(btn)) return;
    e.stopPropagation();
    if (btn.dataset.toggle === "pick") { this._pick = !this._pick; this._render(); this.$(`[data-key="pick"]`)?.focus(); return; }
    if (btn.dataset.toggle === "why") { this._why = !this._why; this._render(); this.$(`[data-key="why"]`)?.focus(); return; }
    if (btn.dataset.choice) this.choose(btn.dataset.choice, btn.dataset.label);
  }

  /** Answer the card: it lifts at once (≤ 100 ms) and tells the reader what he chose. */
  choose(choice, label) {
    if (this.hasAttribute("lifted")) return;
    const q = label ? (this.questions || []).find((x) => x.label === label) : null;
    this.setAttribute("lifted", "");
    this.emit("jv-resume", { choice, ...(q ? { label: q.label, page: q.page, y: q.y } : {}) });
  }

  /** Focus the main answer so Enter takes it (no ring for a mouse user). */
  focusAccept() { this.$(`[data-choice="accept"]`)?.focus({ preventScroll: true, focusVisible: false }); }
}
ResumeCard.define("jv-resume-card");

// ---- gallery ----------------------------------------------------------------------------------------------
const NOW = "2026-11-16T15:40:00";
const QUESTIONS = Array.from({ length: 12 }, (_, i) => ({ label: `Q${i + 1}`, page: [1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 5, 5][i], y: 72 }));
const THREAD = {
  id: "th-pps7", kind: "pdf", ref: "file-pps7", branch: "ge-122", title: "PPS 7",
  thumb: { src: "/api/thumb/file-pps7-p3.webp", kind: "page", alt: "Page 3 of PPS 7, question 7" },
  resume: { page: 3, y: 71.2, label: "Q7", source: "inferred", at: "2026-11-14T21:14:00" },
  done: ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"], viewed: ["Q4"], state: "paused", updated: "2026-11-14T21:14:00",
};
const card = (patch = {}, props = {}) => () => el("jv-resume-card", { thread: { ...THREAD, ...patch }, questions: QUESTIONS, now: NOW, ...props });
registerGallery("resume-card", [
  { label: "Back after two days", build: card() },
  { label: "Something changed", build: card({}, { changed: "Due moved Wed 8 pm → Thu 11:59 pm" }) },
  { label: "Short break, nothing done yet", build: card({ done: [], resume: { ...THREAD.resume, at: "2026-11-16T15:10:00" } }) },
  { label: "Weak spot offers the page", build: card({ resume: { page: 3, label: "Page 3", source: "inferred", at: "2026-11-14T21:14:00" } }) },
  { label: "Weak spot on page 1: no “From the top”", build: card({ done: [], resume: { page: 1, label: "Page 1", source: "inferred", at: "2026-11-14T21:14:00" } }) },
  { label: "Why open", build: () => { const c = card()(); c._why = true; return c; } },
  { label: "Why open with others present", build: () => { const c = card({}, { private: true })(); c._why = true; return c; } },
  { label: "Another question", build: () => { const c = card()(); c._pick = true; return c; } },
  { label: "No thumbnail", build: card({ thumb: undefined }) },
], { about: "Where he stopped, behind a reopened practice set: thumb, “PPS 7 · Q7 · Tue”, one line. Never speaks.", columns: "540px" });
