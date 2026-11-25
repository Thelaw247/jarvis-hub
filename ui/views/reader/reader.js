// The reader (N6): a work thread's PDF inside the hub, on the light reading sheet (HUD v2 §10.1).
// Route: /read/<thread id>. Opens straight away at the resume point (page + y) behind <jv-resume-card>;
// a fresh PDF (no resume point) opens at the top with no card. While he reads it tracks the page, the
// scroll and the time on each question (PDF.js `pagechanging` / `updateviewarea`), and when he leaves it
// saves the spot silently (action resume_save, with the session for jarvis_hub/threads.py). Nothing is said.
//
// Files come from GET /api/file/<thread.ref> (HTTP Range, so Laptop A can stream from B); the question index
// from GET /api/file/<thread.ref>.qindex.json (built when the file was filed). PDF.js 6.5 is vendored in
// ui/vendor/pdfjs and runs fully offline. One worker and the last two documents stay alive between opens,
// so a warm reopen does no added work. The reader's canvas is the one canvas on the HUD (§7): never on the
// ambient screen or the strip.
import { css, html, Jv } from "../../core/dom.js";
import { bridge } from "../../core/bridge.js";
import { router } from "../../core/router.js";
import { registerScene, sceneName } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import "../../components/resume-card/resume-card.js";

css(import.meta.url);

const VENDOR = new URL("../../vendor/pdfjs/", import.meta.url);
const MAX_SCALE = 1.4;  // page width, but never bigger than this (a 2-page-wide practice set on a big screen)
const TOP_ROOM = 28;  // px above the heading when nothing covers it
const READ_LINE = 0.33;  // the page he's on: the one a third of the way down the sheet
const READ_SPAN = 0.6;  // a question heading in the top 60% of the sheet is the one he's on
const HEAD_SLACK = 48;  // px: a heading this close under the spot the reader put it is "at the top"
const RECENT_MS = 5 * 60 * 1000;  // back within minutes, or already answered this open: no card, just the spot
const TICK_MS = 1000;
const IDLE_MS = 10 * 60 * 1000;  // no input this long: he's away, the clock on the question stops
const LOCK_HOLD_MS = 900;  // brackets hold on the heading, then fade
// Mirrors jarvis_hub/threads.py (the server decides; this is the label sent with the session).
const CLEAR_DWELL_S = 60, SHORT_SESSION_S = 180, GLANCE_S = 15;

// ---- PDF.js: loaded once, one worker, the last two documents kept open -------------------------------------
let lib = null;
const docs = new Map();  // file id -> Promise<PDFDocumentProxy>
const indexes = new Map();  // file id -> Promise<index | null>

export function loadPdfjs() {
  lib ||= (async () => {
    const pdfjs = await import(new URL("pdf.min.mjs", VENDOR).href);
    globalThis.pdfjsLib = pdfjs;  // the viewer module reads the library from here
    pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdf.worker.min.mjs", VENDOR).href;
    const viewer = await import(new URL("web/pdf_viewer.mjs", VENDOR).href);
    if (!document.querySelector("link[data-pdfjs]")) {
      const link = Object.assign(document.createElement("link"), { rel: "stylesheet", href: new URL("web/pdf_viewer.css", VENDOR).href });
      link.dataset.pdfjs = "";
      document.head.prepend(link);  // first, so the reader's own rules win
    }
    return { pdfjs, viewer, worker: new pdfjs.PDFWorker({ name: "jarvis-reader" }) };
  })();
  return lib;
}

function openDoc(fileId) {
  if (!docs.has(fileId)) {
    docs.set(fileId, loadPdfjs().then(({ pdfjs, worker }) => pdfjs.getDocument({
      url: `/api/file/${encodeURIComponent(fileId)}`, worker,
      cMapUrl: new URL("cmaps/", VENDOR).href, cMapPacked: true,
      standardFontDataUrl: new URL("standard_fonts/", VENDOR).href,
      wasmUrl: new URL("wasm/", VENDOR).href, iccUrl: new URL("iccs/", VENDOR).href,
      isEvalSupported: false, enableXfa: false,
    }).promise).catch((err) => { docs.delete(fileId); throw err; }));
    while (docs.size > 2) {  // keep the last two open; close the oldest
      const [oldest, doc] = docs.entries().next().value;
      docs.delete(oldest);
      doc.then((d) => d.destroy()).catch(() => {});
    }
  } else {  // most recent last
    const doc = docs.get(fileId);
    docs.delete(fileId);
    docs.set(fileId, doc);
  }
  return docs.get(fileId);
}

