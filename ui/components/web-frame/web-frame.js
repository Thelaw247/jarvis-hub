// <jv-web-frame>: a live web page inside a glass window on the Stage (REACH §5.1), or several pages with a small
// tab row ("tabs" window, like Huw's). Set .win = a window whose data follows contracts/web.schema.json:
//   { id, type: "web", title, data: { pages: [{ id, url, title, site?, frame? }], active? } }
// One page is a web window; two or more get the tab row.
//  - Each page is an <iframe> with a sandbox (scripts, same-origin, forms; never top navigation or pop-ups) and
//    no permissions. Pages from the hub's own address lose same-origin, so nothing framed can reach the hub.
//    The hub's bridge is never handed to a framed page (the desktop side never injects into frames either).
//  - A page that can't be framed shows a card instead (HUD v2 §14.2: kicker `WEB // site` from the window, the
//    page's title as the hero, its address as the one supporting line): when the page says so (frame: "no"),
//    when its site is known to refuse framing in a plain browser (web-policy.js), when it fails to load, or
//    when it hasn't loaded after LOAD_TIMEOUT_MS. Activating the card opens the page in his default browser.
//  - Activating the panel (on the Stage the whole panel is its "Open it") opens the page full size on the
//    Stage (<jv-web-full>), with "Open in browser" and Close; Esc closes it and focus goes back.
//  - Tabs: a real tablist (← → Home End move, selection follows focus). A page's frame is made the first time
//    its tab is shown and kept, so switching back is instant.
// Registers the "web" window kind (core/window-kinds.js) and its scenes.
import { clockTime, css, html, icon } from "../../core/dom.js";
import { el, params, registerGallery, registerScene, sceneName } from "../../core/scenes.js";
import { registerWindowKind } from "../../core/window-kinds.js";
import { addressLine, frameMode, frameSrc, LOAD_TIMEOUT_MS, pagesOf, safeUrl, sandboxFor, webKicker } from "./web-policy.js";

css(import.meta.url);

/** True in the desktop app (WebView2), where jarvis_hub/webframes.py lets the hub frame pages that refuse it.
 *  ?web=browser in a scene forces the plain-browser rules. */
export const desktopFrames = () => params.get("web") !== "browser" && !!window.chrome?.webview;

/** Open an address in his default browser. In the desktop app a new window from the hub's own page goes to the
 *  default browser (pywebview: OPEN_EXTERNAL_LINKS_IN_BROWSER); in a browser it opens a new tab, with no opener
 *  and no referrer. Only http(s). → true when it went. */
export function openInBrowser(url) {
  const safe = safeUrl(url);
  if (!safe) return false;
  const api = window.pywebview?.api;
  if (typeof api?.open_external === "function") { api.open_external(safe); return true; }
  window.open(safe, "_blank", "noopener,noreferrer");
  return true;
}

/** The tab each web window shows now (window id → index), so the kicker's "02 / 03" follows his clicks. */
const shownTab = new Map();
let seq = 0;

class WebFrame extends HTMLElement {
  get win() { return this._win; }
  set win(v) { this._win = v; if (this.isConnected) this.build(); }

  connectedCallback() { if (!this._built) this.build(); }
  disconnectedCallback() { this.timers?.forEach(clearTimeout); this.timers?.clear(); }

  /** Is this in the desktop app? (tests and scenes may set .desktop) */
  get onDesktop() { return typeof this.desktop === "boolean" ? this.desktop : desktopFrames(); }
  get timeout() { return Number.isFinite(this._timeout) ? this._timeout : LOAD_TIMEOUT_MS; }
  set timeout(ms) { this._timeout = ms; }

