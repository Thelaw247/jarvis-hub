// <jv-window heading="PPS 7" status="Due" index="01 / 03" meta="Syllabus p.3" glance="soon" working="0.6"
//            window-id="w-1" active pinned named>…content…</jv-window>
// A HUD window as a slab of glass (HUD v2 §3, v3 §14 decision 3): square corners, a see-through dark fill
// (--glass; --glass-strong under text), a bright thin edge and two ghost edges stacked behind it, down-right. A
// small blue mono kicker inside top-left with the status word last ("PPS 7 // DUE"), a timer, index or type
// top-right, metadata hanging just outside the frame, and content that leads with one big thing. Pin and close
// appear only on hover or keyboard focus (where there is a mouse; always on the phone). Emits
// jv-act { action: "pin" | "unpin" | "close", target: window-id } (close docks the thing into its Rail slot:
// contracts v2; the window manager decides, not this element).
//   active   the window Jarvis means: a brighter frame and (clean) the title plate (one at a time). CSS only,
//            so making a window active on pointerdown never rebuilds the header under his pointer.
//            Its siblings (other windows in the same container) sit back: 0.98 scale, dim frame, 88% opacity in Night.
//   dim      sit back even when no sibling is active
//   glance   its thing's glance code. Only soon, your yes and critical ("wants you") are drawn: a small mark
//            leading the kicker (the one amber or red thing on the window) and corner brackets in the frame's
//            own colour; critical brackets move ±2 px for 5 s, then hold still. Other states are words for
//            screen readers only (no icon glyphs in the kicker, HUD v2 §14.2)
//   clean    the one anatomy (§14.2; the canvas sets it): a kicker row, one hero, at most one line, one footer
//            item. A `.jv-more` block in the content is the "Why?" drawer: sources, details and controls, real
//            and always in the Tab order, drawn under the window only on hover or keyboard focus
//   named    Jarvis is naming this window as he speaks (ui.focus): brackets snap on (250 ms) and the frame brightens
//   marked   "since you looked": a static cyan notch on the top edge; its value is what changed, read to
//            screen readers ("New since you looked: Due moved Wed 8 pm → Thu 11:59 pm"). Never a badge count.
//   working  Jarvis is working on it: a segmented scan bar (~30 blocks, 2 elements); a value 0…1 fills the
//            blocks, empty means "can't tell". Reduced motion: the words "Working · 60%" instead.
//   docked   folded into its Rail slot: never drawn (contracts v2 keep docked windows off state.windows)
//   opens    the panel itself is its "Open it" (the Stage: no buttons on the cards). The content's own open
//            control ([data-key="open"]) stays a real, labelled button for the keyboard and screen readers but is
//            not drawn; a click anywhere on the panel that isn't another control presses it, and keyboard focus
//            on it rings the whole panel.
//   media    the content is a picture or a chart: it fills the panel edge to edge under the kicker (light glass)
//   sheer    a light panel (one big number): the lighter --glass fill; everything else gets --glass-strong
//   sizable  he can size it by hand (the canvas sets it on a board): a small grip in the bottom-right corner, a
//            real button (arrows size the window, Shift+arrows move it, Home lets it go; the canvas does the work)
//   pop      "out": a third tool, "its own window" (emits jv-act popout); "in": "back to the hub" (popin)
//   held, dragging, sizing, leaving-screen   set by the canvas while he has placed, is moving or is sizing it
// Pushed windows (with a window-id) assemble mechanically when they first appear (≤ 300 ms: brackets snap,
// the frame draws, the kicker resolves, a brief lock). The content is usable from 0 ms; the animation is an
// overlay only. assemble({ from }) replays it, growing out of a rect (a recalled window leaving its Rail slot).
import { css, html, icon } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { glance, GLANCE, WANTS_YOU } from "../glance/glance.js";

css(import.meta.url);

