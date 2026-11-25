// <jv-timeline>: the day as an instrument, then as a calm list: classes, blocks Jarvis booked, his own events.
//   .items = day.items   .now = Date   attribute `compact` (inside a window) hides the notes and the ruler
// The ruler (Night HUD, HUD v2 §5–§6): hour ticks from the first thing to the last, each item as a block (done
// filled cyan-hi, the next one cyan, the rest outlined ice) and a "now" hand. It is a picture of the list below
// (aria-hidden); the list carries every fact in words. Each row shows its state as a glance mark (shape + colour
// + word): Done, Now (in progress), Next. Moved items say where they went, without blame (Today's own lane).
import { asDate, css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const KIND = { class: ["book", "Class"], lab: ["gauge", "Lab"], block: ["spark", "Study block"], own: ["you", "Yours"], laundry: ["leaf", "Laundry"] };
const mins = (hhmm) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
// one time style across the hub: "10:00 am", "4:00 pm"
const nice = (hhmm) => { const h = Number(hhmm.slice(0, 2)); return `${h % 12 || 12}:${hhmm.slice(3, 5)} ${h < 12 ? "am" : "pm"}`; };
const hourWord = (h) => `${h % 12 || 12} ${h % 24 < 12 ? "am" : "pm"}`;
const pct = (v) => `${Math.round(v * 1000) / 10}%`;

/** The ruler's span and marks, as numbers: whole hours from the first start to the last end (and now). */
export function rulerModel(items, nowMin) {
  if (!items.length) return null;
  const from = Math.floor(Math.min(...items.map((i) => mins(i.start)), nowMin) / 60);
  const to = Math.ceil(Math.max(...items.map((i) => mins(i.end)), nowMin + 1) / 60);
  const span = Math.max(1, to - from) * 60, at = (m) => (m - from * 60) / span;
  const next = items.find((i) => i.state !== "done" && mins(i.start) > nowMin);
  return {
    from, to, now: at(nowMin),
    hours: Array.from({ length: to - from + 1 }, (_, k) => ({ h: from + k, x: k / Math.max(1, to - from) })),
    blocks: items.map((i) => {
      const live = nowMin >= mins(i.start) && nowMin < mins(i.end);
      const state = i.state === "done" ? "done" : live ? "now" : i === next ? "next" : "upcoming";
      return { id: i.id, x: at(mins(i.start)), w: Math.max(0.006, at(mins(i.end)) - at(mins(i.start))), state };
    }),
  };
}

class Timeline extends Jv {
  static props = ["items", "now"];
  static attrs = ["compact"];
  render() {
    const now = asDate(this.now || store.now()), nowMin = now.getHours() * 60 + now.getMinutes();
    const items = [...(this.items || [])].filter((i) => i.state !== "moved" && i.state !== "missed").sort((a, b) => mins(a.start) - mins(b.start));
    if (!items.length) return html`<jv-notice kind="empty" heading="Nothing on today" text="A free day. Jarvis won't fill it unless you ask."></jv-notice>`;
    const compact = this.hasAttribute("compact");
    this._items = items;
    const nowWords = nice(`${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`);
    const r = compact ? null : rulerModel(items, nowMin);
    const step = r && r.to - r.from > 10 ? 3 : 2;
    const next = items.find((i) => i.state !== "done" && mins(i.start) > nowMin);
    let lineDrawn = false;
    return html`${r ? html`<div class="jv-timeline__ruler" aria-hidden="true"><div class="jv-timeline__track">
          ${r.hours.map((t) => html`<span class="jv-timeline__hour ${(t.h - r.from) % step ? "" : "jv-timeline__hour--major"}" style="left:${pct(t.x)}"></span>${(t.h - r.from) % step || t.h === r.to ? "" : html`<span class="jv-timeline__label" style="left:${pct(t.x)}">${hourWord(t.h)}</span>`}`)}
          ${r.blocks.map((b) => html`<span class="jv-timeline__block jv-timeline__block--${b.state}" style="left:${pct(b.x)};width:${pct(b.w)}"></span>`)}
          ${r.now >= 0 && r.now <= 1 ? html`<span class="jv-timeline__hand" style="left:${pct(r.now)}"></span>` : ""}
        </div></div>` : ""}
      <ol class="jv-timeline" aria-label="Today">
      ${items.map((it) => {
        const [glyph, word] = KIND[it.kind] || KIND.own;
        const live = nowMin >= mins(it.start) && nowMin < mins(it.end);
        const done = it.state === "done";
        const marker = !lineDrawn && mins(it.start) > nowMin ? (lineDrawn = true, html`<li class="jv-timeline__now" aria-label="Now"><span class="jv-kicker">Now · ${nowWords}</span></li>`) : "";
        const mark = done ? html`<jv-glance state="done" label="Done"></jv-glance>` : live ? html`<jv-glance state="progress" label="Now"></jv-glance>`
          : it === next ? html`<span class="jv-timeline__next">Next</span>` : "";
        return html`${marker}<li class="jv-timeline__item ${done ? "jv-timeline__item--done" : ""} ${live ? "jv-timeline__item--live" : ""} ${it === next ? "jv-timeline__item--next" : ""}">
          <p class="jv-timeline__time">${nice(it.start)}<span class="jv-timeline__to"> to ${nice(it.end)}</span></p>
          <div class="jv-timeline__body">
            <p class="jv-timeline__title">${it.title}</p>
            <p class="jv-timeline__meta"><span class="jv-timeline__kind">${icon(glyph)}${word}</span>${it.where ? html`<span class="jv-timeline__where">${it.where}</span>` : ""}<jv-source-chip data-id="${it.id}"></jv-source-chip></p>
            ${it.why && !compact ? html`<details class="jv-timeline__why"><summary class="jv-link" data-key="why-${it.id}">Why this time?</summary><p class="jv-muted">${it.why}</p></details>` : ""}
          </div>
          <p class="jv-timeline__mark">${mark}</p></li>`;
      })}
    </ol>`;
  }
  rendered() { this.querySelectorAll("jv-source-chip").forEach((chip) => { chip.source = this._items.find((i) => i.id === chip.dataset.id)?.source; }); }
}
Timeline.define("jv-timeline");

registerGallery("timeline", [
  { label: "A normal day", build: (s) => el("jv-timeline", { items: s.day.items, now: s.now }) },
  { label: "In progress (during the lab)", build: (s) => el("jv-timeline", { items: s.day.items.map((i) => (i.id === "d-chem" ? { ...i, state: "planned" } : i)), now: "2026-11-16T14:10:00" }) },
  { label: "Compact (in a window)", build: (s) => el("jv-timeline", { items: s.day.items.slice(3, 6), now: s.now }, { compact: true }) },
  { label: "A free day", build: (s) => el("jv-timeline", { items: [], now: s.now }) },
], { about: "The day as an instrument (hour ticks, blocks, the now hand), then each item with its state, source and a reason for the time.", columns: "460px" });