  build() {
    this._built = true;
    this.disconnectedCallback();
    this.timers = new Map();
    this.modes = new Map();  // page id → "loading" | "loaded" | "card"
    const { pages, active } = pagesOf(this._win);
    this.pages = pages;
    this.uid = `jv-web-${++seq}`;
    if (!pages.length) {
      this.replaceChildren(el("p", { className: "jv-muted", textContent: "That page can't be shown here." }));
      return;
    }
    const tabs = pages.length > 1;
    const root = el("div", { className: `jv-web${tabs ? " jv-web--tabs" : ""}` });
    if (tabs) {
      const list = el("div", { className: "jv-web__tabs" }, { role: "tablist", "aria-label": "Pages" });
      pages.forEach((p, i) => {
        const tab = el("button", { type: "button", className: "jv-web__tab", textContent: p.title, title: p.title },
          { role: "tab", id: `${this.uid}-tab-${i}`, "aria-controls": `${this.uid}-page-${i}`, "data-key": `tab-${p.id}` });
        tab.addEventListener("click", () => this.show(i));
        list.append(tab);
      });
      list.addEventListener("keydown", (e) => this.tabKey(e));
      root.append(list);
    }
    const box = el("div", { className: "jv-web__pages" });
    pages.forEach((p, i) => box.append(el("div", { className: "jv-web__page", hidden: true },
      tabs ? { role: "tabpanel", id: `${this.uid}-page-${i}`, "aria-labelledby": `${this.uid}-tab-${i}` } : {})));
    // the window's own "Open it" (HUD v2 §14.2: on the Stage it isn't drawn; the whole panel presses it)
    this.opener = el("button", { type: "button", className: "jv-btn jv-btn--small jv-web__open" }, { "data-key": "open" });
    this.opener.addEventListener("click", (e) => { e.stopPropagation(); this.open(); });
    root.append(box, this.opener);
    this.replaceChildren(root);
    const remembered = shownTab.get(this._win?.id);
    this.show(this.hasAttribute("full") || !Number.isInteger(remembered) || !pages[remembered] ? active : remembered, { quiet: true });
  }

  /** Show page i (made the first time it is shown). */
  show(i, { quiet = false } = {}) {
    if (!this.pages[i]) return;
    this.active = i;
    if (this._win?.id && !this.hasAttribute("full")) shownTab.set(this._win.id, i);
    const panels = this.querySelectorAll(".jv-web__page");
    panels.forEach((panel, k) => { panel.hidden = k !== i; });
    this.querySelectorAll(".jv-web__tab").forEach((tab, k) => {
      tab.setAttribute("aria-selected", String(k === i));
      tab.tabIndex = k === i ? 0 : -1;
    });
    const page = this.pages[i];
    if (!this.modes.has(page.id)) this.mount(page, panels[i]);
    this.label();
    if (!quiet) this.dispatchEvent(new CustomEvent("jv-web-tab", { bubbles: true, detail: { id: this._win?.id, index: i, page } }));
    // the window's kicker follows the tab: WEB // site, 02 / 03
    const host = this.closest("jv-window");
    if (host && !this.hasAttribute("full")) {
      const k = webKicker(this._win, null, i);
      host.setAttribute("status", k.status);
      if (k.index) host.setAttribute("index", k.index);
    }
  }

