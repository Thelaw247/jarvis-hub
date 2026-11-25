// <jv-branch-card>: the briefing for one branch of his life (LIFE_TREE §7), short enough for a HUD window.
//   .card = branch_card   .branch = branch   .facts = [fact] (to resolve key_facts)   .now = Date
// Shows only what a glance needs: the nearest Due (or a parent's roll-up), the Next event, one key fact,
// and Open. Everything else (open loops, people, files, the summary) is one tap away on the branch page.
// Empty sections are left out. Night: the branch's picture (branch.thumb) or its monogram leads, the name is
// in the condensed face, and the due item carries its glance code (soon within 72 h, critical when past,
// otherwise its real progress).
import { countdown, css, dueWords, hoursUntil, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { glance } from "../glance/glance.js";
import "../thumb/thumb.js";

css(import.meta.url);

/** "2d 04h" → "2 days 4 hours", for screen readers. */
const spoken = (text) => text.replace(/(\d+)d/, (_m, n) => `${+n} day${+n === 1 ? "" : "s"}`).replace(/(\d+)h/, (_m, n) => `${+n} hour${+n === 1 ? "" : "s"}`).replace(/(\d+)m\b/, (_m, n) => `${+n} minute${+n === 1 ? "" : "s"}`);

/** "2d 04h" → "2 d 4 h", the way the big countdown writes it. */
const spaced = (text) => text.replace(/(\d+)([dhm])\b/g, (_m, n, unit) => `${+n} ${unit}`);

class BranchCard extends Jv {
  static props = ["card", "branch", "facts", "now"];
  render() {
    const c = this.card, b = this.branch, now = this.now || store.now();
    if (!b) return html``;
    if (b.tier === 2 && document.documentElement.dataset.size === "ambient") return html`<p class="jv-muted">${icon("lock")} Private. Not shown on this screen.</p>`;
    const pic = b.tier === 2 ? html`<span class="jv-branch-card__glyph" aria-hidden="true">${icon("lock")}</span>`
      : html`<jv-thumb size="small" class="jv-branch-card__thumb" fallback="${b.kind === "root" ? "person" : "course"}" text="${b.kind === "leaf" ? b.name : b.glyph || b.name}"></jv-thumb>`;
    const head = html`<header class="jv-branch-card__head">${pic}
      <div class="jv-branch-card__who"><h3 class="jv-branch-card__name">${b.name}</h3><p class="jv-muted">${c?.status || b.summary || "Nothing recorded here yet."}</p></div></header>`;
    const open = html`<p class="jv-branch-card__foot"><button type="button" class="jv-btn jv-btn--small" data-nav="/life/${b.id}" data-key="open">Open ${b.name}</button></p>`;
    if (!c) return html`<article class="jv-branch-card">${head}<p class="jv-muted jv-branch-card__empty">Jarvis hasn't learned anything on this branch yet. It fills in as you use it.</p>${open}</article>`;
    const due = [...(c.due || [])].sort((x, y) => new Date(x.due) - new Date(y.due));
    const first = due[0], fact = (c.key_facts || []).map((id) => (this.facts || []).find((f) => f.id === id)).find(Boolean);
    this._fact = fact;
    const parts = [];
    if (first) {
      const hours = hoursUntil(first.due, now), soon = hours <= 72, past = hours < 0, left = countdown(first.due, now);
      const mark = past ? glance("critical", { bare: true, word: "Past due" }) : soon ? glance("soon", { bare: true, word: "Due soon" })
        : first.progress != null ? glance("progress", { bare: true, value: first.progress, word: `${Math.round(first.progress * 100)}% done` }) : "";
      parts.push(html`<section><h4 class="jv-label">${soon ? "Due soon" : "Due"}</h4>
        <p class="jv-branch-card__due">${mark}<b class="jv-branch-card__count ${soon ? "jv-branch-card__soon" : ""} ${past ? "jv-branch-card__past" : ""}" aria-label="${past ? "Past due" : `${spoken(left)} left`}">${past ? "Past due" : spaced(left)}</b></p>
        <p>${first.title} · ${dueWords(first.due)}${first.progress != null ? html` · <span class="jv-num">${Math.round(first.progress * 100)}%</span> done` : ""}</p></section>`);
    } else if (c.rollup) parts.push(html`<p class="jv-branch-card__rollup">${c.rollup}</p>`);
    const next = c.next?.[0];
    if (next) parts.push(html`<section><h4 class="jv-label">Next</h4><p class="jv-branch-card__next">${icon("calendar")}<span><span class="jv-num">${next.when}</span> · ${next.title}${next.where ? html` <span class="jv-muted">· ${next.where}</span>` : ""}</span></p></section>`);
    if (fact) parts.push(html`<section><h4 class="jv-label">Key fact</h4><p><span class="${fact.confidence === "guess" ? "jv-guess" : ""}">${fact.statement}</span> <jv-source-chip data-fact="${fact.id}"></jv-source-chip></p></section>`);
    return html`<article class="jv-branch-card">${head}${parts}${open}</article>`;
  }
  rendered() {
    this.querySelectorAll("jv-source-chip").forEach((chip) => { chip.source = this._fact?.source; });
    const pic = this.$("jv-thumb");
    if (pic && this.branch?.thumb) pic.thumb = this.branch.thumb;
  }
}
BranchCard.define("jv-branch-card");

const card = (id) => (s) => el("jv-branch-card", { card: s.cards[id], branch: s.branches.find((b) => b.id === id), facts: s.facts, now: s.now });
registerGallery("branch-card", [
  { label: "A course", build: card("ge-122") },
  { label: "A course with its picture", build: (s) => { const b = s.branches.find((x) => x.id === "chem-142"); b.thumb = { src: "/api/thumb/course-chem-142.webp", kind: "course", alt: "CHEM 142 course picture: a molecule" }; return el("jv-branch-card", { card: s.cards["chem-142"], branch: b, facts: s.facts, now: s.now }); } },
  { label: "A parent branch (roll-up)", build: card("school") },
  { label: "A project", build: card("jarvis") },
  { label: "Nothing learned yet", build: card("high-valyrian") },
], { about: "Due (or a parent\u2019s roll-up), Next, one key fact, and Open. The rest lives on the branch page.", columns: "400px" });
