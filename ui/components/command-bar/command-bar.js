// <jv-command-bar>: Ctrl+K or "/" opens it (core/keys.js); type to go anywhere (a view, a branch, his work:
// an open thread at its resume point, something due, a file; a fact, a setting) or just type to Jarvis. Works with the keyboard alone: ↑ ↓ to move, Enter to go, Esc to close.
//   .open() / .close() / .isOpen      Emits jv-nav { path } or jv-act { action, target, args }.
// At most five results plus "Ask Jarvis", so there is never a wall of choices (Hick's law).
import { announce } from "../../core/a11y.js";
import { css, html, icon, Jv } from "../../core/dom.js";
import { TABS } from "../../core/router.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { SETTINGS } from "../../views/controls/controls.js";

css(import.meta.url);

/** Score a query against text: all letters in order; earlier and tighter matches score higher. 0 = no match. */
export function fuzzy(query, text) {
  const q = query.toLowerCase().replace(/\s+/g, ""), t = text.toLowerCase();
  if (!q) return 1;
  const at = t.indexOf(query.toLowerCase().trim());
  if (at >= 0) return 1000 - at * 2 - t.length * 0.1 + (at === 0 || /\W/.test(t[at - 1]) ? 200 : 0);
  let ti = 0, score = 0, last = -1;
  for (const ch of q) {
    ti = t.indexOf(ch, ti);
    if (ti < 0) return 0;
    score += (ti === last + 1 ? 12 : 4) + (ti === 0 || /\W/.test(t[ti - 1]) ? 8 : 0);
    last = ti; ti += 1;
  }
  return score - t.length * 0.05;
}

const DAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const dueWords = (iso) => {
  const d = new Date(iso);
  if (Number.isNaN(+d)) return "";
  const h = d.getHours(), m = d.getMinutes();
  return `due ${DAY[d.getDay()]} ${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "am" : "pm"}`;
};

/** His work: open threads (PDF, doc, study session) at their resume point, everything due, and his files.
 *  A PDF thread opens the hub's reader where he stopped (/read/<thread>); a due item or a file with a PDF
 *  thread opens that thread; the rest open their branch. Nothing private while others may see the screen. */
export function workIndex(s) {
  const shared = !!s.presence?.others || document.documentElement.dataset.size === "ambient";
  const tier2 = new Set((s.branches || []).filter((b) => b.tier === 2).map((b) => b.id));
  const hide = (branch) => shared && tier2.has(branch);
  const branchName = (id) => (s.branches || []).find((b) => b.id === id)?.name || "";
  const threads = (s.threads || []).filter((t) => t.state !== "done" && !hide(t.branch));
  const threadPath = (t) => (t.kind === "pdf" ? `/read/${t.id}` : t.branch ? `/life/${t.branch}` : "/life");
  // a due item's thread: same branch, and the due title ends with the thread's title ("GE 122 · PPS 7" → "PPS 7")
  const threadFor = (title, branch) => threads.find((t) => t.branch === branch && String(title).toLowerCase().endsWith(t.title.toLowerCase()));
  const items = threads.map((t) => ({
    kind: "Open", label: [t.title, t.resume?.label].filter(Boolean).join(" · "), path: threadPath(t), glyph: "file",
    extra: `${branchName(t.branch)} ${t.kind} resume carry on`,
  }));
  const seen = new Set();
  for (const card of Object.values(s.cards || {})) {
    for (const d of card?.due || []) {
      if (seen.has(d.id) || hide(d.branch_id)) continue;
      seen.add(d.id);
      const t = threadFor(d.title, d.branch_id);
      items.push({ kind: "Due", label: [d.title, dueWords(d.due)].filter(Boolean).join(" · "), path: t ? threadPath(t) : d.branch_id ? `/life/${d.branch_id}` : "/life",
        glyph: "book", extra: `${branchName(d.branch_id)} homework due` });
    }
  }
  for (const f of s.files || []) {
    if (hide(f.branch_id) || threads.some((t) => t.ref === f.id)) continue;  // its thread is already listed
    items.push({ kind: "File", label: f.name, path: f.branch_id ? `/life/${f.branch_id}` : "/life", glyph: "file", extra: branchName(f.branch_id) });
  }
  return items;
}