function loadIndex(fileId) {
  if (!indexes.has(fileId)) {
    indexes.set(fileId, fetch(`/api/file/${encodeURIComponent(fileId)}.qindex.json`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null)).catch(() => null));
  }
  return indexes.get(fileId);
}

/** Warm the reader in idle time after boot, so the first open is already warm (never on the strip or a phone). */
function warmUp() {
  if (sceneName && !sceneName.startsWith("reader")) return;
  const size = document.documentElement.dataset.size;
  if (size === "strip" || size === "phone" || document.documentElement.hasAttribute("data-ambient")) return;
  (window.requestIdleCallback || ((fn) => setTimeout(fn, 1500)))(() => loadPdfjs().catch(() => {}), { timeout: 4000 });
}

// ---- helpers ------------------------------------------------------------------------------------------------
const topLabel = (label) => String(label).replace(/^(Q\d+)[a-h]$/, "$1");
const isWeak = (resume) => !!resume && (resume.y == null || /^Page /.test(resume.label || ""));
const questionAt = (index, page, y) => {
  let best = null;
  for (const q of index?.questions || []) if (q.page < page || (q.page === page && q.y <= y + 1)) best = q;
  return best;
};
const settled = new Map();  // thread id -> when he answered its card or left it (this page load)
const taken = new Map();  // thread id -> when he said yes to Jarvis's offer somewhere else (the home's card)
const TAKEN_MS = 10_000;
/** He accepted the return offer for this thread outside the reader (views/now/offer.js): his yes is already in,
 *  so the reader opens at the spot with no second card and the brackets lock onto the question. */
export function accepted(threadId) { taken.set(threadId, performance.now()); }
const backAndForth = (path, index) => {
  const order = new Map((index?.questions || []).map((q, i) => [q.label, i]));
  const steps = path.filter((l) => order.has(l)).map((l) => order.get(l));
  return steps.some((s, i) => i > 0 && s < steps[i - 1]);
};

class ReaderView extends Jv {
  static props = ["params", "route"];

  setup() {
    this._built = false;
    this._abort = new AbortController();
    // the voice and the screen move together (HUD v2 §9.1, §10.1): when Jarvis names this piece of work and the
    // spot is confirmed (he said yes), the card lifts and the brackets lock onto the question
    this.stopStore = store.subscribe((_s, keys) => { if (keys.has("focus") || keys.has("threads")) this.followVoice(); });
  }

  /** Does state.focus name this thread: its id, its file, or a window showing that file? */
  named() {
    const f = store.state.focus, t = this.thread;
    if (!f?.ref || !t || (f.until && new Date(f.until) <= store.now())) return false;
    return f.ref === t.id || f.ref === t.ref || store.state.windows.some((w) => w.id === f.ref && w.ref === t.ref);
  }

  followVoice() {
    if (!this.thread || !this._viewer) return;
    const now = store.thread(this.thread.id);
    if (!now?.resume || now.resume.source !== "confirmed" || !this.named()) return;
    const key = `${store.state.focus.ref}|${store.state.focus.until}`;
    if (key === this._voiced) return;  // once per cue
    this._voiced = key;
    settled.set(now.id, performance.now());  // his yes answered the card
    this.thread = now;
    if (!isWeak(now.resume)) this.choseHere(now.resume.label);  // his yes covered it: an explicit choice
    if (this._card && !this._card.hasAttribute("lifted")) { this._card.setAttribute("lifted", ""); this.liftCard(); }
    if (!isWeak(now.resume)) this.lock(now.resume.label);
  }

  teardown() {
    this.stopStore?.();
    this.save();
    clearInterval(this._tick);
    clearTimeout(this._lockTimer);
    this._abort.abort();
    this._viewer?.cleanup?.();
  }

