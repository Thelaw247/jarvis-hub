// <jv-big-number>: the one big thing a window leads with (HUD v2 §3, §8): a hero number in the condensed face,
// tabular figures, about 3× the title. For due countdowns and stats.
//   attributes: label, value, unit, sub      or      .due = { title, due, progress?, source? } and .now
// A countdown reads "2 d 4 h" (screen readers hear "2 days 4 hours left"). Within 72 hours the label is the
// "soon" glance code (diamond in brackets + "Due soon", warn); past due it is the critical code ("Now"),
// never colour alone. The number itself is always near-white (HUD v2 §14.2: never amber). `bare`: the number
// alone, as a window's hero. Progress is a segmented bar of real progress plus "50% done".
// The caption above the number is sentence case: it is a caption, not a panel title.
import { asDate, css, dueWords, hoursUntil, html, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { glance } from "../glance/glance.js";

css(import.meta.url);

/** Time left as parts ([[2, "d", "day"], [4, "h", "hour"]], at most two, a zero second part dropped) and words. */
export function timeLeft(due, now) {
  const mins = Math.max(0, Math.round((asDate(due) - asDate(now)) / 60000));
  const d = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60;
  const parts = d ? [[d, "d", "day"], [h, "h", "hour"]] : h ? [[h, "h", "hour"], [m, "min", "minute"]] : [[m, "min", "minute"]];
  const kept = parts.filter(([n], i) => n || i === 0);
  return { parts: kept, words: kept.map(([n, , word]) => `${n} ${word}${n === 1 ? "" : "s"}`).join(" ") };
}

class BigNumber extends Jv {
  static attrs = ["label", "value", "unit", "sub", "bare"];
  static props = ["due", "now"];
  render() {
    const a = (n) => this.getAttribute(n);
    const due = this.due, now = this.now || store.now(), bare = this.hasAttribute("bare");
    if (bare) {  // a window's hero (HUD v2 §14.2): the number alone; its words are the window's kicker and one line
      const left = due && hoursUntil(due.due, now) >= 0 ? timeLeft(due.due, now) : null;
      const value = due ? (left ? html`<span aria-hidden="true">${left.parts.map(([n, unit], i) => html`${i ? " " : ""}${n} <span class="jv-big-number__unit">${unit}</span>`)}</span><span class="jv-sr">${left.words} left</span>` : html`<span class="jv-big-number__words">Past due</span>`)
        : html`${a("value")}${a("unit") ? html` <span class="jv-big-number__unit">${a("unit")}</span>` : ""}`;
      return html`<div class="jv-big-number jv-big-number--bare"><p class="jv-big-number__value">${value}</p></div>`;
    }
    if (due) {
      const hours = hoursUntil(due.due, now), soon = hours <= 72 && hours >= 0, past = hours < 0;
      const pct = due.progress != null ? Math.round(due.progress * 100) : null;
      const left = past ? null : timeLeft(due.due, now);
      const value = past ? html`<span class="jv-big-number__words">Past due</span>` : html`<span aria-hidden="true">${left.parts.map(([n, unit], i) => html`${i ? " " : ""}${n} <span class="jv-big-number__unit">${unit}</span>`)}</span><span class="jv-sr">${left.words} left</span>`;
      return html`<div class="jv-big-number ${soon ? "jv-big-number--soon" : ""} ${past ? "jv-big-number--past" : ""}">
        ${soon ? html`<p class="jv-big-number__soon">${glance("soon", { word: "Due soon" })}</p>`
          : past ? html`<p class="jv-big-number__soon jv-big-number__soon--past">${glance("critical", { word: "Now" })}</p>`
          : html`<p class="jv-big-number__label">${a("label") || "Due"}</p>`}
        <p class="jv-big-number__value">${value}</p>
        <p class="jv-big-number__sub">${due.title} · ${dueWords(due.due)}</p>
        ${pct != null ? html`<div class="jv-big-number__bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="${due.title} progress" style="--p:${pct}%"></div>
          <p class="jv-big-number__pct">${glance("progress", { value: due.progress, word: `${pct}% done`, size: "rail" })}</p>` : ""}
        ${due.source ? html`<jv-source-chip></jv-source-chip>` : ""}
      </div>`;
    }
    return html`<div class="jv-big-number">
      ${a("label") ? html`<p class="jv-big-number__label">${a("label")}</p>` : ""}
      <p class="jv-big-number__value">${a("value")}${a("unit") ? html` <span class="jv-big-number__unit">${a("unit")}</span>` : ""}</p>
      ${a("sub") ? html`<p class="jv-big-number__sub">${a("sub")}</p>` : ""}
    </div>`;
  }
  rendered() { const chip = this.$("jv-source-chip"); if (chip) chip.source = this.due?.source; }
}
BigNumber.define("jv-big-number");

const due = (s, id) => s.cards["school"].due.find((d) => d.id === id);
registerGallery("big-number", [
  { label: "Due soon (within 72 h)", build: (s) => el("jv-big-number", { due: due(s, "due-pps7"), now: s.now }) },
  { label: "Due later", build: (s) => el("jv-big-number", { due: due(s, "due-webwork"), now: s.now }) },
  { label: "Past due (no blame)", build: (s) => el("jv-big-number", { due: { title: "Reading notes", due: "2026-11-15T23:59:00" }, now: s.now }) },
  { label: "A stat", build: () => el("jv-big-number", {}, { label: "Hub · event to screen", value: "35", unit: "ms", sub: "Target: under 100 ms" }) },
], { about: "One big number, one line under it." });