/** Everything the bar can jump to, built from the store. */
export function buildIndex(s) {
  const items = [
    ...TABS.map((t) => ({ kind: "View", label: t.label, path: t.path, glyph: "arrow" })),
    { kind: "View", label: "Everything Jarvis knows (Memory)", path: "/life/memory", glyph: "arrow", extra: "facts what jarvis knows" },
    { kind: "View", label: "Unsorted", path: "/life/unsorted", glyph: "arrow" },
    { kind: "View", label: "Under the hood", path: "/controls/hood", glyph: "gauge", extra: "latency spend credits backups" },
    { kind: "View", label: "Waiting for you", path: "/activity", glyph: "arrow", extra: "approvals yes" },
    { kind: "View", label: "Keyboard shortcuts", action: "shortcuts", glyph: "help" },
    ...s.branches.filter((b) => b.kind !== "root" && !(b.tier === 2 && document.documentElement.dataset.size === "ambient")).map((b) => ({ kind: "Branch", label: b.name, path: `/life/${b.id}`, glyph: "leaf", extra: b.id })),
    ...workIndex(s),
    ...s.facts.filter((f) => f.tier !== 2).map((f) => ({ kind: "Fact", label: f.statement, path: f.branch_id === "unsorted" ? "/life/unsorted" : `/life/${f.branch_id}`, glyph: "spark" })),
    // a setting opens Controls at its row, with its control focused (#/controls/<id>)
    ...SETTINGS.map(([id, label, extra]) => ({ kind: "Setting", label, path: `/controls/${id}`, glyph: "gauge", extra })),
    { kind: "Do", label: s.settings?.muted ? "Turn the mic on" : "Mute the mic", action: s.settings?.muted ? "unmute" : "mute", target: "mic", glyph: "mic" },
    { kind: "Do", label: "Clear the screen (everything goes to the Rail)", action: "close_all", target: "all", glyph: "close" },
  ];
  if (s.mode === "demo") items.push({ kind: "Do", label: "Restart the demo day", action: "demo", target: "restart", glyph: "play" });
  return items;
}

// ties go to views, then branches, then his work (a thread before the thing that's due, before a file)
const BONUS = { View: 5, Branch: 3, Open: 2.5, Due: 2, File: 1 };

export function search(query, index, limit = 5) {
  const q = query.trim();
  if (!q) return index.filter((i) => i.kind === "View").slice(0, limit);
  const floor = q.replace(/\s+/g, "").length * 6;  // loose letter-by-letter matches don't count
  return index.map((i) => {
    const base = Math.max(fuzzy(q, i.label), i.extra ? fuzzy(q, i.extra) * 0.8 : 0);
    return { i, score: base >= floor ? base + (BONUS[i.kind] || 0) : 0 };
  }).filter((r) => r.score > 0).sort((a, b) => b.score - a.score).slice(0, limit).map((r) => r.i);
}

