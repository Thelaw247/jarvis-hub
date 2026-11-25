// Branch page (V03d): everything about one branch, as HUD panels. At most six panels show (Status, Due,
// Next, Open loops, Key facts, Recent); People, Files, Decisions, what's missing and the Summary sit under "More".
// The children strip means drilling down never needs the map.   <jv-branch-page branch-id="ge-122">
// Private (tier 2) branches stay locked on a shared screen (attribute `shared`). Beside the Life Map
// (attribute `beside-map`) the "Inside" strip is left out: the map already shows those branches.
import { css, html, icon, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { mapChildren } from "../life/map.js";

css(import.meta.url);

/** End a line with a full stop unless it already ends a sentence. */
/** The "More" button's words. Never "More: gaps": what Jarvis doesn't know yet is "what's missing". */
const moreLabel = (parts, missing) => (parts.length ? `More: ${[...parts, missing && "what's missing"].filter(Boolean).join(", ")}` : "What's missing");
const sentence = (t) => (!t || /[.!?…)]$/.test(t) ? t : `${t}.`);

class BranchPage extends Jv {
  static attrs = ["branch-id", "shared", "beside-map"];
  setup() { this.stop = store.subscribe((_s, keys) => { if (["branches", "cards", "facts", "actions"].some((k) => keys.has(k))) this.update(); }); }
  teardown() { this.stop?.(); }
  render() {
    const s = store.state, id = this.getAttribute("branch-id"), b = store.branch(id), now = store.now();
    if (!b) return html`<jv-notice kind="empty" heading="That branch isn't here" text="It may have been renamed or archived. Search for it with Ctrl+K."></jv-notice>`;
    if (b.tier === 2 && (this.hasAttribute("shared") || s.presence.others)) {
      return html`<jv-notice kind="info" heading="${b.name} is private" text="Private branches don't open on a screen other people can see. Open it on your own laptop or phone."></jv-notice>`;
    }
    const c = s.cards[id] || {}, kids = this.hasAttribute("beside-map") ? [] : mapChildren(s.branches, id);
    const due = [...(c.due || [])].sort((x, y) => new Date(x.due) - new Date(y.due));
    this._due = due[0];
    this._facts = [...new Set([...(c.key_facts || []), ...s.facts.filter((f) => f.branch_id === id).map((f) => f.id)])].map((fid) => s.facts.find((f) => f.id === fid)).filter(Boolean).slice(0, 4);
    this._recent = (c.recent || []).map((aid) => s.actions.find((a) => a.id === aid)).filter(Boolean).slice(0, 3);
    this._files = (c.files || []).slice(0, 3);
    const more = [
      c.people?.length ? html`<jv-window heading="People"><ul class="jv-branch__list">${c.people.slice(0, 4).map((p) => html`<li>${p.name} <span class="jv-muted">· ${p.role}</span></li>`)}</ul></jv-window>` : "",
      this._files.length ? html`<jv-window heading="Files"><div class="jv-branch__files">${this._files.map((_f, i) => html`<jv-file-tile compact data-i="${i}"></jv-file-tile>`)}</div></jv-window>` : "",
      c.decisions?.length ? html`<jv-window heading="Decisions"><ul class="jv-branch__list">${c.decisions.slice(0, 4).map((d) => html`<li>${d.text} <span class="jv-branch__call">${icon("check")}Your call · ${d.date}</span></li>`)}</ul></jv-window>` : "",
      c.gaps?.length ? html`<jv-window heading="Not known yet"><ul class="jv-branch__list jv-muted">${c.gaps.slice(0, 4).map((g) => html`<li>${g}</li>`)}</ul></jv-window>` : "",
      c.story ? html`<jv-window heading="Summary, written by Jarvis"><p class="jv-read">${c.story.text}</p><p class="jv-chips jv-branch__story">${(c.story.sources || []).map((_x, i) => html`<jv-source-chip data-story="${i}"></jv-source-chip>`)}</p></jv-window>` : "",
    ].filter(Boolean);
    const empty = !c.status && !due.length && !this._facts.length;
    return html`<article class="jv-branch" aria-labelledby="branch-title">
      <header class="jv-branch__head"><span class="jv-branch__glyph" aria-hidden="true">${icon(b.tier === 2 ? "lock" : b.kind === "root" ? "you" : "leaf")}</span>
        <div><h2 id="branch-title" class="jv-branch__name">${b.kind === "root" ? "Your life" : b.name}</h2>
          <p class="jv-muted">${b.status === "proposed" ? "Not a branch yet. It only becomes one if you keep it." : c.status || b.summary || "Nothing recorded here yet."}</p></div>
        ${b.status !== "active" ? html`<span class="jv-branch__state">${b.status === "proposed" ? "Proposed" : "Archived"}</span>` : ""}</header>
      ${b.status === "proposed" ? html`<div class="jv-branch__propose"><p>Jarvis thinks this deserves its own branch. ${sentence((b.summary || "").replace(/^Proposed:\s*/i, "").replace(/^./, (ch) => ch.toUpperCase()))}</p>
        <p class="jv-chips"><button type="button" class="jv-btn jv-btn--primary" data-act="confirm" data-target="branch:${b.id}" data-key="keep">Keep it</button><button type="button" class="jv-btn" data-act="forget" data-target="branch:${b.id}" data-key="drop">No thanks</button></p></div>` : ""}
      ${empty && b.status !== "proposed" ? html`<jv-notice kind="empty" heading="Nothing here yet" text="Jarvis hasn't learned anything on this branch. It fills in as you use it; nothing is needed from you."></jv-notice>` : ""}
      <div class="jv-branch__panels">
        ${c.rollup ? html`<jv-window heading="Status" class="jv-branch__wide"><p class="jv-read">${c.rollup}</p></jv-window>` : ""}
        ${due.length ? html`<jv-window heading="Due"><jv-big-number id="branch-due"></jv-big-number>${due.length > 1 ? html`<p class="jv-muted jv-branch__then">Then ${due.slice(1, 3).map((d) => d.title).join(", ")}${due.length > 3 ? ` and ${due.length - 3} more` : ""}</p>` : ""}</jv-window>` : ""}
        ${c.next?.length ? html`<jv-window heading="Next"><ul class="jv-branch__list">${c.next.slice(0, 3).map((n) => html`<li><b class="jv-num">${n.when}</b> ${n.title}${n.where ? html` <span class="jv-muted">· ${n.where}</span>` : ""}</li>`)}</ul></jv-window>` : ""}
        ${c.open_loops?.length ? html`<jv-window heading="Open loops"><ul class="jv-branch__list">${c.open_loops.slice(0, 4).map((o) => html`<li>${o.text}${o.slot ? html`<br><span class="jv-muted">${o.slot}</span>` : ""}</li>`)}</ul></jv-window>` : ""}
        ${this._facts.length ? html`<jv-window heading="Key facts" class="jv-branch__wide"><div class="jv-branch__facts">${this._facts.map((_f, i) => html`<jv-fact-card data-i="${i}"></jv-fact-card>`)}</div>
          <p><a class="jv-link" href="#/life/memory" data-nav="/life/memory" data-key="all-facts">Everything Jarvis knows</a></p></jv-window>` : ""}
        ${this._recent.length ? html`<jv-window heading="Recent" class="jv-branch__wide">${this._recent.map((_a, i) => html`<jv-action-row data-i="${i}"></jv-action-row>`)}</jv-window>` : ""}
      </div>
      ${more.length ? html`<details class="jv-branch__more"><summary class="jv-btn jv-btn--small" data-key="more">${moreLabel([c.people?.length && "people", this._files.length && "files", c.decisions?.length && "decisions", c.story && "summary"].filter(Boolean), !!c.gaps?.length)}</summary>
        <div class="jv-branch__panels">${more}</div></details>` : ""}
      ${kids.length ? html`<nav class="jv-branch__kids" aria-label="Inside ${b.name}"><h3 class="jv-label">Inside</h3>
        <ul>${kids.slice(0, 8).map((k) => html`<li><a href="#/life/${k.id}" data-nav="/life/${k.id}" data-key="kid-${k.id}" class="jv-branch__kid jv-branch__kid--${k.status}"><span aria-hidden="true">${icon(k.tier === 2 ? "lock" : "leaf")}</span>${k.name}${k.due && k.due.hours <= 72 ? html`<span class="jv-branch__kid-due">due ${k.due.label}</span>` : ""}</a></li>`)}</ul></nav>` : ""}
      ${b.kind !== "root" && b.kind !== "system" ? html`<details class="jv-branch__settings"><summary class="jv-link" data-key="settings">Branch settings</summary>
        <p class="jv-chips">${[["edit", "Rename"], ["move", "Move"], ["set", b.tier === 2 ? "Make it not private" : "Make it private"], ["pin", "Pin to the map"], ["forget", b.status === "archived" ? "Bring back" : "Archive"]].map(([act, label]) => html`<button type="button" class="jv-btn jv-btn--small" data-act="${act}" data-target="branch:${b.id}" data-key="set-${act}">${label}</button>`)}</p>
        <p class="jv-muted">Archiving keeps everything searchable. Nothing is deleted.</p></details>` : ""}
    </article>`;
  }
  rendered() {
    const now = store.now(), s = store.state, id = this.getAttribute("branch-id");
    const due = this.$("#branch-due"); if (due) Object.assign(due, { due: this._due, now });
    this.querySelectorAll("jv-fact-card").forEach((n) => Object.assign(n, { fact: this._facts[n.dataset.i], branches: s.branches }));
    this.querySelectorAll("jv-action-row").forEach((n) => Object.assign(n, { action: this._recent[n.dataset.i], now }));
    this.querySelectorAll("jv-file-tile").forEach((n) => { n.file = this._files[n.dataset.i]; });
    this.querySelectorAll("jv-source-chip[data-story]").forEach((n) => { n.source = s.cards[id]?.story?.sources?.[n.dataset.story]; });
    this.querySelectorAll("a[data-nav]").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));
  }
}
BranchPage.define("jv-branch-page");

const page = (id, shared) => ({ render(stage) { const wrap = document.createElement("div"); wrap.className = "jv-view jv-view--narrow"; const p = document.createElement("jv-branch-page"); p.setAttribute("branch-id", id); if (shared) p.setAttribute("shared", ""); wrap.append(p); stage.replaceChildren(wrap); } });
registerScene("branch-course", { ...page("ge-122"), about: "A course: due, next, open loops, key facts, recent" });
registerScene("branch-parent", { ...page("school"), about: "A parent branch: roll-up and children" });
registerScene("branch-empty", { ...page("trips"), about: "Nothing learned yet" });
registerScene("branch-proposed", { ...page("robotics-club"), about: "A branch Jarvis proposes" });
registerScene("branch-private-shared", { ...page("money", true), about: "A private branch on a shared screen stays locked" });
