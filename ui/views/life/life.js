// Life (V03): his whole life as a plant. The Life Map on big screens, the outline on the phone and for the
// keyboard (toggle with L or the Map / List switch), and the branch page beside it. Breadcrumbs always say
// where you are; Esc, Backspace or a crumb goes back out. When the map would draw its labels too small
// (a narrow window, or 200% zoom) it shows the list instead, and says so.
// Night HUD (N5b): the map is drawn as a luminous constellation (see nodes.js); the branch Jarvis is on right
// now (state.focus, while it lasts) and the path down to it are cyan, so a glance says where he is working.
import { css, html, icon, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { attachZoom, fly, focusFor, mapModel, mapScale, VIEW, withPending } from "./map.js";
import { centreSvg, dotSvg, moreSvg, nodeSvg, stem } from "./nodes.js";
import "./outline.js";
import "../branch/branch.js";

css(import.meta.url);

const PREF = "jarvis.life.mode";
const pref = () => { try { return localStorage.getItem(PREF); } catch { return null; } };
/** Below this many CSS px per map unit the labels would need more room than the map has: show the list. */
export const NARROW = 0.55;
let sceneMode = null;  // set by the life-outline scene

/** The branch Jarvis means right now (state.focus.ref, if it names a branch and hasn't run out) and every branch
 *  above it: { target, path: Set }. Empty when he isn't on a branch. */
export function jarvisPath(branches, focus, now) {
  const ref = focus?.ref, live = ref && (!focus.until || new Date(focus.until) > now);
  const byId = new Map(branches.map((b) => [b.id, b])), path = new Set();
  if (!live || !byId.has(ref)) return { target: null, path };
  for (let b = byId.get(ref); b && !path.has(b.id); b = byId.get(b.parent)) path.add(b.id);
  return { target: ref, path };
}

class LifeView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.mode = new URLSearchParams(location.search).get("life") || sceneMode || (document.documentElement.dataset.size === "phone" ? "list" : pref() || "map");
    this.panel = "branch";
    this._size = document.documentElement.dataset.size;
    this.stop = store.subscribe((_s, keys) => {
      const size = document.documentElement.dataset.size, resized = size !== this._size;  // the window crossed a size (phone, laptop, full)
      this._size = size;
      if (resized) this._scale = null;
      if (resized || ["branches", "cards", "settings", "approvals", "facts", "presence", "focus"].some((k) => keys.has(k))) this.update();
    });
    this.onToggle = () => this.setMode(this.shown === "map" ? "list" : "map");
    document.addEventListener("jv-life-toggle", this.onToggle);
    this.addEventListener("click", (e) => {
      const m = e.target.closest("[data-mode]");
      if (m) this.setMode(m.dataset.mode);
      if (e.target.closest("[data-more]")) { e.preventDefault(); e.stopPropagation(); this.setMode("list"); }
      const p = e.target.closest("[data-panel]");
      if (p) { this.panel = this.panel === p.dataset.panel ? "branch" : p.dataset.panel; this.update(); }
      if (e.target.closest(".jv-map__node")) this._keep = "map";  // after flying in, focus stays in the map
      if (e.target.closest("a[data-nav]")) e.preventDefault();
    }, true);
    this.addEventListener("keydown", (e) => this.key(e));
    this.sizer = new ResizeObserver(() => this.fit());
    this.sizer.observe(this);
  }
  teardown() { this.stop?.(); this.sizer?.disconnect(); document.removeEventListener("jv-life-toggle", this.onToggle); }
  setMode(mode) { this.mode = mode; try { localStorage.setItem(PREF, mode); } catch { /* private window */ } this.update(); }

  get selected() { const id = this.params?.[0]; return store.branch(id) ? id : store.state.branches.find((b) => b.kind === "root")?.id; }
  /** What is actually drawn: the map only when there is room for it. */
  get shown() { return this.mode === "map" && !this.narrow && document.documentElement.dataset.size !== "phone" ? "map" : "list"; }
  get narrow() {
    if (document.documentElement.dataset.size === "phone") return false;
    if (this._scale == null) {  // first draw: estimate the map column from the view's own size
      const w = this.clientWidth || innerWidth, h = this.clientHeight || innerHeight;
      this._scale = mapScale(((w - 24) * 1.15) / 2.15, h - 130);
    }
    return this._scale < NARROW;
  }

  key(e) {
    if (e.target.closest?.("jv-life-outline") && (e.key === "Enter" || e.key === " ")) this._keep = "list";
    const node = e.target.closest?.(".jv-map__node");
    if (!node) return;
    const nodes = [...this.querySelectorAll(".jv-map__node")], i = nodes.indexOf(node);
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { nodes[(i + 1) % nodes.length].focus(); e.preventDefault(); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { nodes[(i - 1 + nodes.length) % nodes.length].focus(); e.preventDefault(); }
    else if (e.key === "Backspace") { const m = this._model; if (m?.parent) { this._keep = "map"; this.emit("jv-nav", { path: `/life/${m.parent.id}` }); } e.preventDefault(); }
    else if (e.key === "Enter") this._keep = "map";
    else if (e.key === " ") { this._keep = "map"; node.dispatchEvent(new MouseEvent("click", { bubbles: true })); e.preventDefault(); }
  }

  render() {
    const s = store.state, sel = this.selected;
    if (!sel) return html`<div class="jv-view jv-view--narrow"><header class="jv-view__head"><h1>Life Map</h1></header><jv-notice kind="empty" heading="Your Life Map is empty" text="It fills in as Jarvis learns your courses, projects and people."></jv-notice></div>`;
    const branches = withPending(s.branches, s.approvals);
    this._branches = branches;
    const focus = focusFor(branches, sel), m = mapModel(branches, focus);
    this._model = m;
    const trail = [...m.crumbs, ...(sel !== focus ? [branches.find((b) => b.id === sel)] : [])];
    const unsorted = s.facts.filter((f) => f.branch_id === "unsorted").length;
    const loops = Object.values(s.cards).flatMap((c) => (c.open_loops || []).map((o) => ({ ...o, branch: store.branch(c.branch_id) }))).filter((o) => o.branch);
    const ambient = document.documentElement.dataset.size === "ambient", phone = document.documentElement.dataset.size === "phone";
    const map = this.shown === "map", forced = this.mode === "map" && !map;
    const name = (b) => (b.kind === "root" ? "Life" : b.name);
    const sub = phone ? "Tap a branch to open it." : forced ? "Shown as a list: the window is too narrow for the map. Widen it to see the map."
      : map ? "Pick a branch to open it, or press L for a list." : "Arrow keys move, Enter opens. Press L for the map.";
    return html`<div class="jv-life">
      <div class="jv-life__top">
        <header class="jv-view__head jv-life__bar">
          <nav class="jv-crumbs" aria-label="Where you are">
            ${trail.map((b, i) => i === trail.length - 1 ? html`<span aria-current="page">${name(b)}</span>` : html`<a href="#/life/${b.id}" data-nav="/life/${b.id}" data-key="crumb-${b.id}">${name(b)}</a><span aria-hidden="true">›</span>`)}</nav>
          <h1>Life Map</h1>
          <p class="jv-view__sub">${sub}</p>
        </header>
        <span class="jv-life__tools">
          ${forced || phone ? "" : html`<span class="jv-seg" role="radiogroup" aria-label="Show as">
            <button type="button" role="radio" aria-checked="${String(map)}" data-mode="map" data-key="mode-map" title="Map (press L)">${icon("map")} Map</button>
            <button type="button" role="radio" aria-checked="${String(!map)}" data-mode="list" data-key="mode-list" title="List (press L)">${icon("list")} List</button></span>`}
          <button type="button" class="jv-chip" data-panel="loops" aria-pressed="${String(this.panel === "loops")}" data-key="loops">Open loops <span class="jv-num">${loops.length}</span></button>
          <a class="jv-chip jv-life__link" href="#/life/unsorted" data-nav="/life/unsorted" data-key="unsorted">Unsorted <span class="jv-num">${unsorted}</span></a>
          <a class="jv-chip jv-life__link" href="#/life/memory" data-nav="/life/memory" data-key="memory">Everything Jarvis knows</a>
        </span>
      </div>
      <div class="jv-life__body jv-life__body--${map ? "map" : "list"}">
        <section class="jv-life__tree" aria-label="${map ? "Life Map" : "Life list"}">
          ${map ? html`
            <svg class="jv-map" viewBox="${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}" role="group" aria-label="Life Map of ${m.focus.kind === "root" ? "your life" : m.focus.name}, with ${m.ring.length + (m.more ? m.more.count : 0)} branches growing from it." data-focus="${m.focus.id}">
              <g class="jv-map__viewport"><g class="jv-map__world"></g></g></svg>
            ${m.parent ? html`<a class="jv-btn jv-btn--small jv-life__back" href="#/life/${m.parent.id}" data-nav="/life/${m.parent.id}" data-key="back">${icon("undo")}Back to ${name(m.parent)}</a>` : ""}
            ${m.siblings.length ? html`<p class="jv-life__also">Also in ${name(m.parent)}: ${m.siblings.slice(0, 4).map((b, i) => html`${i ? " · " : ""}<a href="#/life/${b.id}" data-nav="/life/${b.id}" data-key="also-${b.id}">${b.name}</a>`)}</p>` : ""}
            ${m.archived.length ? html`<p class="jv-life__archived">${m.archived.length} archived here. <button type="button" class="jv-link" data-mode="list" data-key="archived">Show in the list</button></p>` : ""}`
          : html`<jv-life-outline></jv-life-outline>`}
        </section>
        <section class="jv-life__page" aria-label="${this.panel === "loops" ? "Open loops" : "Branch"}">
          ${this.panel === "loops" ? html`<div class="jv-sheet"><h2 class="jv-title">Open loops everywhere</h2>
              ${loops.length ? html`<ul class="jv-life__loops">${loops.slice(0, 8).map((o) => html`<li><a href="#/life/${o.branch.id}" data-nav="/life/${o.branch.id}" data-key="loop-${o.branch.id}-${o.text.length}">${o.text}</a><span class="jv-muted"> · ${o.branch.name}${o.slot ? ` · ${o.slot}` : ""}</span></li>`)}</ul>`
                : html`<jv-notice kind="empty" heading="No open loops" text="Nothing is hanging. Enjoy it."></jv-notice>`}</div>`
            : html`<jv-branch-page branch-id="${sel}" ${ambient ? html`shared` : ""} ${map ? html`beside-map` : ""}></jv-branch-page>`}
        </section>
      </div></div>`;
  }

  rendered() {
    const s = store.state, m = this._model, keep = this._keep;
    this._keep = null;
    const outline = this.$("jv-life-outline");
    if (outline) {
      Object.assign(outline, { branches: this._branches, selected: this.selected });
      if (keep === "list") queueMicrotask(() => outline.querySelector('[tabindex="0"]')?.focus({ preventScroll: true }));
    }
    const svg = this.$(".jv-map");
    if (!svg || !m) { this._last = null; this.fit(); return; }
    const world = svg.querySelector(".jv-map__world");
    const opts = { privateScreen: document.documentElement.dataset.size === "ambient" || !!s.presence.others, plants: s.settings.plants !== false };
    const jv = jarvisPath(s.branches, s.focus, store.now());
    world.innerHTML = m.ring.map((r) => stem(r, jv.path.has(r.branch.id))).join("") + (m.more ? stem(m.more) : "")
      + m.ring.flatMap((r) => r.dots.map(dotSvg)).join("") + centreSvg(m.focus)
      + m.ring.map((r) => nodeSvg(r, { ...opts, selected: r.branch.id === this.selected, jarvis: jv.path.has(r.branch.id) })).join("") + (m.more ? moreSvg(m.more) : "");
    this.zoomer = attachZoom(svg, svg.querySelector(".jv-map__viewport"));
    this.fit();
    // fly only when the focus changed: in from where the branch was, out when going back up
    const last = this._last, hadFocus = this._hadFocus || keep === "map";
    if (last && last.focus !== m.focus.id) {
      const from = last.spots.get(m.focus.id);
      fly(world, { from, out: !from });
      // flying out lands on the branch you came from; flying in, on the selected leaf or the first one
      if (hadFocus) (svg.querySelector(`.jv-map__node[data-id="${CSS.escape(last.focus)}"]`) || svg.querySelector(".jv-map__node--selected") || svg.querySelector(".jv-map__node"))?.focus({ preventScroll: true });
    } else if (hadFocus) (svg.querySelector(`.jv-map__node[data-id="${CSS.escape(this._focusId || "")}"]`) || svg.querySelector(".jv-map__node--selected") || svg.querySelector(".jv-map__node"))?.focus({ preventScroll: true });
    this._last = { focus: m.focus.id, spots: new Map(m.ring.map((r) => [r.branch.id, { x: r.x, y: r.y }])) };
  }

  /** Measure the map column: keep labels at their CSS size (never smaller), and switch to the list when
   *  even that wouldn't fit. Measuring only reads layout; writes happen after. */
  fit() {
    const tree = this.$(".jv-life__tree");
    if (!tree || !tree.clientWidth) return;
    const was = this.narrow, scale = mapScale(tree.clientWidth, tree.clientHeight);
    this._scale = scale;
    if (this.narrow !== was) { this.update(); return; }
    const k = Math.max(1, 1 / scale);
    for (const t of this.querySelectorAll(".jv-map__tag")) t.setAttribute("transform", `translate(${t.dataset.x} ${t.dataset.y}) scale(${k.toFixed(3)})`);
    for (const row of this.querySelectorAll(".jv-map__pills")) layoutPills(row, row.parentNode.dataset.anchor);
  }

  _render() {
    const a = document.activeElement;
    this._hadFocus = !!a?.closest?.(".jv-map");
    this._focusId = a?.dataset?.id;
    super._render();
  }
}
LifeView.define("jv-view-life");