class CommandBar extends Jv {
  static attrs = ["inline"];
  setup() {
    this.query = ""; this.active = 0; this.isOpen = this.hasAttribute("inline");
    this.addEventListener("input", (e) => { if (e.target.matches("input")) { this.query = e.target.value; this.active = 0; this.update(); this.sayCount(); } });
    this.addEventListener("keydown", (e) => this.key(e));
    this.addEventListener("mousedown", (e) => { if (e.target.classList.contains("jv-command-bar__scrim")) this.close(); });
    this.addEventListener("click", (e) => { const row = e.target.closest("[data-row]"); if (row) this.choose(Number(row.dataset.row)); });
  }
  open(query = "") {
    if (this.isOpen && !this.hasAttribute("inline")) return;
    this.returnTo = document.activeElement; this.query = query; this.active = 0; this.isOpen = true;
    this._render(); this.$("input")?.focus();
  }
  close() {
    if (!this.isOpen || this.hasAttribute("inline")) return;
    this.isOpen = false; clearTimeout(this._say); this._render();
    this.returnTo?.focus?.({ preventScroll: true });
  }
  /** Tell screen readers how many results there are, once typing pauses (polite, never every keystroke). */
  sayCount() {
    clearTimeout(this._say);
    this._say = setTimeout(() => {
      if (!this.isOpen || !this.query.trim()) return;
      const n = this.results().filter((r) => r.kind !== "Ask").length;
      announce(n ? `${n} result${n === 1 ? "" : "s"}` : "No results. Enter asks Jarvis.", "polite");
    }, 350);
  }
  results() {
    const found = search(this.query, buildIndex(store.state));
    return this.query.trim() ? [...found, { kind: "Ask", label: `Ask Jarvis: “${this.query.trim()}”`, action: "ask", target: "jarvis", args: { text: this.query.trim() }, glyph: "spark" }] : found;
  }
  key(e) {
    const n = this.results().length;
    if (e.key === "ArrowDown") { this.active = (this.active + 1) % n; e.preventDefault(); this.update(); }
    else if (e.key === "ArrowUp") { this.active = (this.active - 1 + n) % n; e.preventDefault(); this.update(); }
    else if (e.key === "Enter") { e.preventDefault(); this.choose(this.active); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.close(); }
    else if (e.key === "Tab") { e.preventDefault(); }  // focus stays in the bar while it is open
  }
  choose(n) {
    const item = this.results()[n];
    if (!item) return;
    this.close();
    if (item.path) this.emit("jv-nav", { path: item.path });
    else this.emit("jv-act", { action: item.action, target: item.target || "", args: item.args });
  }
  render() {
    if (!this.isOpen) return html``;
    const rows = this.results();
    return html`<div class="jv-command-bar__scrim">
      <div class="jv-command-bar" role="dialog" aria-modal="${this.hasAttribute("inline") ? "false" : "true"}" aria-label="Go anywhere or ask Jarvis">
        <label class="jv-command-bar__field">${icon("search")}<span class="jv-sr">Search views, branches, your work, facts and settings, or ask Jarvis</span>
          <input type="text" data-key="input" value="${this.query}" placeholder="Go to… or ask Jarvis" autocomplete="off" spellcheck="false"
            role="combobox" aria-expanded="true" aria-controls="jv-cmd-list" aria-activedescendant="jv-cmd-${this.active}"></label>
        <ul class="jv-command-bar__list" id="jv-cmd-list" role="listbox" aria-label="Results">
          ${rows.map((r, i) => html`<li id="jv-cmd-${i}" role="option" aria-selected="${i === this.active}" data-row="${i}" class="jv-command-bar__row">
            ${icon(r.glyph)}<span class="jv-command-bar__label">${r.label}</span><span class="jv-label jv-command-bar__kind">${r.kind}</span></li>`)}
        </ul>
        <p class="jv-command-bar__hint">↑ ↓ move · Enter go · Esc close</p>
      </div></div>`;
  }
  rendered() { const input = this.$("input"); if (input && document.activeElement === input) input.setSelectionRange(input.value.length, input.value.length); }
}
CommandBar.define("jv-command-bar");

const bar = (query) => () => { const node = el("jv-command-bar", {}, { inline: true }); queueMicrotask(() => { node.query = query; node.update(); }); return node; };
registerGallery("command-bar", [
  { label: "Just opened", build: bar("") },
  { label: "Finding a branch", build: bar("ge 1") },
  { label: "Finding a fact", build: bar("laundry") },
  { label: "Finding his work", build: bar("pps 7") },
  { label: "No match: ask Jarvis", build: bar("how long until my next lab?") },
], { about: "Ctrl+K or /. Go anywhere in two steps, or just type to Jarvis.", columns: "440px" });
