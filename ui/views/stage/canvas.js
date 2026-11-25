// The window canvas (N9; moved out of the Now view): Huw's screen of windows, used by the Stage window
// (ui/views/stage/stage.js) and, with Controls › Look › "Where Jarvis shows things" = On the hub, by the hub's
// Now view (the old behaviour, with the now card as one of the panels).
//  - At most five pushed windows (six counting the now card where there is one), on a 12-column grid sized to
//    the screen so it never scrolls, clear of the bottom band (status line, Rail, the caption above it, the
//    docked orb).
//  - Nothing gets away (HUD v2 §6.2): a window that steps aside (the screen is too small) or is evicted (an
//    older hub sent a sixth) is docked into its Rail slot (`dock`, reason "aside" / "evicted"), never dropped.
//    A window recalled from the Rail grows out of its slot.
//  - One meaning per mark (HUD v2 §5), all drawn by <jv-window> from its own attributes (the canvas only sets
//    them, it hangs nothing on a window): `active` = the window Jarvis means (brighter frame, a reticle in its
//    kicker, the rest sit back; one at most); `glance` = its thing's state, where soon, your yes and critical
//    put corner brackets on it ("wants you", at most 4 on screen); `marked` = a static cyan notch, "new since
//    you looked" (cleared by keyboard focus or an 800 ms hover, `seen`); `status`, `index` and `meta` = the
//    kicker's last word, the top-right index and the line hanging under the frame.
//  - The voice and the screen move together (HUD v2 §9.1): while state.focus names a window or its thing,
//    the window is `named`: brackets snap onto it (250 ms) and its frame brightens, until `until`.
//  - On the Stage (opts.collage, HUD v3 §14.2) the windows are small glass panels in one aligned cluster left
//    of the docked orb instead of a grid: each panel gets its width tier (S, M or L), takes the height its
//    content needs, and core/windows.js cluster() places them (a 16 px gutter, masonry columns on one top
//    baseline, media large in the centre, the cluster centred; overlapping only when crowded; never over the
//    orb or the bottom row). The hub's own canvas uses the same cluster whenever windows are up. The window
//    Jarvis means is drawn on top. Windows keep their spots when another arrives (TIDY, a resize or a window
//    leaving lays the cluster out afresh). Panels have no buttons: pin and close show on hover or focus, and
//    the panel itself opens its thing (`opens`); media fill the panel edge to edge (`media`).
//  - Every window on the canvas is `clean` (§14.2): one kicker row, one hero, at most one line, one footer
//    item; sources and details wait in its "Why?" drawer (hover or keyboard focus).
//  - His hands (v0.17.0, his ask of 2026-11-21): on a board a window can be dragged anywhere and sized from its
//    corner grip; it then stays exactly where and how he left it (`held`) while the others are laid out around
//    it, until Tidy (or Home on the grip). Dragged off the edge of the screen's window it moves to the other
//    one: off the hub into the holder, off the holder back to the hub (opts.move; core/popped.js). The same by
//    keyboard on the grip: arrows size it, Shift+arrows move it, Home lets go.
// slideOrbToDock() is the wake/dock beat both screens use: the big orb pulls in and slides to the corner.
import { asDate, clockTime, css } from "../../core/dom.js";
import { bridge } from "../../core/bridge.js";
import { windowClock } from "../../core/presence.js";
import { store } from "../../core/store.js";
import { arrange, cluster, onScreen, panelWidth, roleOf, sizeOf, visible } from "../../core/windows.js";
import { nowSummary, pane, windowContent, windowKicker } from "../now/widgets.js";

css(import.meta.url);

const NOW_PANEL = { id: "__now", type: "now", size: "1x2", level: 1 };
// the smallest a grid row may get before windows are made smaller instead (canvas never scrolls)
const MIN_ROW = { laptop: 160 };
const MIN_ROW_DEFAULT = 200;  // (220 before the bottom band was reserved; 200 keeps three rows at 1440×900)
const CAPTION_ROOM = 52;  // the caption's line above the Rail (shown or not, so windows don't jump when he speaks)
const WANTS = { soon: 1, yes: 2, critical: 3 };  // the glance states that get corner brackets ("wants you")
const GLANCES = new Set(["done", "progress", "jarvis", "soon", "yes", "critical", "parked"]);
const MAX_WANTS = 4;  // at most 4 amber or red marks outside the Rail (HUD v2 §5)
const HOVER_MS = 800;  // a deliberate hover clears a "since you looked" mark
const GROW_MS = 2000;  // a window recalled within this long grows out of its Rail slot
const EDGE = 20;  // the collage keeps this far from the canvas's edges and the orb
const META = 28;  // room under each cluster panel for its footer line (below the ghost edges)
const MAX_COVERED = 0.5;  // a cluster panel more hidden than this steps aside into the Rail (if one can)
const DRAG_START = 5;  // px the pointer must travel before a press becomes a drag (a click still opens the thing)
const OFF_EDGE = 12;  // released this far outside the screen's window: it moves to the other one
const MIN_W = 220, MIN_H = 120;  // the smallest he can size a window
const STEP = 24;  // one arrow key on the grip
const KEEP_IN = 48;  // a window he placed keeps at least this much of itself on the board
// what a press may not start a drag on: its controls, anything he can type in or select, a framed page
const NO_DRAG = "button, a[href], input, select, textarea, summary, label, [data-act], [data-nav], [role=button], [role=link], [contenteditable], jv-source-chip, iframe, jv-web-frame, .jv-more";
// where he left each window, per screen (the hub's canvas and the holder's are different boards): id → { x, y, w, h }
const HELD = { hub: new Map(), stage: new Map() };

export const still = () => document.documentElement.hasAttribute("data-still");

