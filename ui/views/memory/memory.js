// "Everything Jarvis knows" (Memory) and the Unsorted tray (V03e). Both live inside Life.
//  - Memory: the fact layer, for checking and correcting. Filters (toggle buttons): All · Guesses to review ·
//    Conflicts · Recently learned. Filters by branch and source. Pause memory and Off the record are right here.
//  - Unsorted: things Jarvis couldn't place, each with its guess; one tap files it.
import { css, html, icon, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const TABS = [["all", "All"], ["guesses", "Guesses to review"], ["conflicts", "Conflicts"], ["recent", "Recently learned"]];
const PAGE = 6;
const crumbs = (here) => html`<nav class="jv-crumbs" aria-label="Where you are"><a href="#/life" data-nav="/life" data-key="crumb-life">Life</a><span aria-hidden="true">›</span><span aria-current="page">${here}</span></nav>`;
/** The shared page header: crumb → h1 → subtitle (views.css `.jv-view__head`). */
const head = (title, sub) => html`<header class="jv-view__head">${crumbs(title)}<h1>${title}</h1><p class="jv-view__sub">${sub}</p></header>`;

class MemoryView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.tab = new URLSearchParams(location.search).get("tab") || "all"; this.branch = ""; this.source = ""; this.limit = PAGE;
    this.stop = store.subscribe((_s, keys) => { if (["facts", "settings", "branches"].some((k) => keys.has(k))) this.update(); });
    this.addEventListener("click", (e) => {
      const t = e.target.closest("[data-tab]");
      if (t) { this.tab = t.dataset.tab; this.limit = PAGE; this.update(); }
      if (e.target.closest("[data-more]")) { this.limit += PAGE; this.update(); }
      if (e.target.closest("a[data-nav]")) e.preventDefault();
    });
    this.addEventListener("change", (e) => { if (e.target.name === "branch") this.branch = e.target.value; if (e.target.name === "source") this.source = e.target.value; this.limit = PAGE; this.update(); });
  }
  teardown() { this.stop?.(); }
  render() {
    const s = store.state, c = s.settings;
    const shared = document.documentElement.dataset.size === "ambient" || s.presence.others;
    const facts = s.facts.filter((f) => f.branch_id !== "unsorted" && !(shared && (f.tier === 2 || store.branch(f.branch_id)?.tier === 2)));
    const count = { all: facts.length, guesses: facts.filter((f) => f.confidence === "guess").length, conflicts: facts.filter((f) => f.conflict).length, recent: Math.min(s.learned_today || 0, facts.length) };
    let list = this.tab === "guesses" ? facts.filter((f) => f.confidence === "guess") : this.tab === "conflicts" ? facts.filter((f) => f.conflict)
      : this.tab === "recent" ? [...facts].sort((a, b) => String(b.learned).localeCompare(String(a.learned))).slice(0, Math.max(3, s.learned_today || 0)) : facts;
    if (this.branch) list = list.filter((f) => f.branch_id === this.branch);
    if (this.source) list = list.filter((f) => f.source.kind === this.source);
    this._list = list.slice(0, this.limit);
    const branchIds = [...new Set(facts.map((f) => f.branch_id))], kinds = [...new Set(facts.map((f) => f.source.kind))];
    const empty = { guesses: ["No guesses to review", "Everything here is something you said or an official source."], conflicts: ["No conflicts", "Your sources agree with each other right now."], recent: ["Nothing new today", "Jarvis hasn't learned anything yet today."], all: ["Nothing matches", "Try a different branch or source."] }[this.tab];
    return html`<div class="jv-view">
      ${head("Everything Jarvis knows", "Check it, correct it, or make Jarvis forget it.")}
      ${c.memory_paused || c.off_record ? html`<jv-notice kind="notice" heading="${c.off_record ? "Off the record" : "Memory is paused"}" text="${c.off_record ? "Nothing from this session is being kept." : "Jarvis isn't learning anything new until you turn this off."}"></jv-notice>` : ""}
      <div class="jv-memory__bar">
        <div class="jv-chips" role="group" aria-label="Which facts">${TABS.map(([id, label]) => html`<button type="button" class="jv-chip" aria-pressed="${String(this.tab === id)}" data-tab="${id}" data-key="tab-${id}">${label} <span class="jv-num">${count[id]}</span></button>`)}</div>
        <span class="jv-memory__filters">
          <label><span class="jv-sr">Branch</span><select name="branch" data-key="f-branch"><option value="">Any branch</option>${branchIds.map((id) => html`<option value="${id}" ${this.branch === id ? html`selected` : ""}>${store.branch(id)?.name || id}</option>`)}</select></label>
          <label><span class="jv-sr">Source</span><select name="source" data-key="f-source"><option value="">Any source</option>${kinds.map((k) => html`<option value="${k}" ${this.source === k ? html`selected` : ""}>${k[0].toUpperCase() + k.slice(1)}</option>`)}</select></label>
        </span>
      </div>
      ${this.tab === "guesses" && this._list.length ? html`<p class="jv-muted">A ten-second habit: confirm what's right, fix or forget the rest. Guesses never count as facts until you say so.</p>` : ""}
      ${this._list.length ? html`<div class="jv-view__grid">${this._list.map((_f, i) => html`<jv-fact-card data-i="${i}"></jv-fact-card>`)}</div>
        ${list.length > this.limit ? html`<p><button type="button" class="jv-btn jv-btn--small" data-more data-key="more">Show ${Math.min(PAGE, list.length - this.limit)} more</button></p>` : ""}`
        : html`<jv-notice kind="empty" heading="${empty[0]}" text="${empty[1]}"></jv-notice>`}
      <footer class="jv-memory__foot jv-sheet">
        <div class="jv-row"><p class="jv-row__text"><b>Pause memory</b><span>Jarvis stops learning new things until you turn this off.</span></p>
          <button type="button" class="jv-switch" role="switch" aria-checked="${!!c.memory_paused}" aria-label="Pause memory" data-act="set" data-target="memory_paused" data-args='${JSON.stringify({ value: !c.memory_paused })}' data-key="pause">${c.memory_paused ? "On" : "Off"}</button></div>
        <div class="jv-row"><p class="jv-row__text"><b>Off the record</b><span>Nothing from this session is kept.</span></p>
          <button type="button" class="jv-switch" role="switch" aria-checked="${!!c.off_record}" aria-label="Off the record" data-act="set" data-target="off_record" data-args='${JSON.stringify({ value: !c.off_record })}' data-key="off">${c.off_record ? "On" : "Off"}</button></div>
      </footer></div>`;
  }
  rendered() { this.querySelectorAll("jv-fact-card").forEach((n) => Object.assign(n, { fact: this._list[n.dataset.i], branches: store.state.branches })); }
}
MemoryView.define("jv-view-memory");

class UnsortedView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.stop = store.subscribe((_s, keys) => { if (keys.has("facts")) this.update(); });
    this.addEventListener("click", (e) => { if (e.target.closest("a[data-nav]")) e.preventDefault(); });
  }
  teardown() { this.stop?.(); }
  render() {
    const items = store.state.facts.filter((f) => f.branch_id === "unsorted").slice(0, 6);
    this._items = items;
    return html`<div class="jv-view jv-view--narrow">
      ${head("Unsorted", "Things Jarvis couldn't place with confidence. File each one, or let Jarvis forget it.")}
      ${items.length ? html`<ul class="jv-unsorted">${items.map((f, i) => { const guess = store.branch(f.guess_branch_id); return html`<li class="jv-card">
          <jv-fact-card compact data-i="${i}"></jv-fact-card>
          <div class="jv-unsorted__file">
            ${guess ? html`<p><span class="jv-label">Jarvis's guess</span> ${icon("leaf")} ${guess.name}</p>
              <button type="button" class="jv-btn ${i === 0 ? "jv-btn--primary" : ""}" data-act="file" data-target="${f.id}" data-key="file-${f.id}">File under ${guess.name}</button>` : html`<p class="jv-muted">No guess for this one.</p>`}
            <button type="button" class="jv-btn jv-btn--quiet" data-act="forget" data-target="${f.id}" data-key="forget-${f.id}">Forget it</button>
          </div></li>`; })}</ul>`
        : html`<jv-notice kind="empty" heading="Nothing to sort" text="Everything Jarvis learned has a home. New unsure items will wait here."></jv-notice>`}
    </div>`;
  }
  rendered() { this.querySelectorAll("jv-fact-card").forEach((n) => { n.fact = this._items[n.dataset.i]; }); }
}
UnsortedView.define("jv-view-unsorted");

registerScene("memory", { path: "/life/memory", about: "All facts, with filters" });
registerScene("memory-paused", { path: "/life/memory", about: "Memory paused", patch: (s) => { s.settings.memory_paused = true; } });
registerScene("memory-empty", { path: "/life/memory", about: "Nothing learned yet", patch: (s) => { s.facts = []; s.learned_today = 0; } });
registerScene("unsorted", { path: "/life/unsorted", about: "Two items with guesses" });
registerScene("unsorted-empty", { path: "/life/unsorted", about: "Nothing to sort", patch: (s) => { s.facts = s.facts.filter((f) => f.branch_id !== "unsorted"); } });
