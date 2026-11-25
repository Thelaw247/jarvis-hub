// <jv-fact-card>: one thing Jarvis knows, with where it came from and what you can do about it.
//   .fact = fact contract   .branches = [branch] (optional, enables Move)   attribute `compact` hides the actions
// Guesses get the dotted underline and say what they were guessed from. Conflicts are shown resolved his way
// with one toggle. Forget previews what else goes first. Emits jv-act: confirm, edit, pin_rule, file, forget,
// keep_mine, use_theirs. To keep a page of facts calm, Edit · Pin as rule · Move · Forget sit behind one
// "…" button; Confirm stays out on anything Jarvis isn't sure of. The card is named by its statement, and
// every button says which fact it acts on ("Edit: <fact>").
// Night HUD (N5b): a square window with a kicker (branch // confidence, "FACT" or "RULE" on the right) and its
// learned date hanging outside the frame as metadata; Daylight keeps the Earth card (the kicker and metadata
// are Night-only, everything they say is also on the card or under History).
import { css, html, icon, Jv, shortDate } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

let uid = 0;
const CONF = { sure: "Sure", likely: "Likely", guess: "Guess" };

class FactCard extends Jv {
  static props = ["fact", "branches"];
  static attrs = ["compact"];
  setup() {
    this.mode = "";
    this.uid = `fact-${++uid}`;
    this.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.mode) { this._back = true; this.mode = ""; this.update(); e.stopPropagation(); }
    });
    this.addEventListener("click", (e) => {
      const m = e.target.closest("[data-mode]");
      if (m) { this._back = !m.dataset.mode && this.mode !== "menu"; this.mode = m.dataset.mode; this.update(); e.stopPropagation(); }
    }, true);
    this.addEventListener("submit", (e) => {
      e.preventDefault();
      const f = this.fact, form = e.target;
      if (form.dataset.form === "edit") this.emit("jv-act", { action: "edit", target: f.id, args: { statement: form.elements.statement.value.trim() || f.statement } });
      if (form.dataset.form === "move") this.emit("jv-act", { action: "file", target: f.id, args: { branch_id: form.elements.branch.value } });
      this._back = true; this.mode = ""; this.update();
    });
  }
  render() {
    const f = this.fact;
    if (!f) return html``;
    const guess = f.confidence === "guess", c = f.conflict, compact = this.hasAttribute("compact");
    const other = c ? c.other_source.label : "";
    const branch = (this.branches || []).find((b) => b.id === f.branch_id);
    const kicker = html`<div class="jv-kicker-row jv-fact-card__kicker"><span class="jv-kicker">${branch ? (branch.kind === "root" ? "You" : branch.name) : "Fact"}${c ? " // Conflict" : f.confidence !== "sure" && CONF[f.confidence] ? ` // ${CONF[f.confidence]}` : ""}</span><span class="jv-kicker">${f.pinned ? "Rule" : "Fact"}</span></div>`;
    const out = f.learned ? html`<span class="jv-meta jv-fact-card__out">Added ${shortDate(f.learned)}</span>` : "";
    const body = html`
      <p class="jv-fact-card__statement" id="${this.uid}"><span class="${guess ? "jv-guess" : ""}">${f.statement}</span></p>
      <p class="jv-fact-card__meta">
        <jv-source-chip></jv-source-chip>${f.source.kind === "guess" ? "" : html`<jv-confidence level="${f.confidence}"></jv-confidence>`}
        ${f.pinned ? html`<span class="jv-fact-card__pin">${icon("pin")}Rule</span>` : ""}
        ${f.last_confirmed ? html`<span class="jv-muted jv-fact-card__when">Confirmed ${shortDate(f.last_confirmed)}</span>` : ""}
      </p>
      ${guess && f.basis ? html`<p class="jv-fact-card__basis"><span class="jv-label">Guessed from</span> ${f.basis}</p>` : ""}
      ${c ? html`<p class="jv-fact-card__conflict">${icon("alert")}<span>${c.kept === "mine" ? html`${other} says ${c.other_value}. Kept yours.` : html`Using ${other} (${c.other_value}) instead of yours.`}</span>
        <button type="button" class="jv-link" data-act="${c.kept === "mine" ? "use_theirs" : "keep_mine"}" data-target="${f.id}" data-key="conflict">${c.kept === "mine" ? `Use ${other}` : "Keep mine"}</button></p>` : ""}
      ${f.history?.length ? html`<details class="jv-fact-card__history"><summary class="jv-link" data-key="history">History</summary>
        <ul>${f.history.map((h) => html`<li class="jv-muted">Was “${h.was}” ${h.when}</li>`)}</ul></details>` : ""}`;
    if (compact) return html`<article class="jv-fact-card jv-fact-card--compact" aria-labelledby="${this.uid}">${body}</article>`;
    const about = (verb) => `${verb}: ${f.statement}`;
    const open = this.mode === "menu";
    const toggle = html`<button type="button" class="jv-btn jv-btn--small jv-btn--quiet jv-fact-card__toggle" data-mode="${open ? "" : "menu"}" aria-expanded="${String(open)}" aria-label="${about("More actions")}" title="Edit, pin, move or forget" data-key="menu">${icon("more")}</button>`;
    const confirm = f.confidence !== "sure" ? html`<button type="button" class="jv-btn jv-btn--small" data-act="confirm" data-target="${f.id}" aria-label="${about("Confirm")}" data-key="confirm">${icon("check")}Confirm</button>` : "";
    let tools;
    if (this.mode === "edit") {
      tools = html`<form class="jv-fact-card__form" data-form="edit"><label class="jv-label" for="edit-${f.id}">Correct it</label>
        <textarea id="edit-${f.id}" name="statement" rows="2" data-key="edit-box">${f.statement}</textarea>
        <p class="jv-fact-card__row"><button class="jv-btn jv-btn--small jv-btn--primary" data-key="save">Save</button><button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-mode="" data-key="cancel">Cancel</button></p></form>`;
    } else if (this.mode === "forget") {
      tools = html`<div class="jv-fact-card__form" role="group" aria-label="Forget this?">
        <p>${f.derived?.length ? html`Forgetting this also forgets: ${f.derived.join("; ")}.` : "Only this one fact will be forgotten."}</p>
        <p class="jv-fact-card__row"><button type="button" class="jv-btn jv-btn--small jv-fact-card__warn" data-act="forget" data-target="${f.id}" data-key="forget-yes">Forget it</button><button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-mode="" data-key="cancel">Keep it</button></p></div>`;
    } else if (this.mode === "move") {
      const options = (this.branches || []).filter((b) => b.kind !== "root" && b.kind !== "system" && b.status !== "archived");
      tools = html`<form class="jv-fact-card__form" data-form="move"><label class="jv-label" for="move-${f.id}">Move to</label>
        <select id="move-${f.id}" name="branch" data-key="move-box">${options.map((b) => html`<option value="${b.id}" ${b.id === (f.guess_branch_id || f.branch_id) ? html`selected` : ""}>${b.name}</option>`)}</select>
        <p class="jv-fact-card__row"><button class="jv-btn jv-btn--small jv-btn--primary" data-key="save">Move</button><button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-mode="" data-key="cancel">Cancel</button></p></form>`;
    } else if (open) {
      tools = html`<p class="jv-fact-card__row jv-fact-card__actions" role="group" aria-label="${about("Actions")}">${confirm}
        <button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-mode="edit" aria-label="${about("Edit")}" data-key="edit">${icon("edit")}Edit</button>
        <button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-act="pin_rule" data-target="${f.id}" aria-pressed="${f.pinned ? "true" : "false"}" aria-label="${about(f.pinned ? "Unpin rule" : "Pin as rule")}" data-key="pin">${icon("pin")}${f.pinned ? "Unpin rule" : "Pin as rule"}</button>
        ${this.branches ? html`<button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-mode="move" aria-label="${about("Move")}" data-key="move">${icon("move")}Move</button>` : ""}
        <button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-mode="forget" aria-label="${about("Forget")}" data-key="forget">${icon("trash")}Forget</button></p>`;
    } else {
      tools = confirm ? html`<p class="jv-fact-card__row jv-fact-card__actions">${confirm}</p>` : "";
    }
    return html`<article class="jv-fact-card ${out ? "jv-fact-card--meta" : ""}" aria-labelledby="${this.uid}">${kicker}${body}${toggle}${tools}${out}</article>`;
  }
  rendered() {
    const chip = this.$("jv-source-chip");
    if (chip) chip.source = this.fact?.source;
    if (this.mode === "edit") this.$("textarea")?.focus();
    if (this.mode === "move") this.$("select")?.focus();
    if (this._back && !this.mode) this.$("[data-key=menu]")?.focus({ preventScroll: true });  // back from a form: focus the "…" again
    this._back = false;
  }
}
FactCard.define("jv-fact-card");

const fact = (id, attrs, mode) => (s) => { const node = el("jv-fact-card", { fact: s.facts.find((f) => f.id === id), branches: s.branches }, attrs); if (mode) queueMicrotask(() => { node.mode = mode; node.update(); }); return node; };
registerGallery("fact-card", [
  { label: "Something you said (Sure)", build: fact("f-blocks") },
  { label: "From a syllabus, with evidence", build: fact("f-ge-late") },
  { label: "A guess (dotted underline)", build: fact("f-8am") },
  { label: "Conflict, kept yours", build: fact("f-ge-quiz") },
  { label: "Unexpected source", build: fact("f-sched") },
  { label: "Forget preview", build: fact("f-res", {}, "forget") },
  { label: "Editing", build: fact("f-laundry", {}, "edit") },
  { label: "Compact (in a window)", build: fact("f-ge-pps7", { compact: true }) },
  { label: "Actions open", build: fact("f-blocks", {}, "menu") },
], { about: "Statement, source, confidence in words, history. Confirm on guesses; Edit · Pin as rule · Move · Forget behind “…”.", columns: "380px" });