  tabKey(e) {
    const n = this.pages.length, to = { ArrowRight: this.active + 1, ArrowLeft: this.active - 1, Home: 0, End: n - 1 }[e.key];
    if (to === undefined || e.altKey || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    e.stopPropagation();
    this.show((to + n) % n);
    this.querySelector(".jv-web__tab[aria-selected='true']")?.focus();
  }

  /** Put a page into its panel: the live frame, or the card when it can't be framed. */
  mount(page, panel) {
    if (frameMode(page, { desktop: this.onDesktop }) === "card") { this.card(page, panel, "refused"); return; }
    this.modes.set(page.id, "loading");
    panel.dataset.mode = "loading";
    const wait = el("p", { className: "jv-web__wait jv-kicker", textContent: `Loading ${page.site}` }, { "aria-hidden": "true" });
    const src = frameSrc(page.url, location.origin, document.documentElement.dataset.theme);  // a page Jarvis made loads from the hub itself
    const frame = el("iframe", { className: "jv-web__frame", src, title: page.title, referrerPolicy: "no-referrer", loading: "eager" },
      { sandbox: sandboxFor(src, location.origin), allow: "" });
    frame.addEventListener("load", () => {
      if (this.modes.get(page.id) !== "loading") return;
      clearTimeout(this.timers.get(page.id));
      this.modes.set(page.id, "loaded");
      panel.dataset.mode = "loaded";
      this.label();
    });
    frame.addEventListener("error", () => this.card(page, panel, "error"));
    this.timers.set(page.id, setTimeout(() => { if (this.modes.get(page.id) === "loading") this.card(page, panel, "timeout"); }, this.timeout));
    panel.replaceChildren(wait, frame);
  }

  /** The card for a page that can't be shown here (§14.2): its title as the hero, its address under it. */
  card(page, panel, why) {
    clearTimeout(this.timers.get(page.id));
    this.modes.set(page.id, "card");
    panel.dataset.mode = "card";
    panel.dataset.why = why;
    const card = el("div", { className: "jv-web__card" });
    card.innerHTML = String(html`<p class="jv-web__title">${page.title}</p><p class="jv-web__address" title="${page.url}">${addressLine(page.url)}</p>`);
    panel.replaceChildren(card);
    if (panel.hidden === false) this.label();
  }

  /** The opener's words follow the page shown: the card opens his browser, a live page opens full size. */
  label() {
    const page = this.pages[this.active];
    if (!page || !this.opener) return;
    const card = this.modes.get(page.id) === "card";
    this.opener.dataset.does = card ? "browser" : "full";
    this.opener.replaceChildren(card ? "Open in browser" : "Open full size", el("span", { className: "jv-sr", textContent: `: ${page.title}` }));
  }

  /** The panel was activated: full size on the Stage, or (for a card) the default browser. */
  open() {
    const page = this.pages[this.active];
    if (!page) return;
    if (this.modes.get(page.id) === "card") { openInBrowser(page.url); return; }
    openFull(this._win, page.id, { returnTo: this.closest("jv-window") || this, desktop: this.desktop });
  }

  /** The mode of each page (for tests): { <page id>: "loading" | "loaded" | "card" } */
  get state() { return Object.fromEntries(this.modes || []); }
}
if (!customElements.get("jv-web-frame")) customElements.define("jv-web-frame", WebFrame);

// ---- full size on the Stage ------------------------------------------------------------------------------
// <jv-web-full>: the page (or the tabs) full size over the Stage, in one glass frame. Kicker `WEB // site` and
// the page's place, then "Open in browser" and Close. Esc closes it; focus goes back to the window it came from.
// Keys typed here never reach the hub's shortcuts. One at a time.
class WebFull extends HTMLElement {
  connectedCallback() {
    if (this._built) return;
    this._built = true;
    this.setAttribute("role", "dialog");
    this.setAttribute("aria-modal", "true");
    this.innerHTML = String(html`<div class="jv-web-full__scrim" aria-hidden="true"></div>
      <section class="jv-web-full__panel jv-frame">
        <header class="jv-web-full__head">
          <h2 class="jv-web-full__kicker jv-kicker" id="jv-web-full-title"></h2>
          <span class="jv-web-full__index jv-kicker"></span>
          <button type="button" class="jv-btn jv-btn--small" data-key="browser">Open in browser</button>
          <button type="button" class="jv-web-full__close" data-key="close">${icon("close")}<span class="jv-sr">Close the page</span></button>
        </header>
        <div class="jv-web-full__body"></div>
      </section>`);
    this.setAttribute("aria-labelledby", "jv-web-full-title");
    this.querySelector("[data-key=close]").addEventListener("click", () => this.close());
    this.querySelector(".jv-web-full__scrim").addEventListener("click", () => this.close());
    this.querySelector("[data-key=browser]").addEventListener("click", () => openInBrowser(this.frame?.pages?.[this.frame.active]?.url));
    this.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); this.close(); }
      else if (e.key === "Tab") this.trap(e);
      e.stopPropagation();  // the hub's shortcuts (1-5, /, m) don't apply while a page is open
    });
    this.addEventListener("jv-web-tab", () => this.head());
  }

  /** Show `win` with page `pageId` first. */
  show(win, pageId, { returnTo = null, desktop } = {}) {
    this.returnTo = returnTo;
    this.frame = el("jv-web-frame", typeof desktop === "boolean" ? { desktop } : {}, { full: true });
    this.frame.win = { ...win, data: { ...win.data, active: pageId } };
    this.querySelector(".jv-web-full__body").replaceChildren(this.frame);
    this.head();
    this.querySelector("[data-key=close]").focus({ preventScroll: true });
  }

  head() {
    const k = webKicker(this.frame?.win, null, this.frame?.active);
    this.querySelector(".jv-web-full__kicker").textContent = `${k.heading} // ${k.status}`;
    this.querySelector(".jv-web-full__index").textContent = k.index;
  }

  trap(e) {
    const stops = [...this.querySelectorAll("button, iframe, [tabindex='0']")].filter((n) => !n.closest("[hidden]") && n.getClientRects().length);
    if (!stops.length) return;
    const first = stops[0], last = stops.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  close() {
    const back = this.returnTo;
    this.remove();
    if (back?.isConnected) {
      const target = back.querySelector?.('[data-key="open"]') || back;
      target.focus?.({ preventScroll: true });
    }
  }
}
if (!customElements.get("jv-web-full")) customElements.define("jv-web-full", WebFull);

/** Open a web window full size on the Stage (one at a time). → the <jv-web-full> */
export function openFull(win, pageId, options = {}) {
  document.querySelector("jv-web-full")?.remove();
  const full = document.createElement("jv-web-full");
  document.body.append(full);
  full.show(win, pageId, options);
  return full;
}

