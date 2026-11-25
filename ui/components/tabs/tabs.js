// <jv-page-dots>: the five views (Now · Today · Life · Activity · Controls) as Huw's page dots, under the icon
//   row (the Rail draws one; HUD v3 §14 decision 2). The view he is on is a short bar, the others small dots.
//   .tabs = [{ id, label, path }]   .current = "life"   .badge = 2  (approvals waiting: said to screen readers on
//   Activity; the amber mark is the Your yes slot's badge, so it isn't repeated here)
// <jv-tabs>: the same five as tabs, now only the phone's bottom tab bar (an icon above each word). On every
//   other screen the header's copy is hidden: the dots replace the pills (no pills in the top-right corner).
// Both are plain links (#/path), so they work with the keyboard, Back and screen readers. Keys 1–5 are
// handled by core/keys.js (each link says so in aria-keyshortcuts); ← → Home End also move along the dots.
import { css, html, icon, Jv } from "../../core/dom.js";
import { TABS } from "../../core/router.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const GLYPH = { now: "clock", today: "calendar", life: "leaf", activity: "list", controls: "gauge" };

class Tabs extends Jv {
  static props = ["tabs", "current", "badge"];
  render() {
    const tabs = this.tabs || TABS, badge = this.badge || 0;
    return html`<nav class="jv-tabs" aria-label="Views"><ul class="jv-tabs__list">
      ${tabs.map((t, i) => html`<li><a class="jv-tabs__tab" href="#${t.path}" data-nav="${t.path}" data-key="${t.id}" title="${t.label} (press ${i + 1})" ${t.id === this.current ? html`aria-current="page"` : ""}>
        <span class="jv-tabs__glyph">${icon(GLYPH[t.id] || "arrow")}</span><span class="jv-tabs__word">${t.label}</span>${t.id === "activity" && badge ? html`<span class="jv-tabs__badge" aria-hidden="true">${badge}</span><span class="jv-sr">, ${badge} waiting for your yes</span>` : ""}</a></li>`)}
    </ul></nav>`;
  }
  setup() { this.addEventListener("click", (e) => { if (e.target.closest("a")) e.preventDefault(); }, true); }
}
Tabs.define("jv-tabs");

class PageDots extends Jv {
  static props = ["tabs", "current", "badge"];
  render() {
    const tabs = this.tabs || TABS, badge = this.badge || 0;
    return html`<nav class="jv-page-dots" aria-label="Views"><ul class="jv-page-dots__list">
      ${tabs.map((t, i) => html`<li><a class="jv-page-dots__dot" href="#${t.path}" data-nav="${t.path}" data-key="${t.id}" title="${t.label} (press ${i + 1})" aria-keyshortcuts="${i + 1}" ${t.id === this.current ? html`aria-current="page"` : ""}>
        <span class="jv-sr">${t.label}${t.id === "activity" && badge ? `, ${badge} waiting for your yes` : ""}</span></a></li>`)}
    </ul></nav>`;
  }
  setup() {
    this.addEventListener("click", (e) => { if (e.target.closest("a")) e.preventDefault(); }, true);
    // ← → Home End move along the dots (each dot is also its own Tab stop; Enter opens it)
    this.addEventListener("keydown", (e) => {
      const dots = [...this.querySelectorAll(".jv-page-dots__dot")], i = dots.indexOf(e.target.closest?.(".jv-page-dots__dot"));
      const to = i < 0 || e.altKey || e.ctrlKey || e.metaKey ? undefined : { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: dots.length - 1 }[e.key];
      if (to === undefined) return;
      e.preventDefault();
      dots[(to + dots.length) % dots.length].focus();
    });
  }
}
PageDots.define("jv-page-dots");

registerGallery("tabs", [
  { label: "Tabs, Now selected", wide: true, build: () => el("jv-tabs", { current: "now", badge: 0 }) },
  { label: "Tabs, one waiting for your yes", wide: true, build: () => el("jv-tabs", { current: "life", badge: 1 }) },
  { label: "Page dots, Now", build: () => el("jv-page-dots", { current: "now", badge: 0 }) },
  { label: "Page dots, Life", build: () => el("jv-page-dots", { current: "life", badge: 2 }) },
], { about: "Five places only. Page dots under the icon row on every screen but the phone, which keeps its tab bar. The tabs' one badge means something is waiting for your yes." });