export class WindowCanvas {
  /** host: the view element (pointer and focus are read from it); canvas: the grid element.
   *  opts.nowCard: the hub's now card is one of the panels (and the phone's fixed panels);
   *  opts.resting(): true while the screen rests (marks are never cleared then);
   *  opts.redraw(): called after a resize. */
  constructor(host, canvas, { nowCard = false, collage: board = false, resting = () => false, redraw = () => {}, only = null, move = null } = {}) {
    Object.assign(this, { host, canvas, nowCard, board, always: board, resting, redraw, only, move });
    this.held = HELD[board ? "stage" : "hub"];  // where he put windows by hand, and how big he made them
    this.windows = new Map();
    this.docking = new Set();  // windows this screen has asked the hub to dock, until they leave
    this.spots = new Map();  // cluster: where each window's top-left corner stood, so it stays put
    canvas.classList.add("jv-canvas");
    canvas.classList.toggle("jv-canvas--collage", board);
    // (the hub's own canvas is the same aligned cluster whenever windows are up; alone, its Now card rests in the
    // middle, and the phone keeps one column: draw() decides)
    this.on = {
      pointerdown: (e) => { const w = e.target.closest("jv-window[window-id]"); if (w) { this.touch(w.getAttribute("window-id")); this.press(e, w); } },
      keydown: (e) => this.gripKey(e),
      dblclick: (e) => { const w = e.target.closest?.(".jv-window__grip")?.closest("jv-window[window-id]"); if (w) this.letGo(w.getAttribute("window-id")); },
      "jv-act": (e) => {  // the window's "own window" / "back to the hub" button: this screen's business, not the hub server's
        const { action, target } = e.detail || {};
        if (action !== "popout" && action !== "popin") return;
        e.stopPropagation();
        this.send(target);
      },
      focusin: (e) => { const w = e.target.closest("jv-window[window-id]"); if (w) { this.touch(w.getAttribute("window-id")); this.seen(w); } },
      pointerover: (e) => this.hover(e.target.closest?.("jv-window[window-id]")),
      pointerleave: () => this.hover(null),
    };
    for (const [name, fn] of Object.entries(this.on)) host.addEventListener(name, fn);
    this.onRecall = (e) => { this.growFrom = { ...e.detail, at: performance.now() }; };
    document.addEventListener("jv-rail-recall", this.onRecall);
    this.onResize = () => { cancelAnimationFrame(this.resizing); this.resizing = requestAnimationFrame(() => { this.resized = true; this._fitSig = null; this.spots.clear(); this.redraw(); this.resized = false; }); };
    addEventListener("resize", this.onResize);
  }
  stop() {
    for (const [name, fn] of Object.entries(this.on)) this.host.removeEventListener(name, fn);
    document.removeEventListener("jv-rail-recall", this.onRecall);
    removeEventListener("resize", this.onResize);
    clearTimeout(this.hoverTimer); clearTimeout(this.focusTimer); cancelAnimationFrame(this._fitRaf);
  }

  touch(id) { windowClock.touch(id); if (this.activeId !== id) { this.activeId = id; this.markActive(); } }

  // ---- his hands: drag to move, the corner grip to size, off the edge to the other window --------------------
  /** Can windows be moved and sized by hand here? Only on a board (never the grid, never the phone). */
  get handy() { return this.board && document.documentElement.dataset.size !== "phone"; }

  /** Send a window to the other screen (hub ↔ holder), if this screen has one to send to. */
  send(id) {
    if (!this.move || !id) return false;
    this.held.delete(id); windowClock.keep(id, false);
    this.move(id);
    return true;
  }

  /** Let go of a window: it goes back to where Jarvis would put it, at the size its content asks for. */
  letGo(id) {
    if (!this.held.delete(id)) return;
    windowClock.keep(id, false);
    this.spots.clear(); this._fitSig = null; this.redraw();
  }
  /** Remember where he put a window or how big he made it; it then stays up until he closes it or lets it go. */
  hold(id, spot) { this.held.delete(id); this.held.set(id, spot); windowClock.keep(id); }  // re-added: the last one touched is last

  /** Keep a spot on the board: at least KEEP_IN px of the window stays inside, and its top never leaves the top. */
  clamp(x, y, w, h) {
    const box = this.canvas.getBoundingClientRect();
    return { x: Math.round(Math.min(Math.max(x, KEEP_IN - w), Math.max(0, box.width - KEEP_IN))), y: Math.round(Math.min(Math.max(y, 0), Math.max(0, box.height - KEEP_IN))) };
  }

  /** A press on a window: on its grip it sizes, elsewhere (not on a control) it may become a drag. */
  press(e, node) {
    if (!this.handy || e.button !== 0 || !e.isPrimary || node.hasAttribute("leaving")) return;
    const id = node.getAttribute("window-id"), grip = e.target.closest(".jv-window__grip");
    if (!grip && e.target.closest(NO_DRAG)) return;
    const box = this.canvas.getBoundingClientRect(), r = node.getBoundingClientRect();
    const start = { px: e.clientX, py: e.clientY, x: r.left - box.left, y: r.top - box.top, w: r.width, h: r.height };
    let moving = false;
    const move = (ev) => {
      const dx = ev.clientX - start.px, dy = ev.clientY - start.py;
      if (!moving) {
        if (!grip && Math.hypot(dx, dy) < DRAG_START) return;
        moving = true;
        node.toggleAttribute(grip ? "sizing" : "dragging", true);
        node.style.setProperty("--z", "60");
        try { node.setPointerCapture(e.pointerId); } catch { /* the pointer is gone */ }
      }
      if (grip) {
        const w = Math.round(Math.min(Math.max(MIN_W, start.w + dx), Math.max(MIN_W, box.width - start.x))), h = Math.round(Math.min(Math.max(MIN_H, start.h + dy), Math.max(MIN_H, box.height - start.y)));
        node.style.width = `${w}px`; node.style.height = `${h}px`; node.style.maxHeight = "none";
      } else {
        node.style.left = `${Math.round(start.x + dx)}px`; node.style.top = `${Math.round(start.y + dy)}px`;
        // past the edge of this screen's window: it is on its way to the other one
        node.toggleAttribute("leaving-screen", !!this.move && this.offEdge(ev));
      }
    };
    const end = (ev) => {
      if (ev.pointerId !== e.pointerId) return;
      for (const [type, fn] of listening) removeEventListener(type, fn, true);
      if (!moving) return;
      try { node.releasePointerCapture(e.pointerId); } catch { /* already released */ }
      node.removeAttribute("dragging"); node.removeAttribute("sizing"); node.removeAttribute("leaving-screen");
      // the click that ends a drag is not a click on the window (it would open its thing)
      const swallow = (c) => { c.stopPropagation(); c.preventDefault(); };
      node.addEventListener("click", swallow, { capture: true, once: true });
      setTimeout(() => node.removeEventListener("click", swallow, { capture: true }), 0);
      if (ev.type === "pointercancel") { this._fitSig = null; this.redraw(); return; }
      const now = node.getBoundingClientRect(), was = this.held.get(id) || {};
      if (grip) this.hold(id, { ...was, x: was.x ?? Math.round(start.x), y: was.y ?? Math.round(start.y), w: Math.round(now.width), h: Math.round(now.height) });
      else if (this.move && this.offEdge(ev)) { this.send(id); return; }
      else this.hold(id, { ...was, ...this.clamp(now.left - box.left, now.top - box.top, now.width, now.height) });
      this._fitSig = null; this.redraw();
    };
    // on the window, not the node: the pointer leaves a small window (or its corner grip) with its first move
    const listening = [["pointermove", (ev) => { if (ev.pointerId === e.pointerId) move(ev); }], ["pointerup", end], ["pointercancel", end]];
    for (const [type, fn] of listening) addEventListener(type, fn, true);
  }
  offEdge(ev) { return ev.clientX < -OFF_EDGE || ev.clientY < -OFF_EDGE || ev.clientX > innerWidth + OFF_EDGE || ev.clientY > innerHeight + OFF_EDGE; }