  render() {
    if (this._built) return null;  // drawn once; PDF.js owns the sheet after that
    this._built = true;
    this._t0 = performance.now();
    this.thread = store.thread(this.params?.[0] || "");
    const t = this.thread;
    if (!t) return html`<div class="jv-view jv-view--narrow"><jv-notice kind="empty" heading="That piece of work isn't here" text="It may have been archived. Life has everything that's filed." action-label="Open Life" target="/life"></jv-notice></div>`;
    const branch = store.branch(t.branch);
    return html`<div class="jv-reader" data-state="loading">
      <section class="jv-frame jv-reader__frame" aria-labelledby="rd-title">
        <div class="jv-kicker-row jv-reader__bar">
          <span class="jv-kicker" id="rd-where">${t.title} // Opening</span>
          <span class="jv-reader__right">
            <span class="jv-kicker" id="rd-page" aria-hidden="true"></span>
            <button type="button" class="jv-pill" data-key="close" id="rd-close" aria-label="Close ${t.title}. Your place is kept.">Close</button>
          </span>
        </div>
        <h1 class="jv-sr" id="rd-title">${t.title}</h1>
        <div class="jv-paper jv-reader__sheet">
          <div class="jv-reader__scroll" id="rd-scroll" tabindex="0" aria-label="${t.title}"><div class="pdfViewer"></div></div>
          <p class="jv-reader__status" id="rd-status" role="status"></p>
        </div>
        <div class="jv-reader__card" id="rd-card"></div>
        <span class="jv-meta">${branch?.name || t.branch} · PDF</span>
      </section>
    </div>`;
  }

  rendered() {
    if (!this.thread || this._wiredView) return;
    this._wiredView = true;
    this.$("#rd-close").addEventListener("click", (e) => { e.stopPropagation(); this.close(); });
    const resume = this.thread.resume;
    this.session = { started: performance.now(), seconds: 0, dwell: {}, path: [], visible: [], corrected: false, chosen: null, since: [] };
    this._lastInput = performance.now();
    const yes = taken.get(this.thread.id);
    this._taken = !!resume && yes != null && performance.now() - yes < TAKEN_MS;
    taken.delete(this.thread.id);
    if (this._taken) settled.set(this.thread.id, performance.now());
    if (resume && !(sceneName === "reader-accepted") && !this.settledLately(resume)) this.showCard();
    this.open().catch((err) => this.fail(err));
  }

  // ---- opening --------------------------------------------------------------------------------------------
  async open() {
    const t = this.thread, signal = this._abort.signal;
    const [{ viewer: V, pdfjs }, doc, index] = await Promise.all([loadPdfjs(), openDoc(t.ref), loadIndex(t.ref)]);
    if (signal.aborted) return;
    this.index = index;
    if (this._card) this._card.questions = index?.questions || [];
    const container = this.$("#rd-scroll");
    const eventBus = new V.EventBus();
    const linkService = new V.PDFLinkService({ eventBus });
    const viewer = new V.PDFViewer({
      container, eventBus, linkService, removePageBorders: true, abortSignal: signal,
      textLayerMode: 1, annotationMode: pdfjs.AnnotationMode.ENABLE, l10n: new V.GenericL10n(),
    });
    linkService.setViewer(viewer);
    this._viewer = viewer;
    this._bus = eventBus;
    const target = this.target();
    eventBus.on("pagesinit", () => {
      this.fit();
      if (target) this.jumpTo(target.page, target.y, this.cardRoom());
      this._placed = true;  // positions before this were the sheet loading at the top, not him
      this.track();
      this.followVoice();
    }, { signal });
    eventBus.on("pagerendered", ({ pageNumber }) => {
      if (this._landed || pageNumber !== (target?.page || 1)) return;
      this._landed = performance.now() - this._t0;
      this.dataset.landedMs = String(Math.round(this._landed));
      this.$(".jv-reader").dataset.state = "ready";
      if (sceneName === "reader-accepted") this.lock(target?.label || this.thread.resume?.label, { hold: true });
      else if (this._taken && !isWeak(this.thread.resume)) { this.choseHere(this.thread.resume.label); this.lock(this.thread.resume.label); }
    }, { signal });
    eventBus.on("updateviewarea", () => this.track(), { signal });
    // PDF.js makes each text layer a nameless tab stop: Tab goes sheet → Close, not through every page
    eventBus.on("textlayerrendered", ({ pageNumber }) => {
      container.querySelector(`.page[data-page-number="${pageNumber}"] .textLayer`)?.setAttribute("tabindex", "-1");
    }, { signal });
    eventBus.on("pagechanging", () => this.track(), { signal });
    viewer.setDocument(doc);
    linkService.setDocument(doc, null);
    this.listenForHim(container, signal);
    window.addEventListener("pagehide", () => this.save(), { signal });
    this._tick = setInterval(() => this.tickDwell(), TICK_MS);
  }