/** Size each tag pill to its text (and its glance shape, where the theme shows one) and line them up from the
 *  label's anchor. All reads first, then the writes. */
function layoutPills(row, anchor) {
  const pills = [...row.children], gap = 6;
  const marks = pills.map((p) => { const m = p.querySelector(".jv-map__pill-mark"); return !!m && getComputedStyle(m).display !== "none"; });
  const widths = pills.map((p, i) => Math.ceil(p.querySelector("text").getComputedTextLength()) + 20 + (marks[i] ? 15 : 0));
  const total = widths.reduce((a, b) => a + b, 0) + gap * (pills.length - 1);
  let x = anchor === "end" ? -total : anchor === "middle" ? -total / 2 : 0;
  pills.forEach((p, i) => {
    p.querySelector("rect").setAttribute("x", x); p.querySelector("rect").setAttribute("y", -11); p.querySelector("rect").setAttribute("width", widths[i]);
    p.querySelector(".jv-map__pill-mark")?.setAttribute("transform", `translate(${x + 14} 0)`);
    p.querySelector("text").setAttribute("x", x + 10 + (marks[i] ? 15 : 0));
    x += widths[i] + gap;
  });
}

registerScene("life", { path: "/life", about: "The Life Map: your life as a plant, six areas growing from the pot" });
registerScene("life-school", { path: "/life/school", about: "Flown into School: a proposed branch, due tags" });
registerScene("life-fall", { path: "/life/fall-2026", about: "Eight courses: six shown, the rest under +n more" });
registerScene("life-course", { path: "/life/ge-122", about: "A course selected, its branch page beside the map" });
registerScene("life-jarvis", { path: "/life", about: "Jarvis is working on GE 122: the path to it is cyan, with a reticle on School", patch: (s) => { s.focus = { ref: "ge-122", until: "2026-11-16T23:00:00" }; } });
registerScene("life-jarvis-course", { path: "/life/fall-2026", about: "Inside Fall 2026: GE 122 is the branch Jarvis is on", patch: (s) => { s.focus = { ref: "ge-122", until: "2026-11-16T23:00:00" }; } });
registerScene("life-outline", { path: "/life/fall-2026", about: "The same tree as a list (keyboard, screen readers, phone)", patch: () => { sceneMode = "list"; } });
registerScene("life-private", { path: "/life/life", about: "Private (tier 2) branches show a lock" });
registerScene("life-projects", { path: "/life/projects", about: "Projects, with one archived" });
registerScene("life-empty", { path: "/life", about: "Before Jarvis knows anything", patch: (s) => { s.branches = []; s.cards = {}; s.facts = []; } });
