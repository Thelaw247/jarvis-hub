// Today (V02, Night pass N5b): a big "next" window first (what's next, when, where: one big thing), the day as an
// instrument (jv-timeline), proposed changes as a preview (Yes, do it · Change it · No) marked with the amber
// "your yes" square, and a lane for things that were missed or moved (dashed, "Moved"), which rebooks without
// guilt. Progress comes first: "4 of 6 done".
import { css, dayName, html, icon, Jv, shortDate } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const mins = (hhmm) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
const nice = (hhmm) => { const h = Number(hhmm.slice(0, 2)); return `${h % 12 || 12}:${hhmm.slice(3, 5)}`; };
const half = (hhmm) => (Number(hhmm.slice(0, 2)) < 12 ? "am" : "pm");
const KIND = { class: "Class", lab: "Lab", block: "Study block", own: "Yours", laundry: "Laundry" };
/** "in 20 min", "in 2 h 5 min", "now" */
export function untilWords(startMin, nowMin) {
  const d = startMin - nowMin;
  if (d <= 0) return "now";
  const h = Math.floor(d / 60), m = d % 60;
  return h ? `in ${h} h${m ? ` ${m} min` : ""}` : `in ${m} min`;
}
/** The next thing on today's plan (not done, not moved), or the one happening now. */
export function nextItem(items, nowMin) {
  const live = items.filter((i) => i.state !== "moved" && i.state !== "missed");
  return live.find((i) => i.state !== "done" && mins(i.start) <= nowMin && nowMin < mins(i.end))
    || live.filter((i) => i.state !== "done" && mins(i.start) > nowMin).sort((a, b) => mins(a.start) - mins(b.start))[0] || null;
}