const ASSEMBLE_MS = 300;
// what a click on an `opens` panel leaves alone: its own controls and anything else he can work
const CONTROLS = "button, a[href], input, select, textarea, summary, label, details, [data-act], [data-nav], [role=button], [role=link], [contenteditable], jv-source-chip";
const still = () => document.documentElement.hasAttribute("data-still");

class Window extends HTMLElement {
  // `active` is not observed: the brighter frame and the title plate are pure CSS (see the note above).
  static observedAttributes = ["heading", "pinned", "window-id", "status", "index", "meta", "glance", "working", "marked", "pop", "sizable"];

  connectedCallback() {
    if (this._built) return;
    this._built = true;
    this.classList.add("jv-frame");
    const body = el("div", { className: "jv-window__body" });
    body.append(...this.childNodes);
    this.head = el("header", { className: "jv-window__head" });
    this.titleEl = el("h2", { className: "jv-window__title" });
    this.indexEl = el("span", { className: "jv-window__index jv-kicker" });
    this.pinnedEl = el("span", { className: "jv-window__pinned jv-sr", textContent: "Pinned" });
    this.tools = el("span", { className: "jv-window__tools" });
    this.head.append(this.titleEl, this.indexEl, this.pinnedEl, this.tools);
    const ghosts = [1, 2].map((n) => el("span", { className: `jv-window__ghost jv-window__ghost--${n}` }, { "aria-hidden": "true" }));
    this.append(this.head, body, ...ghosts, ...[1, 2, 3, 4].map((n) => el("span", { className: `jv-window__bracket jv-window__bracket--${n}` }, { "aria-hidden": "true" })));
    this.body = body;
    this.setAttribute("role", "group");
    this.addEventListener("click", (e) => {
      const btn = e.target.closest(".jv-window__tool");
      if (btn && this.head.contains(btn)) {
        e.stopPropagation();
        this.dispatchEvent(new CustomEvent("jv-act", { bubbles: true, detail: { action: btn.dataset.tool, target: this.getAttribute("window-id") || "" } }));
        return;
      }
      // the panel is its own "Open it": a click on it that isn't on another control (or a text selection) presses it
      if (!this.hasAttribute("opens") || e.defaultPrevented || e.button > 0 || e.target.closest(".jv-window__grip")) return;
      if (e.target.closest(CONTROLS) || String(getSelection?.() || "")) return;
      this.opener?.click();
    });
    // the "Why?" drawer (a resting window's sources and details) opens under the window, or over it when there
    // is no room below
    const aim = () => {
      const more = this.body.querySelector(".jv-more");
      if (!more) return;
      // the room is the view itself: never over the bottom band (caption, icon row) or under the top edge, so the
      // drawer can't run into the menu below (v0.5.3); it opens toward the side with more room and scrolls inside
      const r = this.getBoundingClientRect(), need = Math.min(more.scrollHeight + 24, 420);
      const view = (this.closest("main") || document.body).getBoundingClientRect();
      const band = [document.getElementById("foot"), document.getElementById("caption")].map((el) => el?.getBoundingClientRect()).filter((b) => b?.height);
      const bottom = Math.min(view.bottom, innerHeight, ...band.map((b) => b.top)) - 8;
      const below = bottom - r.bottom, above = r.top - view.top - 8, up = need > below && above > below;
      this.toggleAttribute("why-up", up);
      this.style.setProperty("--why-max", `${Math.max(96, Math.min(420, Math.floor(up ? above : below)))}px`);
    };
    this.addEventListener("pointerenter", aim);
    this.addEventListener("focusin", aim);
    this.draw();
    if (this.hasAttribute("window-id") && !this.hasAttribute("docked")) this.assemble();
  }

  attributeChangedCallback(_name, before, after) { if (this._built && before !== after) this.draw(); }

  /** Replace the content (used by the window manager when data changes). */
  setContent(...nodes) { this.body.replaceChildren(...nodes); }

  /** The first pin or close button, for moving focus here (null when the window has no tools). */
  get firstTool() { return this.tools?.querySelector('button:not([data-tool^="pop"])') || this.tools?.querySelector("button") || null; }  // pin, as before the own-window button

