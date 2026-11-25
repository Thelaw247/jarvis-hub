// Life outline (V03c): the same tree as an indented list, for the keyboard, screen readers and the phone.
// role="tree": ↑ ↓ move, → opens a branch or steps in, ← closes or steps out, Enter opens the branch page,
// Home / End jump. Counts and badges are words ("2 due · 1 needs your yes"), never colour alone.
// Give it branches from map.js's withPending(), so "needs your yes" follows the approvals.
import { html, icon, Jv } from "../../core/dom.js";
import { byActivity } from "./map.js";

class LifeOutline extends Jv {
  static props = ["branches", "selected"];
  setup() {
    this.open = null;
    this.addEventListener("keydown", (e) => this.key(e));
    this.addEventListener("click", (e) => {
      const t = e.target.closest("[data-toggle]");
      if (t) { this.toggle(t.dataset.toggle); e.stopPropagation(); e.preventDefault(); }
    }, true);
  }
  kids(id) { return (this.branches || []).filter((b) => b.parent === id).sort((a, b) => (a.status === "archived") - (b.status === "archived") || (a.kind === "system") - (b.kind === "system") || byActivity(a, b)); }
  ensureOpen() {
    if (this.open || !(this.branches || []).length) return;
    const root = (this.branches || []).find((b) => b.kind === "root");
    this.open = new Set(root ? [root.id, this.selected] : []);  // the selected branch shows what's inside it
    for (let b = (this.branches || []).find((x) => x.id === this.selected); b; b = this.branches.find((x) => x.id === b.parent)) this.open.add(b.parent);
  }
  toggle(id) { this.ensureOpen(); if (!this.open) return; this.open.has(id) ? this.open.delete(id) : this.open.add(id); this.update(); }
  rows() {
    this.ensureOpen();
    if (!this.open) return [];
    const out = [], walk = (id, level) => { for (const b of this.kids(id)) { const kids = this.kids(b.id); out.push({ b, level, kids: kids.length }); if (kids.length && this.open.has(b.id)) walk(b.id, level + 1); } };
    const root = (this.branches || []).find((b) => b.kind === "root");
    if (root) { out.push({ b: root, level: 1, kids: this.kids(root.id).length }); if (this.open.has(root.id)) walk(root.id, 2); }
    return out;
  }
  key(e) {
    const rows = this.rows(), i = rows.findIndex((r) => r.b.id === this.cursor);
    if (i < 0) return;
    const row = rows[i];
    const go = (j) => { const next = rows[Math.max(0, Math.min(rows.length - 1, j))]; this.cursor = next.b.id; this.update(); e.preventDefault(); };
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(rows.length - 1);
    else if (e.key === "ArrowRight") { if (row.kids && !this.open.has(row.b.id)) { this.toggle(row.b.id); e.preventDefault(); } else if (row.kids) go(i + 1); }
    else if (e.key === "ArrowLeft") { if (row.kids && this.open.has(row.b.id)) { this.toggle(row.b.id); e.preventDefault(); } else { const p = rows.findIndex((r) => r.b.id === row.b.parent); if (p >= 0) go(p); } }
    else if (e.key === "Enter" || e.key === " ") { this.emit("jv-nav", { path: `/life/${row.b.id}` }); e.preventDefault(); }
  }
  render() {
    const rows = this.rows();
    if (!rows.length) return html`<jv-notice kind="empty" heading="Nothing here yet" text="Branches appear as Jarvis learns about your life."></jv-notice>`;
    if (!rows.some((r) => r.b.id === this.cursor)) this.cursor = rows.some((r) => r.b.id === this.selected) ? this.selected : rows[0].b.id;
    return html`<ul class="jv-outline" role="tree" aria-label="Your life, as a list">
      ${rows.map(({ b, level, kids }) => {
        const soon = b.due && b.due.hours <= 72;
        // each word carries its own glance shape in Night: a diamond for due soon, a hollow square for your yes
        const words = [[b.counts?.due ? `${b.counts.due} due` : b.due ? `due in ${b.due.label}` : "", soon ? "soon" : ""], [b.pending ? `${b.pending} needs your yes` : "", "yes"],
          [b.status === "proposed" ? "proposed" : "", ""], [b.status === "archived" ? "archived" : "", ""], [b.tier === 2 ? "private" : "", ""]].filter(([w]) => w);
        return html`<li role="treeitem" aria-level="${level}" ${kids ? html`aria-expanded="${this.open.has(b.id)}"` : ""} aria-selected="${b.id === this.selected}" aria-current="${b.id === this.selected ? "page" : "false"}"
            tabindex="${b.id === this.cursor ? 0 : -1}" data-key="row-${b.id}" data-nav="/life/${b.id}" class="jv-outline__row jv-outline__row--${b.status}" style="--level:${level}">
          ${kids ? html`<span class="jv-outline__twist" data-toggle="${b.id}" aria-hidden="true">${icon("chevron")}</span>` : html`<span class="jv-outline__twist"></span>`}
          <span class="jv-outline__glyph" aria-hidden="true">${icon(b.tier === 2 ? "lock" : b.kind === "root" ? "you" : "leaf")}</span>
          <span class="jv-outline__name">${b.name}</span>
          ${words.length ? html`<span class="jv-outline__words ${soon ? "jv-outline__words--soon" : ""}">${words.map(([w, kind], i) => html`${i ? " · " : ""}<span class="${kind ? `jv-outline__word jv-outline__word--${kind}` : ""}">${w}</span>`)}</span>` : ""}
        </li>`;
      })}
    </ul>`;
  }
  rendered() { if (this._hadFocus) this.querySelector('[tabindex="0"]')?.focus({ preventScroll: true }); }
  _render() { this._hadFocus = this.contains(document.activeElement); super._render(); }
}
LifeOutline.define("jv-life-outline");