  /** The grip by keyboard: arrows size the window, Shift+arrows move it, Home lets it go. */
  gripKey(e) {
    const grip = e.target.closest?.(".jv-window__grip"), node = grip?.closest("jv-window[window-id]");
    if (!node || !this.handy || e.altKey || e.ctrlKey || e.metaKey) return;
    const id = node.getAttribute("window-id");
    if (e.key === "Home") { e.preventDefault(); this.letGo(id); return; }
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!d) return;
    e.preventDefault();
    const box = this.canvas.getBoundingClientRect(), r = node.getBoundingClientRect();
    const at = { x: r.left - box.left, y: r.top - box.top, w: r.width, h: r.height, ...this.held.get(id) };
    if (e.shiftKey) Object.assign(at, this.clamp(at.x + d[0] * STEP, at.y + d[1] * STEP, at.w, at.h));
    else { at.w = Math.round(Math.min(Math.max(MIN_W, at.w + d[0] * STEP), Math.max(MIN_W, box.width - at.x))); at.h = Math.round(Math.min(Math.max(MIN_H, at.h + d[1] * STEP), Math.max(MIN_H, box.height - at.y))); }
    this.hold(id, { x: Math.round(at.x), y: Math.round(at.y), w: Math.round(at.w), h: Math.round(at.h) });
    this.touch(id);
    this._fitSig = null; this.redraw();
  }

  /** He looked at a window's thing (keyboard focus, or a deliberate hover): clear its mark. Never while resting. */
  seen(node) {
    if (this.resting() || !node?.isConnected) return;
    const ref = markOf(this.windowById(node.getAttribute("window-id")), store.state.marks);
    if (ref) bridge.act("seen", ref);
  }
  hover(node) {
    if (node === this.hovered) return;
    this.hovered = node;
    clearTimeout(this.hoverTimer);
    if (node) this.hoverTimer = setTimeout(() => { if (this.hovered === node) this.seen(node); }, HOVER_MS);
  }
  windowById(id) { return store.state.windows.find((w) => w.id === id); }

  /** Ask the hub to dock windows this screen can't show (never more than once each). */
  dock(ids, reason) {
    for (const id of ids) {
      if (this.docking.has(id)) continue;
      this.docking.add(id);
      bridge.act("dock", id, { reason });
    }
  }

  /** → { wins: windows in placing order, lead: id of the window Jarvis is talking about } */
  shown(s = store.state) {
    const size = document.documentElement.dataset.size;
    const waiting = new Set(s.approvals.filter((a) => a.status === "pending").map((a) => a.id));
    const mine = this.only ? this.only(s.windows, s) : s.windows;  // one window: the hub and the holder each draw their own
    let { list: wins, lead, evicted } = onScreen(visible(mine, { presence: s.presence, size }), { waiting });
    if (evicted.length) this.dock(evicted, "evicted");  // only an older hub sends a sixth: it docks, never drops
    if (this.nowCard && size === "phone") {  // on the phone, everything waiting for a yes is right here, pushed or not
      const have = new Set(wins.filter((w) => w.type === "approval").map((w) => w.ref));
      wins = [...s.approvals.filter((a) => a.status === "pending" && !have.has(a.id)).map((a) => ({ id: `w-${a.id}`, type: "approval", title: "Waiting for your yes", ref: a.id, fixed: true })), ...wins,
        { id: "__quick", type: "notice", title: "Quick controls", fixed: true }];
    }
    return { wins, lead, waiting };
  }

  /** Keep the windows clear of the bottom band: the caption's line above the Rail, and the docked orb where it
   *  stands taller than the band. Sets --canvas-reserve (the canvas's bottom padding). */
  reserve() {
    const foot = document.getElementById("foot"), dock = document.getElementById("dock");
    if (!foot || document.documentElement.dataset.size === "phone") { this.canvas.style.removeProperty("--canvas-reserve"); return; }
    const top = foot.getBoundingClientRect().top;
    const orb = dock?.getBoundingClientRect();
    const over = orb && orb.height ? Math.max(0, top - orb.top + 8) : 0;  // how far the orb reaches up past the band
    this.canvas.style.setProperty("--canvas-reserve", `${Math.ceil(Math.max(CAPTION_ROOM, over))}px`);
  }

  /** How many grid rows fit on this screen without the canvas scrolling (inside the reserved band). */
  maxRows() {
    const size = document.documentElement.dataset.size;
    if (size === "phone") return Infinity;  // the phone is one scrolling column
    this.reserve();
    const cs = getComputedStyle(this.canvas), gap = parseFloat(cs.rowGap) || 0;
    const h = this.canvas.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    return Math.max(2, Math.floor((h + gap) / ((MIN_ROW[size] || MIN_ROW_DEFAULT) + gap)));
  }

  /** Draw the windows on screen. → the number of windows on the canvas (not counting the now card). */
  draw(s = store.state, { wins, lead } = this.shown(s)) {
    const now = store.now();
    const empty = !wins.length;
    this.board = this.always || (this.nowCard && !empty && document.documentElement.dataset.size !== "phone");
    this.canvas.classList.toggle("jv-canvas--collage", this.board);
    this.canvas.classList.toggle("jv-canvas--empty", empty);
    this.canvas.classList.toggle("jv-now__canvas--empty", empty && this.nowCard);
    if (lead !== this.leadId) { this.leadId = lead; if (lead) this.activeId = lead; }  // a new window is the one Jarvis means
    // the window Jarvis means goes first, then the Now card (on the hub), then the rest; ranks say what gives way first
    const count = s.windows.length;
    const panels = wins.map((w) => ({ ...w, size: sizeOf(w), level: w.id === lead || (w.type === "approval" && !w.fixed) ? 2 : 0, rank: s.windows.findIndex((x) => x.id === w.id) }));
    const card = this.nowCard ? [{ ...NOW_PANEL, rank: count }] : [];
    const ordered = panels.length ? [panels[0], ...card, ...panels.slice(1)] : card;
    // the collage has no rows: every window gets its own panel (the max-windows rule already holds)
    const fit = this.board ? { spots: [], rows: 0, sizes: new Map(), left: [] } : arrange(ordered, { maxRows: empty ? Infinity : this.maxRows() });
    const spotOf = new Map(fit.spots.map((p) => [p.id, p]));
    // windows that stepped aside dock into the Rail; only when the canvas is really laid out (never while hidden)
    if (fit.left.length && this.canvas.clientHeight > 0 && !document.hidden) this.dock(fit.left.filter((id) => !wins.find((w) => w.id === id)?.fixed), "aside");
    for (const id of this.docking) if (!s.windows.some((w) => w.id === id)) this.docking.delete(id);
    const onCanvas = wins.filter((w) => !fit.left.includes(w.id));
    const before = this.rects();
    this.canvas.style.setProperty("--rows", Math.max(fit.rows, 2));

    if (this.nowCard) this.drawNowPanel(s, onCanvas, empty ? null : spotOf.get("__now"), empty);

    const ids = new Set(onCanvas.map((w) => w.id));
    for (const [id, node] of this.windows) {
      if (ids.has(id)) continue;
      this.windows.delete(id);
      this.leave(node, onCanvas);
    }
    const grown = [];
    const things = new Map((s.threads || []).map((t) => [t.ref, t]));
    for (const win of onCanvas) {
      let node = this.windows.get(win.id);
      const sig = JSON.stringify([win.type, win.ref, win.data]);
      if (!node) {
        node = document.createElement("jv-window");
        node.setAttribute("clean", "");  // the one anatomy (HUD v2 §14.2)
        if (!win.fixed) node.setAttribute("window-id", win.id);  // fixed panels (phone) have no pin or close
        this.windows.set(win.id, node);
        this.canvas.append(node);  // arrangeDom() puts it in its place below
        if (this.growFrom?.id === win.id && performance.now() - this.growFrom.at < GROW_MS) { grown.push([node, this.growFrom.rect]); this.growFrom = null; }
      }
      const kicker = windowKicker(win, s, things.get(win.ref), now);
      for (const name of ["heading", "status", "index", "meta"]) setAttr(node, name, kicker[name]);
      node.toggleAttribute("pinned", !!win.pinned);
      const hands = !win.fixed && (this.always || this.board) && document.documentElement.dataset.size !== "phone";
      node.toggleAttribute("sizable", hands);  // its corner grip
      setAttr(node, "pop", hands && this.move ? (this.always ? "in" : "out") : null);  // its "own window" / "back to the hub" button
      // rebuild the content only when what it shows changed; otherwise just hand it fresh data
      const stamp = `${sig}|${dataStamp(win, s)}`;
      if (win.id === "__quick") { if (!node.dataset.stamp) { node.dataset.stamp = "q"; node.setContent(document.createElement("jv-quick-controls")); } }
      else if (node.dataset.stamp !== stamp) { node.dataset.stamp = stamp; node.setContent(windowContent(win, s, now)); }
      if (!this.board) place(node, spotOf.get(win.id), fit.sizes.get(win.id));
    }
    // keep the DOM (and so the Tab order and what a screen reader reads) in the order things are placed
    const nodes = onCanvas.map((w) => this.windows.get(w.id));
    this.arrangeDom(this.nowPanel ? [...nodes.slice(0, 1), this.nowPanel, ...nodes.slice(1)] : nodes);
    const said = s.focus?.ref && (!s.focus.until || asDate(s.focus.until) > now) ? onCanvas.find((w) => w.id === s.focus.ref || w.ref === s.focus.ref) : null;
    if (said) this.activeId = said.id;  // the window Jarvis is naming is the one he means (the reticle follows the voice)
    if (this.activeId && !ids.has(this.activeId)) this.activeId = lead && ids.has(lead) ? lead : onCanvas[0]?.id;
    this.markActive();
    this.markThings(onCanvas, s);
    if (this.board) this.layoutBoard(onCanvas, s, lead); else this.fit(onCanvas, s, lead);
    this.glide(before);
    for (const [node, rect] of grown) node.assemble({ from: rect });  // a recalled window grows out of its Rail slot
    if (this.activeId !== this._shownActive) {  // bring the window Jarvis means into view (the phone scrolls)
      this._shownActive = this.activeId;
      this.windows.get(this.activeId)?.scrollIntoView({ block: "nearest", behavior: still() ? "auto" : "smooth" });
    }
    return onCanvas.length;
  }

  /** Nothing is cut silently (film review M2): measure each window's content against its area. A window
   *  that doesn't fit first goes compact (data-fit="compact": its secondary rows drop, see window.css); if one
   *  still doesn't fit, the oldest unpinned window that isn't the one Jarvis means or a question steps aside
   *  into its Rail slot (reason "aside") rather than this one shrinking further. When nothing can step aside,
   *  the window says so (data-clipped: a fade and "More" at its foot). Measured only when what is on the
   *  canvas or the screen size changed, and once more on the next frame (late fonts and pictures). */
  fit(onCanvas, s, lead, again = false) {
    const root = document.documentElement;
    const nodes = onCanvas.map((w) => [w, this.windows.get(w.id)]).filter(([, n]) => n && !n.hasAttribute("leaving"));
    const sig = JSON.stringify([innerWidth, innerHeight, root.dataset.size, onCanvas.map((w) => [w.id, this.windows.get(w.id)?.dataset.stamp, this.windows.get(w.id)?.style.gridArea])]);
    if (!again && sig === this._fitSig) return;
    this._fitSig = sig;
    for (const [, n] of nodes) { delete n.dataset.fit; n.removeAttribute("data-clipped"); }
    if (root.dataset.size === "phone" || !this.canvas.clientHeight || document.hidden) return;
    const over = (n) => n.body && n.body.scrollHeight - n.body.clientHeight > 2;
    let tight = nodes.filter(([, n]) => over(n));
    tight.forEach(([, n]) => { n.dataset.fit = "compact"; });
    tight = tight.filter(([, n]) => over(n));
    if (!again) { cancelAnimationFrame(this._fitRaf); this._fitRaf = requestAnimationFrame(() => { if (this._fitSig === sig) this.fit(onCanvas, s, lead, true); }); }
    if (!tight.length) return;
    const waiting = new Set(s.approvals.filter((a) => a.status === "pending").map((a) => a.id));
    const rank = (w) => s.windows.findIndex((x) => x.id === w.id);
    const aside = onCanvas.filter((w) => !w.fixed && !w.pinned && w.id !== lead && !(w.type === "approval" && waiting.has(w.ref)) && !this.docking.has(w.id))
      .sort((a, b) => rank(a) - rank(b))[0];
    if (aside && onCanvas.length > 1) { this.dock([aside.id], "aside"); return; }
    tight.forEach(([, n]) => n.setAttribute("data-clipped", ""));
  }

  /** The Stage's cluster (HUD v3 §14.2): give each panel its width tier and what it leads with (media, a chart,
   *  a number or a title), let it take the height its content needs, then place them all with cluster(). The
   *  window Jarvis means is drawn on top; the rest keep their spots when another arrives, and the cluster is
   *  laid out afresh when one leaves. A panel left more than half hidden makes the oldest window that may step
   *  aside dock into the Rail; one whose content still can't fit says so ("More"). Measured when what is on
   *  the board or the screen changed, and once more on the next frame (late fonts). */
  layoutBoard(onCanvas, s, lead, again = false) {
    const root = document.documentElement;
    const nodes = onCanvas.map((w) => [w, this.windows.get(w.id)]).filter(([, n]) => n && !n.hasAttribute("leaving"));
    if (this.nowPanel) nodes.push([{ id: NOW_PANEL.id, type: "now", fixed: true }, this.nowPanel]);  // the hub's Now card is one of the panels
    const nodeOf = new Map(nodes.map(([w, n]) => [w.id, n]));
    const ids = new Set(nodes.map(([w]) => w.id));
    let gone = false;
    for (const id of [...this.spots.keys()]) if (!ids.has(id)) { this.spots.delete(id); gone = true; }
    for (const id of [...this.held.keys()]) if (!s.windows.some((w) => w.id === id)) this.held.delete(id);  // it closed: nothing to hold
    if (gone && nodes.every(([w]) => this.spots.has(w.id))) this.spots.clear();  // one left and none came: close the gap
    const sig = JSON.stringify([innerWidth, innerHeight, root.dataset.size, lead, nodes.map(([w, n]) => [w.id, n.dataset.stamp ?? n.textContent]), [...this.held]]);
    if (!again && sig === this._fitSig) return;
    this._fitSig = sig;
    const room = this.room();
    if (!nodes.length || !room) return;
    const { area, keepOut } = room, width = area.right - area.left;
    const roles = new Map();
    for (const [w, n] of nodes) {  // writes first ...
      const thumb = n.querySelector("jv-thumb.jv-pane__media");
      const role = roleOf(w, { picture: w.type !== "file" || !!thumb });
      roles.set(w.id, role);
      // tiers go by content: a few words are small, a sentence medium, media large
      const hero = n.querySelector(".jv-pane__title")?.textContent || "", line = n.querySelector(".jv-pane__line:not([hidden])")?.textContent || "";
      const short = role === "title" && hero.length <= 20 && line.length <= 34;
      n.toggleAttribute("media", role === "media");
      n.toggleAttribute("sheer", role === "number");
      n.toggleAttribute("opens", true);
      const mine = this.held.get(w.id);  // he sized it: that is its size
      n.toggleAttribute("held", !!mine);
      n.toggleAttribute("sized", !!mine?.h);
      n.style.width = `${mine?.w ? Math.min(mine.w, Math.max(MIN_W, width)) : panelWidth(w, width, { picture: !!thumb, short })}px`;
      n.style.maxHeight = mine?.h ? "none" : `${Math.max(120, area.bottom - area.top - META)}px`;
      if (mine?.h) n.style.height = `${mine.h}px`; else n.style.removeProperty("height");
      delete n.dataset.fit;
      n.removeAttribute("data-clipped");
    }
    const over = (n) => n.body && n.body.scrollHeight - n.body.clientHeight > 2;  // ... then reads
    nodes.filter(([, n]) => over(n)).forEach(([, n]) => { n.dataset.fit = "compact"; });
    const waiting = new Set(s.approvals.filter((a) => a.status === "pending").map((a) => a.id));
    const rank = (w) => s.windows.findIndex((x) => x.id === w.id);
    const first = (w) => (w.id === lead ? 0 : w.type === "approval" && waiting.has(w.ref) ? 1 : 2);  // then the newest first
    const order = [...nodes].sort(([a], [b]) => first(a) - first(b) || rank(b) - rank(a));
    if (!again) this._fresh = !nodes.some(([w]) => this.spots.has(w.id));
    else if (this._fresh) this.spots.clear();  // late fonts or pictures: the fresh cluster is measured again
    // a window he placed is not the cluster's to place: the others are laid out as if it weren't there, and it
    // sits where he left it, on top of them if it must (a board with only his own windows has no cluster at all)
    const placed = (id) => this.held.get(id)?.x != null;
    const panels = order.filter(([w]) => !placed(w.id)).map(([w, n]) => ({ id: w.id, w: n.offsetWidth, h: n.offsetHeight, centre: roles.get(w.id) === "media", prev: this.spots.get(w.id) }));
    const spots = panels.length ? cluster(panels, { area, keepOut, foot: META }) : [];
    for (const spot of spots) {
      const n = nodeOf.get(spot.id), want = panels.find((p) => p.id === spot.id);
      n.style.left = `${spot.x}px`;
      n.style.top = `${spot.y}px`;
      n.style.setProperty("--z", String(spot.z));
      n.dataset.col = String(spot.col);
      if (spot.h < want.h && !this.held.get(spot.id)?.h) n.style.height = `${spot.h}px`;
      this.spots.set(spot.id, { x: spot.x, y: spot.y });  // its top-left corner
    }
    for (const [w, n] of order) {
      if (!placed(w.id)) continue;
      const mine = this.held.get(w.id), at = this.clamp(mine.x, mine.y, n.offsetWidth, n.offsetHeight);
      n.style.left = `${at.x}px`;
      n.style.top = `${at.y}px`;
      n.style.setProperty("--z", String(20 + [...this.held.keys()].indexOf(w.id)));  // above the cluster; the one he touched last on top
      delete n.dataset.col;
    }
    if (!again) { cancelAnimationFrame(this._fitRaf); this._fitRaf = requestAnimationFrame(() => { if (this._fitSig === sig) this.layoutBoard(onCanvas, s, lead, true); }); }
    // crowded: a panel more than half hidden makes the oldest that may step aside dock into its Rail slot
    if (spots.some((p) => p.covered > MAX_COVERED) && nodes.length > 1) {
      const aside = onCanvas.filter((w) => !w.fixed && !w.pinned && w.id !== lead && !(w.type === "approval" && waiting.has(w.ref)) && !this.docking.has(w.id))
        .sort((a, b) => rank(a) - rank(b))[0];
      if (aside) { this.dock([aside.id], "aside"); return; }
    }
    nodes.filter(([, n]) => over(n)).forEach(([, n]) => n.setAttribute("data-clipped", ""));
  }

  /** The collage's room, in canvas pixels: the canvas less its edges and the caption's line above the bottom row,
   *  and what nothing may cover (the docked orb, the Stage's few words top-right). Null when not laid out. */
  room() {
    const box = this.canvas.getBoundingClientRect();
    if (!box.width || !box.height) return null;
    const local = (r, by = 0) => ({ left: r.left - box.left - by, top: r.top - box.top - by, right: r.right - box.left + by, bottom: r.bottom - box.top + by });
    const foot = document.getElementById("foot")?.getBoundingClientRect();
    const bottom = foot?.height ? Math.min(box.height, foot.top - box.top - CAPTION_ROOM) : box.height - EDGE;
    const area = { left: EDGE, top: 12, right: box.width - EDGE, bottom: Math.max(160, bottom) };
    const keepOut = [document.getElementById("dock"), ...this.host.querySelectorAll("[data-keep-clear]")]
      .map((n) => n?.getBoundingClientRect()).filter((r) => r?.width && r.height).map((r) => local(r, EDGE));
    return { area, keepOut };
  }

  /** TIDY: lay the board out afresh, his own placing and sizing included (the order they came is the store's; see stage.js). */
  tidy() { for (const id of this.held.keys()) windowClock.keep(id, false); this.held.clear(); this.spots.clear(); this._fitSig = null; this.redraw(); }

  /** The hub's now card as a panel (and the quiet clock above it when nothing is pushed). */
  drawNowPanel(s, onCanvas, spot, empty) {
    if (!this.nowPanel) {
      this.clock = document.createElement("jv-clock");
      this.clock.setAttribute("live", "");
      this.clock.className = "jv-now__clock";
      this.nowPanel = document.createElement("jv-window");
      this.nowPanel.setAttribute("heading", "Now");
      this.nowPanel.setAttribute("clean", "");
      this.nowPanel.className = "jv-now__card";
      // the one anatomy: the next thing and one line; the whole card waits in the "Why?" drawer
      this.nowHero = Object.assign(document.createElement("h3"), { className: "jv-pane__title" });
      this.nowPanel.append(pane("title", this.nowHero, " ", [document.createElement("jv-now-card")]));
      this.canvas.append(this.clock, this.nowPanel);
    }
    this.clock.hidden = !empty;
    if (!this.board) for (const k of ["left", "top", "width", "max-height", "height", "--z"]) this.nowPanel.style.removeProperty(k);
    const hide = shownElsewhere(onCanvas, s), sum = nowSummary(s.now_card, new Set(hide));
    Object.assign(this.nowPanel.querySelector("jv-now-card"), { hide: hide.join(" "), card: s.now_card });
    if (this.nowHero.textContent !== sum.hero) this.nowHero.textContent = sum.hero;
    this.nowHero.classList.toggle("jv-pane__title--number", !!sum.number);
    const line = this.nowPanel.querySelector(".jv-pane__line");
    if (line.textContent !== sum.line) line.textContent = sum.line;
    line.hidden = !sum.line;
    const day = s.now_card?.day;
    setAttr(this.nowPanel, "status", sum.number ? "Today" : hide.includes("next") || !s.now_card?.next_up ? "" : "Next");
    setAttr(this.nowPanel, "index", day?.total && !sum.number ? `${day.done} / ${day.total}` : "");
    setAttr(this.nowPanel, "meta", s.now ? `As of ${clockTime(s.now)}` : "");  // its one footer item
    setAttr(this.nowPanel, "glance", !hide.includes("flag") && s.now_card?.flag && (hide.includes("next") || !s.now_card?.next_up) ? "soon" : null);
    place(this.nowPanel, spot);
  }

  /** Put the windows in `order` (after the clock, on the hub), moving as few as possible (the ones already in
   *  the right order stay put), and give focus back if a move took it away. */
  arrangeDom(order) {
    const kids = [...this.canvas.children];
    const at = order.map((n) => kids.indexOf(n));
    // the longest run already in order (by DOM position) stays; everything else is inserted around it
    const best = at.map(() => 1), prev = at.map(() => -1);
    at.forEach((a, i) => { for (let j = 0; j < i; j++) if (a >= 0 && at[j] >= 0 && at[j] < a && best[j] + 1 > best[i]) { best[i] = best[j] + 1; prev[i] = j; } });
    const keep = new Set();
    for (let i = at.reduce((m, a, k) => (a >= 0 && (m < 0 || best[k] > best[m]) ? k : m), -1); i >= 0; i = prev[i]) keep.add(order[i]);
    const focused = document.activeElement;
    let after = this.clock || null;
    for (const node of order) {
      if (!keep.has(node)) {
        if (after) { if (after.nextElementSibling !== node) after.after(node); }
        else if (this.canvas.firstElementChild !== node) this.canvas.prepend(node);
      }
      after = node;
    }
    if (focused && focused !== document.activeElement && focused.isConnected) focused.focus({ preventScroll: true });
  }

  /** A window leaves: fade it out, and if focus was in it, hand focus to the next window's tools (or the
   *  view heading) first, so a keyboard user is never dropped on the page body. */
  leave(node, staying) {
    if (node.contains(document.activeElement)) {
      const nodes = staying.map((w) => this.windows.get(w.id)).filter(Boolean);
      const after = nodes.find((n) => node.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING) || nodes.at(-1);
      (after?.firstTool || this.host.querySelector("h1")).focus();
    }
    node.inert = true;
    const rail = document.getElementById("rail")?.getBoundingClientRect(), r = node.getBoundingClientRect();
    if (!still() && rail?.width && r.width && node.animate) {
      // it fades and settles away (serious mode: no flight into the icon row)
      const cs = getComputedStyle(node), ms = parseFloat(cs.getPropertyValue("--t-close")) || 160;
      node.style.pointerEvents = "none";
      node.animate([{ transform: "none", opacity: 1 }, { transform: "translateY(4px) scale(0.99)", opacity: 0 }],
        { duration: ms, easing: cs.getPropertyValue("--ease-in").trim() || "ease-in", fill: "forwards" });
      setTimeout(() => node.remove(), ms + 20);
      return;
    }
    node.setAttribute("leaving", "");
    setTimeout(() => node.remove(), still() ? 0 : 200);
  }

  rects() {
    if (still() || this.resized) return null;  // nothing glides under reduced motion or while the window is resized
    return new Map([...this.canvas.children].filter((n) => n.tagName === "JV-WINDOW" && !n.hasAttribute("leaving")).map((n) => [n, n.getBoundingClientRect()]));
  }

  /** Windows that moved slide from where they were, one after another (300 ms at most in all), instead of
   *  all jumping at once when the window Jarvis means takes the first spot. */
  glide(before) {
    if (!before) return;
    const root = getComputedStyle(document.documentElement);
    const duration = parseFloat(root.getPropertyValue("--t-move")) || 200, easing = root.getPropertyValue("--ease").trim() || "ease";
    let i = 0;
    for (const [node, was] of before) {
      if (!node.isConnected || node.hasAttribute("leaving")) continue;
      const r = node.getBoundingClientRect(), dx = was.left - r.left, dy = was.top - r.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
      node.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], { duration, delay: Math.min(i++ * 25, 100), easing, fill: "backwards" });
    }
  }

  /** The window Jarvis means: a brighter frame and a reticle in its kicker, the rest sit back. One at a time. */
  markActive() {
    for (const [id, node] of this.windows) node.toggleAttribute("active", id === this.activeId);
  }

  /** Each window's glance state (brackets only for the ≤ 4 that want him), its "since you looked" notch and
   *  the voice's focus cue: all as attributes; <jv-window> draws them. */
  markThings(wins, s) {
    const marks = s.marks || {}, now = store.now();
    const focus = s.focus?.ref && (!s.focus.until || asDate(s.focus.until) > now) ? s.focus.ref : null;
    const states = new Map(wins.map((w) => [w.id, stateOf(w, s)]));
    const wants = new Set([...states].filter(([, st]) => WANTS[st]).sort((a, b) => WANTS[b[1]] - WANTS[a[1]]).slice(0, MAX_WANTS).map(([id]) => id));
    for (const win of wins) {
      const node = this.windows.get(win.id);
      if (!node) continue;
      const state = states.get(win.id);
      // a fifth thing that wants him shows no mark here: it only raises its Rail slot's count (HUD v2 §5)
      setAttr(node, "glance", state && (!WANTS[state] || wants.has(win.id)) ? state : null);
      const mark = marks[markOf(win, marks)];
      setAttr(node, "marked", mark ? mark.what : null);
      node.toggleAttribute("named", !!focus && (focus === win.id || focus === win.ref));
    }
    clearTimeout(this.focusTimer);  // let go when `until` passes
    if (focus && s.focus.until && s.mode !== "scene") this.focusTimer = setTimeout(() => this.redraw(), Math.max(0, asDate(s.focus.until) - now) + 10);
  }
}