  /** The content's own "Open it" (a button or link with data-key="open"), or null. */
  get opener() { return this.body?.querySelector('[data-key="open"]:not(:disabled)') || null; }

  /** Play the mechanical assembly (≤ 300 ms) over the window. `from`: a DOMRect to grow out of (its Rail slot).
   *  Nothing waits for it: the content is there and usable the whole time. Skipped when nothing may move. */
  assemble({ from } = {}) {
    if (still() || !this.isConnected) return;
    clearTimeout(this._assembling);
    this.querySelectorAll(":scope > .jv-window__draw").forEach((n) => n.remove());
    this.titleEl.querySelector(".jv-window__cover")?.remove();
    this.append(el("span", { className: "jv-window__draw" }, { "aria-hidden": "true" }));
    this.titleEl.append(el("span", { className: "jv-window__cover" }, { "aria-hidden": "true" }));
    this.removeAttribute("assembling");
    void this.offsetWidth;  // restart the keyframes if it was already assembling
    this.setAttribute("assembling", "");
    if (from && this.animate) {
      const to = this.getBoundingClientRect();
      if (to.width && to.height) {
        const dx = from.left + from.width / 2 - (to.left + to.width / 2), dy = from.top + from.height / 2 - (to.top + to.height / 2);
        // serious mode (v0.6.0): a recalled window fades in and settles, nudged a little from its slot's side
        const cs = getComputedStyle(this), easing = cs.getPropertyValue("--ease-out").trim() || "ease-out", ms = parseFloat(cs.getPropertyValue("--t-open")) || 240;
        const nx = Math.max(-12, Math.min(12, dx * 0.04)), ny = Math.max(-12, Math.min(12, dy * 0.04));
        this.animate([{ transform: `translate(${nx.toFixed(1)}px, ${ny.toFixed(1)}px) scale(0.985)`, opacity: 0 }, { transform: "none", opacity: 1 }],
          { duration: ms, easing });
      }
    }
    this._assembling = setTimeout(() => this.settle(), ASSEMBLE_MS + 20);
  }

  /** End the assembly at once (also what happens after 300 ms). */
  settle() {
    clearTimeout(this._assembling);
    if (this.hasAttribute("assembling-hold")) return;  // scenes freeze it mid-way for screenshots
    this.removeAttribute("assembling");
    this.querySelectorAll(":scope > .jv-window__draw").forEach((n) => n.remove());
    this.titleEl?.querySelector(".jv-window__cover")?.remove();
  }