  /** Where to open: the resume point (the page alone for a weak spot), or nothing for a fresh PDF. */
  target() {
    const r = this.thread.resume;
    if (!r) return null;
    if (isWeak(r)) return { page: r.page || 1, y: 0, label: null };
    // a question the index knows opens at its heading (whatever units the spot was saved in); else the saved y
    const q = (this.index?.questions || []).find((x) => x.label === r.label);
    return { page: q?.page || r.page || 1, y: q?.y ?? r.y ?? 0, label: r.label };
  }

  /** Room above the resume question's heading: below the card while it's up, so the heading shows under it. */
  cardRoom() { return this.covered() + TOP_ROOM; }

  /** How much of the sheet's top the card covers (px), or 0: the card has to lie over the page where a heading
   *  lands (the top band, across the page's width). At the bottom (phone) or beside the page it covers nothing. */
  covered() {
    const card = this._card, sheet = this.$(".jv-reader__sheet");
    if (!card || card.hasAttribute("lifted") || !sheet) return 0;
    const c = card.getBoundingClientRect(), s = sheet.getBoundingClientRect();
    const page = this.$(".pdfViewer .page")?.getBoundingClientRect() || s;
    const left = Math.max(s.left, page.left), right = Math.min(s.right, page.right);
    const overTop = c.height > 0 && c.top < s.top + TOP_ROOM + HEAD_SLACK && c.bottom > s.top;
    return overTop && c.left < right && c.right > left ? Math.round(c.bottom - s.top) : 0;
  }

  fit() {
    const v = this._viewer;
    if (!v) return;
    v.currentScaleValue = "page-width";
    if (v.currentScale > MAX_SCALE) v.currentScale = MAX_SCALE;
  }

  /** Scroll so (page, y) — PDF points from the top of the page — sits `room` px below the sheet's top edge. */
  jumpTo(page, y, room = TOP_ROOM) {
    const v = this._viewer, pv = v?.getPageView(page - 1);
    if (!pv) return;
    const box = pv.viewport.viewBox;
    const [, top] = pv.viewport.convertToViewportPoint(box[0], box[3] - (y || 0));
    const lift = y ? room : 0;  // a page opens at its top edge
    v.container.scrollTop = Math.max(0, pv.div.offsetTop + top - lift);
    this._jumped = performance.now();
    this._room = lift;  // where the heading sits, while the sheet stays where it was put
    this._jumpTop = v.container.scrollTop;
  }