/** The dock beat (HUD v2 §4): the big orb on `layer` pulls its outer layers in and slides to the shell's dock
 *  (the orb does it: `docked`) over the canvas, while the windows assemble behind it; the corner orb shows when
 *  it lands (`jv-orb-docked`). Nothing waits for it. `box` is where the layer stood (so the orb starts exactly
 *  where it was); `host` gets `cls` while it slides. Reduced motion, the phone and a hidden page swap at once.
 *  `onDone` is called once it has landed (or was ended).
 *  → a function that ends it (also called by itself when the orb lands, or after 1.2 s at most). */
export function slideOrbToDock({ layer, host, cls, box, onDone, windows }) {
  const orb = layer?.querySelector("jv-orb"), root = document.documentElement;
  if (!orb || still() || document.hidden || ["phone", "strip"].includes(root.dataset.size)) return null;
  if (box?.width) for (const [k, v] of [["x", box.left], ["y", box.top], ["w", box.width], ["h", box.height]]) layer.style.setProperty(`--dock-${k}`, `${v}px`);
  host.classList.add(cls);
  root.setAttribute("data-orb-docking", "");
  let timer = 0;
  const done = () => {
    clearTimeout(timer);
    orb.removeEventListener("jv-orb-docked", done);
    // the corner orb takes over exactly where these rings are (v0.6.3): without this they jumped to their own
    // angles at the hand-off ("the rings skip a beat")
    handOffSpin(orb, document.getElementById("orb"));
    host.classList.remove(cls);
    root.removeAttribute("data-orb-docking");
    orb.removeAttribute("docked");  // back in the centre for the next time the screen rests
    onDone?.();
  };
  orb.addEventListener("jv-orb-docked", done, { once: true });
  timer = setTimeout(done, 1200);  // never left half way if the event doesn't come
  const core = orb.getBoundingClientRect();
  orb.setAttribute("docked", "");
  if (windows) emerge(windows, core);
  return done;
}

