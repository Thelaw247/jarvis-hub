// <jv-now-card>: what matters right now, in four short parts (plan §3: at most 4 items per panel).
//   .card = now_card contract
// No time-of-day greeting heading ("GOOD AFTERNOON" felt mechanical; the card leads with content; the window's
// kicker already says NOW). Progress comes first as one small line (the progress glance: ring + "4 of 6 done
// today"), then Next up,
// led by its title in the condensed face with its picture (next_up.thumb) or a big room code beside it, one
// flag (the "soon" glance: diamond in brackets) with a "Why?" that shows the source and ends with controls,
// things ready to offer, and what Jarvis doesn't know.
import { css, html, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { glance } from "../glance/glance.js";
import "../thumb/thumb.js";

/** A room code such as "ENGR 1A10" or "ARTS 101" (shown as a big room code, which beats a photo). */
const ROOM = /^[A-Z]{2,6}\s?\d[0-9A-Z]{1,4}$/;

css(import.meta.url);

class NowCard extends Jv {
  static props = ["card", "hide"];
  render() {
    const c = this.card;
    if (!c) return html`<jv-notice kind="empty" heading="Nothing on the card yet" text="Jarvis builds it when your day starts."></jv-notice>`;
    // .hide = "next flag": parts a window on screen already shows, so the card doesn't say them twice
    const hide = new Set(String(this.hide || "").split(/\s+/));
    const day = c.day, next = hide.has("next") ? undefined : c.next_up, flag = hide.has("flag") ? null : c.flag;
    const offers = (c.ready_to_offer || []).slice(0, 3), gaps = (c.gaps || []).slice(0, 3);
    return html`<article class="jv-now-card" aria-label="Now">
      ${day ? html`<header class="jv-now-card__head">
        <p class="jv-now-card__done">${day.total && day.done >= day.total ? glance("done", { word: `${day.done} of ${day.total} done today` }) : glance("progress", { value: day.total ? day.done / day.total : 0, word: `${day.done} of ${day.total} done today` })}</p>
      </header>` : ""}
      ${next === undefined ? "" : html`<section class="jv-now-card__part">
        <h3 class="jv-now-card__kicker">Next</h3>
        ${next ? html`<div class="jv-now-card__lead${next.thumb || ROOM.test(next.where || "") ? " jv-now-card__lead--pic" : ""}">
            ${next.thumb ? html`<jv-thumb size="small" data-thumb="next"></jv-thumb>` : ROOM.test(next.where || "") ? html`<jv-thumb size="small" fallback="room" text="${next.where}"></jv-thumb>` : ""}
            <div><p class="jv-now-card__next">${next.title}</p>
            <p class="jv-now-card__meta"><span class="jv-now-card__when">${next.when}</span>${next.where ? html` · ${next.where}` : ""} <jv-source-chip data-src="next"></jv-source-chip></p></div>
          </div>`
          : html`<p class="jv-muted">Nothing booked. The rest of the day is yours.</p>`}
      </section>`}
      ${flag ? html`<section class="jv-now-card__part jv-now-card__flag">
        <h3 class="jv-now-card__kicker">${glance("soon", { size: "rail", bare: true, word: "Needs you soon" })}One thing</h3>
        <p>${flag.text}</p>
        <details class="jv-now-card__why">
          <summary class="jv-link" data-key="why">Why?</summary>
          <p>${flag.why || "It's the closest deadline."} <jv-source-chip data-src="flag"></jv-source-chip></p>
          <p class="jv-now-card__controls">
            <button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-act="less" data-target="flag" data-key="less">Less of this</button>
            <button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-act="wrong" data-target="flag" data-key="wrong">That's wrong</button>
            ${flag.branch_id ? html`<button type="button" class="jv-btn jv-btn--small" data-nav="/life/${flag.branch_id}" data-key="open">Open it</button>` : ""}
          </p>
        </details>
      </section>` : ""}
      ${offers.length ? html`<section class="jv-now-card__part">
        <h3 class="jv-now-card__kicker">Ready when you are</h3>
        <ul class="jv-now-card__list">${offers.map((o) => html`<li>${o.path ? html`<a href="#${o.path}" data-nav="${o.path}" data-key="offer-${o.id}">${o.text}</a>` : o.text}</li>`)}</ul>
      </section>` : ""}
      ${gaps.length ? html`<section class="jv-now-card__part">
        <h3 class="jv-now-card__kicker">Not sure about</h3>
        <ul class="jv-now-card__list jv-muted">${gaps.map((g) => html`<li>${g}</li>`)}</ul>
      </section>` : ""}
    </article>`;
  }
  rendered() {
    const c = this.card;
    const pic = this.$("jv-thumb[data-thumb=next]");
    if (pic) pic.thumb = c?.next_up?.thumb;
    this.querySelectorAll("jv-source-chip").forEach((chip) => { chip.source = chip.dataset.src === "next" ? c?.next_up?.source : c?.flag?.source; });
    this.querySelectorAll("a[data-nav]").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));
  }
}
NowCard.define("jv-now-card");

const card = (change) => (state) => { const c = state.now_card; change?.(c); return el("jv-now-card", { card: c }); };
registerGallery("now-card", [
  { label: "A normal afternoon", build: card() },
  { label: "Next up with its picture", build: card((c) => { c.next_up = { ...c.next_up, title: "GE 122 lecture 22", when: "9:30 am", where: "ENGR 1A10", thumb: { src: "/api/thumb/slides-ge122-l21.webp", kind: "slide", alt: "GE 122 lecture slides: Frames and trusses" } }; }) },
  { label: "Next up in a room", build: card((c) => { c.next_up = { ...c.next_up, title: "CHEM 142 lab 5", when: "1:30 pm", where: "THORV 130" }; c.flag = null; }) },
  { label: "No flag, nothing ready", build: card((c) => { c.flag = null; c.ready_to_offer = []; }) },
  { label: "Nothing booked", build: card((c) => { c.next_up = null; c.flag = null; c.gaps = []; c.ready_to_offer = []; c.day = { done: 6, total: 6 }; }) },
  { label: "Next and the flag are already in windows", build: (state) => el("jv-now-card", { card: state.now_card, hide: "next flag" }) },
  { label: "Before the first build", build: () => el("jv-now-card", { card: null }) },
], { about: "Next up, one flag, what's ready, what's unknown. Progress first.", columns: "380px" });