  /** Where the sheet is: the page and y at its top, the question on the reading line, the questions in view.
   *  What's under the card isn't in view. The empty working space above a heading near the top belongs to that
   *  heading's question, not the one before it: only a heading in view puts a question in view, and the question
   *  running through the top edge counts only when no heading sits near the top. */
  where() {
    const v = this._viewer, c = v?.container;
    if (!v || !c || !v.pagesCount) return null;
    const at = (cssY) => {
      for (let i = 0; i < v.pagesCount; i++) {
        const pv = v.getPageView(i), top = pv.div.offsetTop, h = pv.div.offsetHeight;
        if (cssY < top + h || i === v.pagesCount - 1) {
          const box = pv.viewport.viewBox;
          const [, yUser] = pv.viewport.convertToPdfPoint(0, Math.max(0, cssY - top));
          return { page: i + 1, y: Math.max(0, Math.round((box[3] - yUser) * 10) / 10) };
        }
      }
      return { page: 1, y: 0 };
    };
    const h = c.clientHeight, cover = Math.min(this.covered(), h * READ_SPAN);
    const room = Math.abs(c.scrollTop - (this._jumpTop ?? -1e9)) < 2 ? this._room || 0 : 0;  // he hasn't moved it
    const band = Math.max(cover + (h - cover) * READ_LINE, room + HEAD_SLACK);
    const sheetTop = at(c.scrollTop), top = at(c.scrollTop + cover), bottom = at(c.scrollTop + h);
    const upper = at(c.scrollTop + Math.max(h * READ_SPAN, band)), near = at(c.scrollTop + band);
    const qs = this.index?.questions || [];
    const between = (q, a, b) => (q.page > a.page || (q.page === a.page && q.y >= a.y)) && (q.page < b.page || (q.page === b.page && q.y <= b.y));
    const inView = qs.filter((q) => between(q, top, upper));  // headings in the part he reads, not the bottom edge
    const headed = qs.some((q) => !q.part && between(q, top, near));
    const holding = questionAt(this.index, top.page, top.y);
    const visible = [...new Set([...(holding && !headed ? [holding] : []), ...inView].map((q) => topLabel(q.label)))];
    // what he's on: the first question heading in the upper part of the sheet, else the question running
    // through the top edge (the heading has scrolled off)
    const current = qs.find((q) => !q.part && between(q, top, upper)) || holding;
    const page = current && between(current, top, bottom) ? current.page : at(c.scrollTop + cover + (h - cover) * READ_LINE).page;
    return { page, y: page === sheetTop.page ? sheetTop.y : 0, top: sheetTop, current, visible };
  }

  track() {
    if (!this._placed) return;
    const w = this.where();
    if (!w) return;
    this.position = w;
    const s = this.session, label = w.current?.label;
    if (label && s.path[s.path.length - 1] !== label) s.path.push(label);
    if (s.chosen && label && s.since[s.since.length - 1] !== topLabel(label)) s.since.push(topLabel(label));
    s.visible = w.visible;
    const tops = (this.index?.questions || []).filter((q) => !q.part);
    const cur = w.current ? topLabel(w.current.label) : null;
    this.$("#rd-where").textContent = cur && tops.length ? `${this.thread.title} // ${cur} of ${tops.length}` : `${this.thread.title} // Reading`;
    this.$("#rd-page").textContent = `P. ${w.page} / ${this._viewer.pagesCount}`;
    this.$("#rd-scroll").setAttribute("aria-label", `${this.thread.title}, page ${w.page} of ${this._viewer.pagesCount}`);
    this.emit("jv-reader-position", { thread: this.thread.id, page: w.page, y: w.y, label: label || null });
  }

  tickDwell() {
    const now = performance.now();
    const last = this._lastTick || now;
    this._lastTick = now;
    if (document.hidden || now - this._lastInput > IDLE_MS) return;
    const seconds = Math.min(5, (now - last) / 1000);
    this.session.seconds += seconds;
    const label = this.position?.current?.label;
    if (label) this.session.dwell[label] = Math.round(((this.session.dwell[label] || 0) + seconds) * 10) / 10;
  }