/** Copy where every ring of one orb is in its turn onto the same ring of another (same layer, same spinner), as a
 *  fraction of the turn, so a hand-off between two orbs shows no jump. Runs again on the next frame, in case the
 *  receiving orb only starts its animations once it is shown. */
export function handOffSpin(from, to) {
  if (!from || !to || from === to) return;
  const copy = () => {
    for (const layer of from.querySelectorAll(".jv-orb__L")) {
      const name = [...layer.classList].find((c) => c.startsWith("jv-orb__L--"));
      const other = name && to.querySelector(`.${name}`);
      if (!other) continue;
      for (const sel of [".jv-orb__spin", ".jv-orb__field"]) {
        const a = layer.querySelector(sel)?.getAnimations?.()[0], b = other.querySelector(sel)?.getAnimations?.()[0];
        if (!a || !b) continue;
        const da = a.effect?.getTiming().duration, db = b.effect?.getTiming().duration;
        if (!(da > 0) || !(db > 0) || a.currentTime == null) continue;
        b.currentTime = ((a.currentTime % da) / da) * db;
      }
    }
  };
  copy(); requestAnimationFrame(copy);
  to.takeSpin?.(from);  // the JS-driven rings (orb.js): same angle and speed
}

// The windows arrive as the orb leaves the centre (v0.6.0, serious mode): they fade in and settle a few pixels
// into place, all together, while the orb moves. No flights from the orb and no stagger (research: staggers and
// arcs read as playful; short standard easing reads as functional). Only transform and opacity.
const EMERGE_AFTER = 80;  // ms: as the orb starts to move
export function emerge(canvasEl, orbBox) {
  if (still()) return;
  const cs = getComputedStyle(document.documentElement);
  const ms = parseFloat(cs.getPropertyValue("--t-open")) || 240, easing = cs.getPropertyValue("--ease-out").trim() || "ease-out";
  for (const w of canvasEl.querySelectorAll("jv-window[window-id]:not([docked])")) {
    if (!w.animate) continue;
    w.animate([{ transform: "translateY(6px) scale(0.985)", opacity: 0 }, { transform: "none", opacity: 1 }],
      { duration: ms, delay: EMERGE_AFTER, easing, fill: "backwards" });
  }
}