  /** Update the header in place: the buttons are made once and only their words change, so focus and a
   *  click that is already under way are never lost. */
  draw() {
    const heading = this.getAttribute("heading") || "Window";
    const status = this.getAttribute("status") || "";
    const state = this.getAttribute("glance");
    const pinned = this.hasAttribute("pinned");
    this.setAttribute("aria-label", heading);
    // the kicker: ≤ 4 words in mono caps, status word last; anything longer reads as a sentence-case title
    const long = heading.trim().split(/\s+/).length > 4;
    const sig = JSON.stringify([heading, status, state, long]);
    if (this.titleEl.dataset.sig !== sig) {
      this.titleEl.dataset.sig = sig;
      const cover = this.titleEl.querySelector(".jv-window__cover");
      // no icon glyphs in the kicker (§14.2): only a "wants you" mark (diamond, square, triangle) may lead it,
      // the one amber or red thing on the window; any other state is its word, for screen readers
      const wants = WANTS_YOU.has(state), word = GLANCE[state] ? status || GLANCE[state].word : "";
      this.titleEl.innerHTML = String(html`${wants ? html`<span class="jv-window__glance" aria-hidden="${!!status}">${glance(state, { size: "rail", bare: true, word })}</span>` : word && !status ? html`<span class="jv-sr">${word}</span>` : ""}<span class="jv-window__name">${heading}</span>${status ? html`<span class="jv-window__sep" aria-hidden="true"> // </span><span class="jv-window__status">${status}</span>` : ""}`);
      if (cover) this.titleEl.append(cover);
    }
    this.titleEl.classList.toggle("jv-window__title--long", long);
    this.toggleAttribute("data-wants", WANTS_YOU.has(state));
    const index = this.getAttribute("index") || "";
    this.indexEl.textContent = index;
    this.indexEl.hidden = !index;
    this.pinnedEl.hidden = !pinned;
    this.drawMeta();
    this.drawWorking();
    this.drawMark();
    if (!this.hasAttribute("window-id")) { this.tools.replaceChildren(); return; }
    if (!this.tools.firstChild) {
      this.tools.innerHTML = String(html`
        <button type="button" class="jv-window__tool" data-tool="pin">${icon("pin")}<span class="jv-sr"></span></button>
        <button type="button" class="jv-window__tool" data-tool="close">${icon("close")}<span class="jv-sr"></span></button>`);
    }
    const [pin, close] = this.tools.querySelectorAll('button:not([data-tool^="pop"])');
    this.drawPop(heading);
    this.drawGrip(heading);
    pin.dataset.tool = pinned ? "unpin" : "pin";
    pin.setAttribute("aria-pressed", String(pinned));
    pin.title = pinned ? "Pinned. It stays until you close it" : "Keep this up";
    pin.querySelector(".jv-sr").textContent = `${pinned ? "Unpin" : "Pin"} ${heading}`;
    close.querySelector(".jv-sr").textContent = `Close ${heading}`;
    close.title = `Close ${heading} (it waits on the Rail)`;
  }

  /** The third tool, where this screen has another to send the window to: out to its own window, or back. */
  drawPop(heading) {
    const way = this.getAttribute("pop");
    let btn = this.tools.querySelector('button[data-tool^="pop"]');
    if (way !== "out" && way !== "in") { btn?.remove(); return; }
    if (!btn) {
      btn = el("button", { type: "button", className: "jv-window__tool" });
      btn.innerHTML = String(html`${icon("expand")}<span class="jv-sr"></span>`);
      this.tools.prepend(btn);
    }
    btn.dataset.tool = way === "out" ? "popout" : "popin";
    btn.title = way === "out" ? "Move to its own window (or drag it off the edge)" : "Move back to the hub";
    btn.querySelector(".jv-sr").textContent = way === "out" ? `Move ${heading} to its own window` : `Move ${heading} back to the hub`;
  }

  /** The corner grip, where he can size windows by hand. Last in the window, so it is the last Tab stop in it. */
  drawGrip(heading) {
    let grip = this.querySelector(":scope > .jv-window__grip");
    if (!this.hasAttribute("sizable")) { grip?.remove(); return; }
    if (!grip) {
      grip = el("button", { type: "button", className: "jv-window__grip" }, { "aria-keyshortcuts": "ArrowLeft ArrowRight ArrowUp ArrowDown Shift+ArrowLeft Shift+ArrowRight Shift+ArrowUp Shift+ArrowDown Home" });
      grip.title = "Drag to size. Arrows size it, Shift+arrows move it, Home puts it back";
      this.append(grip);
    }
    grip.setAttribute("aria-label", `Size or move ${heading}: arrows size it, Shift and arrows move it, Home puts it back`);
  }

  /** Metadata hanging just outside the frame (never the only copy of a fact). */
  drawMeta() {
    const meta = this.getAttribute("meta") || (this.hasAttribute("pinned") ? "Pinned" : "");  // one footer item
    let node = this.querySelector(":scope > .jv-window__meta");
    if (!meta) { node?.remove(); return; }
    if (!node) { node = el("p", { className: "jv-meta jv-window__meta" }); this.append(node); }
    node.textContent = meta;
  }

  /** "Since you looked": the notch on the top edge, with what changed for screen readers. */
  drawMark() {
    let node = this.querySelector(":scope > .jv-window__notch");
    if (!this.hasAttribute("marked")) { node?.remove(); return; }
    if (!node) {
      node = el("span", { className: "jv-window__notch" });
      node.innerHTML = '<span class="jv-window__notchmark" aria-hidden="true"></span><span class="jv-sr"></span>';
      this.append(node);
    }
    const what = this.getAttribute("marked");
    node.lastElementChild.textContent = what ? `New since you looked: ${what}` : "New since you looked";
  }

  /** The working scan bar: a masked track of ~30 blocks (lit up to the progress) and one sweeping chunk. */
  drawWorking() {
    const on = this.hasAttribute("working");
    let bar = this.querySelector(":scope > .jv-window__working");
    if (!on) { bar?.remove(); return; }
    const raw = this.getAttribute("working");
    const value = raw === "" || raw == null || Number.isNaN(Number(raw)) ? null : Math.max(0, Math.min(1, Number(raw)));
    const pct = value == null ? null : Math.round(value * 100);
    const words = pct == null ? "Working" : `Working · ${pct}%`;
    if (!bar) {
      bar = el("div", { className: "jv-window__working" });
      bar.innerHTML = '<span class="jv-window__scan" role="progressbar" aria-valuemin="0" aria-valuemax="100"><span class="jv-window__chunk"></span></span><span class="jv-window__scan-words jv-kicker"></span>';
      this.head.after(bar);
    }
    const scan = bar.firstElementChild;
    scan.style.setProperty("--p", `${pct ?? 0}%`);
    scan.setAttribute("aria-label", `${this.getAttribute("heading") || "Window"}: Jarvis is working`);
    scan.setAttribute("aria-valuetext", words);
    if (pct == null) scan.removeAttribute("aria-valuenow"); else scan.setAttribute("aria-valuenow", String(pct));
    bar.lastElementChild.textContent = words;
  }
}
if (!customElements.get("jv-window")) customElements.define("jv-window", Window);

// ---- scenes ------------------------------------------------------------------------------------------------
const sample = (attrs, content) => {
  const w = el("jv-window", {}, attrs);
  if (typeof content === "function") w.append(content()); else w.append(el("p", { textContent: content ?? "PPS 7 is due Wednesday at 8 pm." }));
  return w;
};
const big = (value, unit, sub) => () => el("jv-big-number", {}, { label: "", value, unit, sub });
const due = (title, when) => () => el("jv-big-number", { due: { id: "d", title, due: when }, now: "2026-11-16T15:40:00" });
const pair = (a, b) => {
  const box = el("div", { className: "jv-window-demo" });
  box.append(a, b);
  return box;
};
registerGallery("window", [
  { label: "Resting", build: () => sample({ heading: "Due", "window-id": "w-1" }) },
  { label: "Active (Jarvis means it)", build: () => sample({ heading: "Next", "window-id": "w-2", active: true, index: "01 / 03" }, big("4:00", "pm", "Review GE 122 lecture 21")) },
  { label: "Pinned", build: () => sample({ heading: "GE 122", "window-id": "w-3", pinned: true }) },
  { label: "Kicker, index and metadata", build: () => sample({ heading: "MATH 133", status: "Exam", index: "EXAM", meta: "Syllabus p.3 · Canvas", "window-id": "w-4" }, big("6", "days", "MATH 133 midterm · Sunday 9 am")) },
  { label: "Wants you: soon", build: () => sample({ heading: "PPS 7", status: "Soon", glance: "soon", "window-id": "w-5" }, due("PPS 7", "2026-11-18T20:00:00")) },
  { label: "Wants you: your yes", build: () => sample({ heading: "Week plan", status: "Your yes", glance: "yes", "window-id": "w-6" }, "Four study blocks on Friday. Go ahead?") },
  { label: "Wants you: critical", build: () => sample({ heading: "Lab 4", status: "Now", glance: "critical", "window-id": "w-7" }, big("40", "min", "Report due at 5 pm")) },
  { label: "Working (60%)", build: () => sample({ heading: "Canvas", status: "Syncing", working: "0.6", glance: "jarvis", "window-id": "w-8", index: "00:04" }, "Checking six courses for new files.") },
  { label: "Working (can't tell)", build: () => sample({ heading: "Study pack", status: "Building", working: "", "window-id": "w-9" }, "Lecture 21 · notes and flashcards") },
  { label: "New since you looked", build: () => sample({ heading: "PPS 7", status: "Due", marked: "Due moved Wed 8 pm → Thu 11:59 pm", "window-id": "w-15" }, due("PPS 7", "2026-11-19T23:59:00")) },
  { label: "Named as Jarvis speaks", build: () => sample({ heading: "GE 122", status: "Next", named: true, active: true, "window-id": "w-10" }, big("4:00", "pm", "ENGR 1A10")) },
  { label: "Focused and unfocused", wide: true, build: () => pair(
    sample({ heading: "PPS 7", status: "Q7 of 12", glance: "progress", active: true, "window-id": "w-11" }, big("Q7", "of 12", "Practice set · page 3")),
    sample({ heading: "Lab 4", status: "Draft", "window-id": "w-12" }, "Results section, last edited yesterday.")) },
  { label: "Assembling (frozen at 150 ms)", build: () => {
    const w = sample({ heading: "PPS 7", status: "Due", "window-id": "w-13", "assembling-hold": true, style: "--jv-asm-at: -150ms" }, due("PPS 7", "2026-11-18T20:00:00"));
    return w;
  } },
  { label: "Docked (not drawn)", build: () => {
    const box = el("div", { className: "jv-window-demo jv-window-demo--note" });
    box.append(sample({ heading: "Due", "window-id": "w-14", docked: true }), el("p", { className: "jv-muted", textContent: "A docked window waits in its Rail slot; nothing of it is drawn here." }));
    return box;
  } },
  { label: "No tools (inside a page)", build: () => sample({ heading: "Status" }, "Week 11 of 13 · on track") },
  // HUD v3 on the Stage's board (the collage sets these): see-through glass, no buttons drawn
  { label: "Board: media edge to edge", build: (s) => {
    const file = s.files.find((f) => f.id === "file-pps7");
    return sample({ heading: "PPS 7", status: "Q7", index: "P. 3 / 5", meta: "Added 3:40 pm", "window-id": "w-16", media: true, opens: true },
      () => el("jv-file-tile", { file: { ...file, page: "Page 3 of 5", thumb: { src: "/api/thumb/file-pps7-p3.webp", kind: "page", alt: "PPS 7, page 3: question 7, a truss" } } }));
  } },
  { label: "Board: a big number (sheer glass)", build: () => sample({ heading: "PPS 7", status: "Due", glance: "soon", "window-id": "w-17", sheer: true, opens: true }, due("PPS 7", "2026-11-18T20:00:00")) },
  { label: "Board: the one Jarvis means (title plate)", build: (s) => {
    const branch = s.branches.find((b) => b.id === "ge-122");
    return sample({ heading: "GE 122", "window-id": "w-18", active: true, opens: true, meta: "Added 3:41 pm" }, () => el("jv-branch-card", { card: s.cards["ge-122"], branch, facts: s.facts, now: s.now }));
  } },
  { label: "Board: pin and close on hover or focus", build: () => {
    const w = sample({ heading: "Lab 4", status: "Draft", "window-id": "w-19", opens: true }, "Results section, last edited yesterday.");
    w.setAttribute("data-show-tools", "");
    return w;
  } },
], { about: "A slab of glass: a see-through dark fill, a bright edge and two ghost edges behind it. Brackets mean only “wants you”; the window Jarvis means has the bright edge, a reticle and (on the Stage) a title plate; the rest sit back. On the Stage pin and close show on hover or focus, and the panel itself opens its thing. Close never loses anything.", columns: "340px" });