  /** His own scrolling is the answer to the card: it lifts silently and the spot follows him. */
  listenForHim(container, signal) {
    const his = () => {
      this._lastInput = performance.now();
      if (this._card && !this._card.hasAttribute("lifted")) this._card.choose("ignore");
    };
    for (const type of ["wheel", "touchmove", "pointerdown"]) container.addEventListener(type, his, { passive: true, signal });
    container.addEventListener("keydown", (e) => {
      if (["PageDown", "PageUp", "ArrowDown", "ArrowUp", " ", "Home", "End"].includes(e.key)) his();
    }, { signal });
    this.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && this._card && !this._card.hasAttribute("lifted") && !e.target.closest("button,a,input")) { e.preventDefault(); this._card.choose("accept"); }
    }, { signal });
  }

  // ---- the card ---------------------------------------------------------------------------------------------
  showCard() {
    const t = this.thread, s = store.state;
    const card = document.createElement("jv-resume-card");
    Object.assign(card, {
      thread: t, questions: [], now: store.now().toISOString(),
      changed: store.mark(t.ref)?.what || store.mark(t.id)?.what || null,
      private: !!(s.presence?.others || s.ui?.ambient),
    });
    card.addEventListener("jv-resume", (e) => this.answer(e.detail));
    this.$("#rd-card").append(card);
    this._card = card;
    requestAnimationFrame(() => card.focusAccept());
  }

  answer({ choice, label, page, y }) {
    const r = this.thread.resume;
    settled.set(this.thread.id, performance.now());  // answered: it stays away for this open and a quick reopen
    if (choice === "accept") {
      bridge.act("resume_accept", this.thread.id);
      if (!isWeak(r)) { this.choseHere(r.label); this.lock(r.label); }
    } else if (choice === "top") {
      this.session.corrected = true;
      this.jumpTo(1, 0);
    } else if (choice === "pick") {
      this.session.corrected = label !== r?.label;
      this.choseHere(label);
      this.jumpTo(page, y, TOP_ROOM + 40);
      this.lock(label);
    }
    // "ignore": the scroll (or Esc) was the answer; nothing to say, nothing to send
    this.liftCard();
  }

  /** The card goes (after its 200 ms lift). If it held the focus, the sheet takes it, so Tab carries on in the PDF. */
  liftCard() {
    const card = this._card;
    if (!card) return;
    if (card.contains(document.activeElement)) this.$("#rd-scroll")?.focus({ preventScroll: true });
    setTimeout(() => { card.remove(); if (this._card === card) this._card = null; }, 220);
  }

  /** He picked this question himself (or his yes covered it): it's the spot while he stays on it. */
  choseHere(label) {
    if (!label) return;
    this.session.chosen = label;
    this.session.since = [];
  }

  /** No card when he answered it this open, or the spot was saved minutes ago (a quick close and reopen). */
  settledLately(resume) {
    const answered = settled.get(this.thread.id);
    if (answered != null && performance.now() - answered < RECENT_MS) return true;
    const at = Date.parse(resume?.at || "");
    return Number.isFinite(at) && Math.abs(store.now().getTime() - at) < RECENT_MS;
  }

  /** Brackets lock onto the question's heading (250 ms), hold, then fade. Reduced motion: shown, then gone. */
  lock(label, { hold = false } = {}) {
    const q = (this.index?.questions || []).find((x) => x.label === label);
    const pv = q && this._viewer?.getPageView(q.page - 1);
    if (!pv) return;
    const vp = pv.viewport, box = vp.viewBox, [pw] = [pv.div.offsetWidth];
    const [x0, y0] = vp.convertToViewportPoint(box[0] + q.x, box[3] - q.y);
    const [, y1] = vp.convertToViewportPoint(box[0] + q.x, box[3] - q.y - q.h);
    const left = Math.max(4, x0 - 10), width = Math.max(pw - left * 2, (q.w || 40) * vp.scale + 20);
    let el = this.querySelector(".jv-reader__lock");
    if (!el) { el = document.createElement("div"); el.className = "jv-reader__lock"; el.setAttribute("aria-hidden", "true"); el.innerHTML = "<i></i><i></i><i></i><i></i>"; }
    el.style.cssText = `left:${left}px;top:${y0 - 8}px;width:${width}px;height:${y1 - y0 + 16}px`;
    el.className = "jv-reader__lock";
    pv.div.append(el);
    void el.offsetWidth;  // restart the snap
    el.classList.add("jv-reader__lock--on");
    this.dataset.locked = label;
    clearTimeout(this._lockTimer);
    if (!hold) this._lockTimer = setTimeout(() => { el.classList.add("jv-reader__lock--fade"); this._lockTimer = setTimeout(() => { el.remove(); delete this.dataset.locked; }, 320); }, 250 + LOCK_HOLD_MS);
  }

  // ---- leaving ----------------------------------------------------------------------------------------------
  /** The label sent with the session (threads.py re-decides it from the session when its hook is wired). */
  inferred() {
    const s = this.session, w = this.position, r = this.thread.resume;
    if (!w) return null;
    const spotOf = (l) => { const q = (this.index?.questions || []).find((x) => x.label === l); return q && { label: q.label, page: q.page, y: q.y, confirmed: true }; };
    const stayed = (labels, l) => labels.every((x) => topLabel(x) === topLabel(l));
    if (s.chosen && stayed(s.since, s.chosen) && spotOf(s.chosen)) return spotOf(s.chosen);  // his own choice stands
    if (r && s.seconds < GLANCE_S && s.path.length <= 1 && !s.corrected) return null;  // a glance keeps the saved spot
    const cur = w.current;
    if (r && !isWeak(r) && stayed([...s.path, ...(cur ? [cur.label] : [])], r.label) && spotOf(r.label)) {  // he hasn't moved off it
      return { ...spotOf(r.label), confirmed: r.source === "confirmed" };
    }
    const others = s.visible.filter((l) => !cur || l !== topLabel(cur.label));
    const clear = cur && !others.length && ((s.dwell[cur.label] || 0) >= CLEAR_DWELL_S || s.seconds < SHORT_SESSION_S) && !backAndForth(s.path.slice(-4), this.index);
    return clear ? { label: cur.label, page: cur.page, y: cur.y } : { label: `Page ${w.page}`, page: w.page };
  }

  save() {
    if (!this.thread || this._saved || !this._viewer) return;
    this.tickDwell();
    const spot = this.inferred();
    settled.set(this.thread.id, performance.now());  // a reopen within minutes opens at the spot, no card
    if (!spot) return;
    this._saved = true;
    const s = this.session, w = this.position;
    bridge.act("resume_save", this.thread.id, {
      ...spot,
      session: { file: this.thread.ref, seconds: Math.round(s.seconds), dwell: s.dwell, path: s.path.slice(-50),
        visible: s.visible, page: w.page, y: w.y, current: w.current?.label || null, corrected: s.corrected,
        chosen: s.chosen, since: s.since.slice(-50) },
    });
  }

  close() {
    if (this._closing) return;  // a double click on Close goes back once
    this._closing = true;
    this.save();
    if (!router.back()) router.go("/now");
  }

  fail(err) {
    const missing = /Missing|404|Unexpected server response/i.test(String(err?.message || err));
    const el = this.$(".jv-reader");
    if (!el) return;
    el.dataset.state = "missing";
    this.$("#rd-status").textContent = missing ? "This file isn't on this laptop yet. It opens once it has synced." : "This PDF couldn't be opened.";
  }
}
ReaderView.define("jv-view-reader");
router.register("/read", "jv-view-reader", "now", "Reader");  // the overseer may move this line to views/index.js
warmUp();