/** Set or remove an attribute, touching the element only when it changes. */
export function setAttr(node, name, value) {
  if (value == null || value === "") { if (node.hasAttribute(name)) node.removeAttribute(name); }
  else if (node.getAttribute(name) !== String(value)) node.setAttribute(name, String(value));
}

/** The ref whose "since you looked" mark a window shows: its thing's, or its own id's. */
function markOf(win, marks = {}) {
  if (!win) return null;
  return win.ref && marks[win.ref] ? win.ref : marks[win.id] ? win.id : null;
}

/** The glance state of a window's thing: a pending approval waits for his yes; otherwise what the Rail (the
 *  server's word for the thing) says, if anything. */
function stateOf(win, s) {
  if (win.type === "approval" && s.approvals.some((a) => a.id === win.ref && a.status === "pending")) return "yes";
  const ref = win.ref || win.id;
  for (const slot of Object.values(s.rail?.slots || {})) {
    const item = (slot.items || []).find((i) => i.ref === ref);
    if (item) return GLANCES.has(item.state) ? item.state : null;
  }
  return null;
}

/** Sections of the Now card that a window on the canvas already shows, so the card doesn't repeat them. */
function shownElsewhere(wins, s) {
  const hide = [];
  const flagBranch = s.now_card?.flag?.branch_id;
  const flagDue = new Set((s.cards[flagBranch]?.due || []).slice(0, 1).map((d) => d.id));
  if (wins.some((w) => w.type === "next_up")) hide.push("next");
  if (flagBranch && wins.some((w) => (w.type === "countdown" && flagDue.has(w.ref)) || (w.type === "branch_card" && w.ref === flagBranch))) hide.push("flag");
  return hide;
}

/** What a window's content depends on, so it is rebuilt only when that changes. */
function dataStamp(win, s) {
  switch (win.type) {
    case "approval": return s.approvals.find((a) => a.id === win.ref)?.status;
    case "fact": case "unsorted": return JSON.stringify(s.facts.find((f) => f.id === win.ref) || null);
    case "branch_card": return JSON.stringify(s.cards[win.ref] || null).length + ":" + s.facts.length;
    case "next_up": return JSON.stringify(s.now_card?.next_up || null);
    default: return "";
  }
}
function place(node, spot, size) {
  node.style.gridColumn = spot ? `${spot.col} / span ${spot.w}` : "";
  node.style.gridRow = spot ? `${spot.row} / span ${spot.h}` : "";
  if (size) node.dataset.size = size;
}