// ---- the window kind -------------------------------------------------------------------------------------
registerWindowKind("web", {
  content: (win) => el("jv-web-frame", { win }),
  kicker: (win, s) => webKicker(win, s, shownTab.get(win.id)),
  role: "media",  // near the centre of the board, edge to edge (HUD v2 §14.2 L tier)
  width: 600,
  size: "2x2",
});

// ---- scenes ----------------------------------------------------------------------------------------------
const D = "2026-11-16";
const DEMO = "/demo/web";
export const WEB_PAGES = {
  search: { id: "p-search", url: `${DEMO}/search.html?q=method+of+joints`, title: "method of joints - Search", site: "search.demo" },
  article: { id: "p-article", url: `${DEMO}/article.html`, title: "The method of joints, step by step", site: "statics.demo" },
  blocked: { id: "p-doc", url: "https://docs.google.com/document/d/demo-ge122-notes/edit", title: "GE 122 lab notes", site: "docs.google.com", frame: "no" },
};
const absolute = (p) => ({ ...p, url: new URL(p.url, location.origin).href });
export const WEB_WINDOWS = {
  search: { id: "w-web-search", type: "web", title: "Search", pushed: `${D}T15:40:30`, data: { pages: [absolute(WEB_PAGES.search)] } },
  tabs: { id: "w-web-tabs", type: "web", title: "Truss reading", pushed: `${D}T15:40:50`, data: { pages: [absolute(WEB_PAGES.article), absolute(WEB_PAGES.search), WEB_PAGES.blocked], active: "p-article" } },
  blocked: { id: "w-web-doc", type: "web", title: "Lab notes", pushed: `${D}T15:41:05`, data: { pages: [WEB_PAGES.blocked] } },
};

/** A web window as the Stage draws it (for the gallery: the kicker, the content, opens/media like the board). */
function framed(win, { board = true, tools = false } = {}) {
  const k = webKicker(win);
  const node = el("jv-window", {}, { heading: k.heading, status: k.status, index: k.index || null, meta: `Added ${clockTime(win.pushed)}`, "window-id": win.id, opens: board, media: board, "data-show-tools": tools });
  node.append(el("jv-web-frame", { win }));
  node.style.width = "600px";
  return node;
}

registerGallery("web-frame", [
  { label: "Web window, a live page", build: () => framed(WEB_WINDOWS.search), wide: true },
  { label: "Tabs window, three pages", build: () => framed(WEB_WINDOWS.tabs), wide: true },
  { label: "Card, a page that can't be framed", build: () => framed(WEB_WINDOWS.blocked), wide: true },
  { label: "Pin and close, shown as on hover or focus", build: () => framed(WEB_WINDOWS.blocked, { tools: true }), wide: true },
  { label: "On the hub (no board): the opener shows", build: () => framed(WEB_WINDOWS.search, { board: false }), wide: true },
], { about: "A live web page in the glass frame (REACH §5.1). Pages that can't be framed become a card: WEB // site, the title, the address; activating it opens his browser." });

const stageScene = (about, extra = () => {}) => ({ path: "/stage", about, patch: (s) => {
  s.windows = [WEB_WINDOWS.search, WEB_WINDOWS.tabs, { id: "w-due-pps7", type: "countdown", title: "Due", ref: "due-pps7", size: "1x1", pushed: `${D}T15:40:21` }];
  s.approvals = [];
  s.orb = { state: "speaking", level: 0.6 };
  s.caption = { text: "Here's the method of joints, and your lab notes beside it.", source: { kind: "web", label: "Web" }, ttl_ms: 600000 };
  extra(s);
} });
registerScene("stage-web", stageScene("Web windows on the Stage: a live search page, a tabs window (article, search, lab notes) and a countdown"));
registerScene("stage-web-card", stageScene("A web window whose page refuses framing in a plain browser: the card (WEB // site, title, address)", (s) => { s.windows = [WEB_WINDOWS.blocked, WEB_WINDOWS.search]; }));
registerScene("stage-web-full", stageScene("A web window opened full size on the Stage, with Open in browser and Close"));

// the full-size scene opens the tabs window once the Stage has drawn it
if (sceneName === "stage-web-full") {
  const ready = () => {
    if (!document.documentElement.hasAttribute("data-ready")) { setTimeout(ready, 50); return; }
    openFull(WEB_WINDOWS.tabs, "p-article", { returnTo: document.querySelector('jv-window[window-id="w-web-tabs"]') });
  };
  ready();
}