// ---- scenes (the demo PPS 7 is drawn by jarvis_hub/threads.py; nothing from his disk) ----------------------
const THREAD = {
  id: "th-pps7", kind: "pdf", ref: "file-pps7", branch: "ge-122", title: "PPS 7",
  thumb: { src: "/api/thumb/file-pps7-p3.webp", kind: "page", alt: "Page 3 of PPS 7, question 7" },
  done: ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"], viewed: ["Q4"], state: "paused", updated: "2026-11-14T21:14:00",
};
const put = (s, thread) => { s.threads = [thread, ...(s.threads || []).filter((x) => x.id !== thread.id)]; };
const Q7 = { page: 3, y: 71.2, label: "Q7", at: "2026-11-14T21:14:00" };
registerScene("reader-fresh", { path: "/read/th-pps7", about: "A fresh practice set: opens at the top, no card",
  patch: (s) => put(s, { ...THREAD, resume: null, done: [], viewed: [], state: "open" }) });
registerScene("reader-resume", { path: "/read/th-pps7", about: "Back two days later: open at Q7 behind the resume card",
  patch: (s) => put(s, { ...THREAD, resume: { ...Q7, source: "inferred" } }) });
registerScene("reader-weak", { path: "/read/th-pps7", about: "The spot wasn't clear: the card offers page 3",
  patch: (s) => put(s, { ...THREAD, resume: { page: 3, label: "Page 3", source: "inferred", at: Q7.at } }) });
registerScene("reader-accepted", { path: "/read/th-pps7", about: "Taken: the card is gone and the brackets hold on Q7",
  patch: (s) => put(s, { ...THREAD, resume: { ...Q7, source: "confirmed" } }) });