class TodayView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.tweak = "";
    this.stop = store.subscribe((_s, keys) => { if (keys.has("day") || keys.has("now_card")) this.update(); });
    this.addEventListener("click", (e) => { const t = e.target.closest("[data-tweak]"); if (t) { this.tweak = t.dataset.tweak; this.update(); } });
    this.addEventListener("submit", (e) => {
      e.preventDefault();
      this.emit("jv-act", { action: "change", target: e.target.dataset.id, args: { note: e.target.elements.note.value.trim() } });
      this.tweak = ""; this.update();
    });
  }
  teardown() { this.stop?.(); }
  render() {
    const s = store.state, day = s.day, now = store.now();
    const head = (sub) => html`<header class="jv-view__head"><h1>Today</h1>${sub ? html`<p class="jv-view__sub">${sub}</p>` : ""}</header>`;
    if (!day) return html`<div class="jv-view jv-view--narrow">${head("")}<jv-notice kind="empty" heading="No plan yet" text="Jarvis builds today's plan in the morning."></jv-notice></div>`;
    const items = day.items, done = items.filter((i) => i.state === "done").length;
    const planned = items.filter((i) => i.state !== "moved" && i.state !== "missed").length;
    const moved = items.filter((i) => i.state === "moved" || i.state === "missed");
    const proposals = (day.proposals || []).slice(0, 4);
    this._proposals = proposals;
    const date = `${dayName(now)}, ${shortDate(now)}`;
    const nowMin = now.getHours() * 60 + now.getMinutes();
    const next = nextItem(items, nowMin), left = planned - done;
    this._next = next;
    // A free day: one plain card and one quiet action, no empty boxes.
    const free = html`<section class="jv-card jv-today__free" aria-labelledby="today-free"><p class="jv-kicker">Today // Free</p><h2 id="today-free">Nothing on today</h2>
      <p class="jv-muted">A free day. Jarvis won't fill it unless you ask.</p>
      <p><button type="button" class="jv-btn" data-act="ask" data-target="jarvis" data-args='{"text":"Help me plan something for today"}' data-key="plan-free">${icon("spark")}Ask Jarvis to plan something</button></p></section>`;
    if (!planned && !proposals.length && !moved.length) return html`<div class="jv-view">${head(date)}${free}</div>`;
    // the one big thing: what's next (or happening now), its time as the hero number, the room as a big code
    const live = next && mins(next.start) <= nowMin;
    const hero = next ? html`<section class="jv-frame jv-today__next" aria-labelledby="today-next">
        <div class="jv-kicker-row"><span class="jv-kicker">${live ? "Now // In progress" : `Next // ${untilWords(mins(next.start), nowMin)}`}</span><span class="jv-kicker">${KIND[next.kind] || "Event"}</span></div>
        <div class="jv-today__next-body">
          <p class="jv-today__next-time"><span class="jv-hero">${nice(next.start)}</span><span class="jv-today__half">${half(next.start)}</span><span class="jv-sr"> to ${nice(next.end)} ${half(next.end)}</span></p>
          <div class="jv-today__next-what"><h2 id="today-next" class="jv-display">${next.title}</h2>
            <p class="jv-today__next-where">${next.where ? html`<span class="jv-today__room">${next.where}</span>` : ""}<span class="jv-muted">Until ${nice(next.end)} ${half(next.end)}</span>${live ? html`<jv-glance state="progress" label="Now"></jv-glance>` : ""}</p>
            ${next.source ? html`<p><jv-source-chip data-next="1"></jv-source-chip></p>` : ""}</div></div>
        <span class="jv-meta">${planned} planned · ${left} left</span></section>`
      : planned ? html`<section class="jv-frame jv-today__next jv-today__next--clear" aria-labelledby="today-next">
          <div class="jv-kicker-row"><span class="jv-kicker">Next // Clear</span></div>
          <h2 id="today-next" class="jv-display">Nothing else today</h2><p class="jv-muted">Everything planned is behind you.</p></section>` : "";
    return html`<div class="jv-view">
      ${head(html`${date}${planned ? html` <span class="jv-today__done">${done ? html`<jv-glance state="done" label=""></jv-glance>` : ""}<span><b class="jv-num">${done} of ${planned}</b> done</span></span>` : ""}`)}
      <div class="jv-view__cols">
        <div class="jv-view__stack">
          ${hero}
          ${planned ? html`<section class="jv-sheet jv-today__plan" aria-labelledby="today-plan"><h2 id="today-plan" class="jv-view__kicker"><span class="jv-kicker">Today // ${left ? `${left} left` : "All done"}</span><span class="jv-kicker jv-kicker--end">${done} / ${planned}</span></h2><jv-timeline></jv-timeline></section>` : free}
        </div>
        <div class="jv-view__stack">
          <section aria-labelledby="today-prop"><h2 id="today-prop" class="jv-view__kicker"><span class="jv-kicker">Proposed</span>${proposals.length ? html`<span class="jv-view__count jv-view__count--waiting">${proposals.length}</span>` : ""}</h2>
            ${proposals.length ? proposals.map((p, i) => html`<article class="jv-card jv-today__proposal">
                <div class="jv-kicker-row"><span class="jv-kicker">Change // Preview</span><jv-glance state="yes" label="Your yes"></jv-glance></div>
                <h3 class="jv-today__ptitle">${p.text}</h3>
                <ul class="jv-today__changes">${p.changes.map((c) => html`<li>${c}</li>`)}</ul>
                <p class="jv-muted">${p.why}</p>
                ${p.sources?.length ? html`<p class="jv-chips">${p.sources.map((_x, j) => html`<jv-source-chip data-p="${i}" data-s="${j}"></jv-source-chip>`)}</p>` : ""}
                ${this.tweak === p.id ? html`<form class="jv-today__tweak" data-id="${p.id}"><label class="jv-today__ask" for="tweak-${p.id}">What should change?</label>
                    <input id="tweak-${p.id}" name="note" type="text" placeholder="For example: make it 10:00 am" data-key="tweak-box" autocomplete="off">
                    <p class="jv-today__buttons"><button class="jv-btn jv-btn--small jv-btn--primary" data-key="tweak-send">Ask again with that</button><button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-tweak="" data-key="tweak-cancel">Cancel</button></p></form>`
                  : html`<p class="jv-today__buttons">
                    <button type="button" class="jv-btn ${i === 0 ? "jv-btn--primary" : ""}" data-act="apply" data-target="${p.id}" data-key="apply-${p.id}">Yes, do it</button>
                    <button type="button" class="jv-btn" data-tweak="${p.id}" data-key="tweak-${p.id}">Change it</button>
                    <button type="button" class="jv-btn jv-btn--quiet" data-act="skip" data-target="${p.id}" data-key="skip-${p.id}">No</button></p>`}
              </article>`) : html`<p class="jv-today__none">Nothing to decide. When Jarvis wants to change the plan, the preview shows up here first.</p>`}
          </section>
          ${moved.length ? html`<section aria-labelledby="today-moved"><h2 id="today-moved" class="jv-view__kicker"><span class="jv-kicker">Moved // ${moved.length}</span></h2>
            <ul class="jv-today__moved">${moved.slice(0, 4).map((m) => html`<li class="jv-today__moved-row"><jv-glance state="parked" label="${m.state === "missed" ? "Missed" : "Moved"}"></jv-glance><p><b>${m.title}</b></p><p class="jv-muted">${m.moved_to || "Not rebooked yet. No rush."}</p></li>`)}</ul></section>` : ""}
        </div>
      </div></div>`;
  }
  rendered() {
    const s = store.state;
    const tl = this.$("jv-timeline");
    if (tl) Object.assign(tl, { items: s.day.items, now: store.now() });
    const chip = this.$("jv-source-chip[data-next]");
    if (chip) chip.source = this._next?.source;
    this.querySelectorAll("jv-source-chip[data-p]").forEach((chip) => { chip.source = this._proposals[chip.dataset.p].sources[chip.dataset.s]; });
    if (this.tweak) this.$("input[name=note]")?.focus();
  }
}
TodayView.define("jv-view-today");

registerScene("today", { path: "/today", about: "Timeline, one proposed change, one moved block" });
registerScene("today-quiet", { path: "/today", about: "Nothing proposed, nothing moved", patch: (s) => { s.day.proposals = []; s.day.items = s.day.items.filter((i) => i.state !== "moved"); } });
registerScene("today-morning", { path: "/today", about: "Early morning: everything ahead, the first class is next", patch: (s) => { s.now = "2026-11-16T07:50:00"; s.day.items.forEach((i) => { if (i.state === "done") i.state = "planned"; }); } });
registerScene("today-free", { path: "/today", about: "A free day", patch: (s) => { s.day.items = []; s.day.proposals = []; } });
