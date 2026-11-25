// Small helpers every component and view uses: safe HTML templates, the Jv base element, icons, time words.
// No colours here: everything visual comes from tokens.css.

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s ?? ""));

// A value written straight after `aria-…="` is an ARIA state: true and false must stay "true"/"false"
// (an empty aria-checked, aria-pressed or aria-expanded is invalid and reads as nothing).
const ARIA_VALUE = /\saria-[a-z]+\s*=\s*["']?$/i;

/** html`<p>${text}</p>`: every value is escaped unless it is another html`` result or raw().
 *  null, undefined and false render as nothing, except in an aria-* attribute, where booleans render as words. */
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((v, i) => {
    if (typeof v === "boolean" && ARIA_VALUE.test(strings[i])) out += String(v);
    else out += (Array.isArray(v) ? v : [v]).map((x) => (x == null || x === false ? "" : x instanceof Raw ? x.s : esc(x))).join("");
    out += strings[i + 1];
  });
  return new Raw(out);
}

/** Load a component's stylesheet once (index.html links them too, so the first paint is already styled). */
export function css(url) {
  const href = new URL(url).pathname.replace(/\.js$/, ".css");
  if (![...document.styleSheets].some((s) => s.href && new URL(s.href).pathname === href) &&
      !document.querySelector(`link[data-jv="${href}"]`)) {
    const link = Object.assign(document.createElement("link"), { rel: "stylesheet", href });
    link.dataset.jv = href;
    document.head.append(link);
  }
}

const ICONS = {
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3ZM5 11a7 7 0 0 0 14 0M12 18v3",
  "mic-off": "M9 9v3a3 3 0 0 0 5 2M15 10V6a3 3 0 0 0-6-.6M5 11a7 7 0 0 0 11 5.7M19 11a7 7 0 0 1-.6 2.8M12 18v3M4 4l16 16",
  pin: "M9 4h6l-1 6 3 3H7l3-3-1-6ZM12 13v7",
  close: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5l4.5 4.5L19 7.5",
  undo: "M9 7 4 12l5 5M4 12h10a6 6 0 0 1 0 12",
  chevron: "M9 6l6 6-6 6",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4-4",
  calendar: "M5 6h14v14H5zM5 10h14M9 3v4M15 3v4",
  file: "M7 3h7l4 4v14H7zM14 3v4h4",
  folder: "M3 7h6l2 2h10v10H3z",
  leaf: "M5 19C5 10 10 5 19 5c0 9-5 14-14 14ZM5 19l8-8",
  lock: "M7 11h10v9H7zM9 11V8a3 3 0 0 1 6 0v3",
  clock: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16ZM12 8v4l3 2",
  alert: "M12 4 3 20h18L12 4ZM12 10v4M12 17v.5",
  you: "M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM4 21a8 8 0 0 1 16 0",
  book: "M5 4h9a4 4 0 0 1 4 4v12H9a4 4 0 0 1-4-4V4ZM9 4v16",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
  spark: "M12 3v6M12 15v6M3 12h6M15 12h6M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3",
  help: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17v.5",
  canvas: "M4 5h16v11H4zM9 20h6M12 16v4",
  expand: "M4 10V4h6M20 14v6h-6M4 4l6 6M20 20l-6-6",
  arrow: "M5 12h14M13 6l6 6-6 6",
  list: "M8 6h12M8 12h12M8 18h12M4 6h.5M4 12h.5M4 18h.5",
  map: "M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M12 10V4M13.7 13l5.3 3M10.3 13 5 16",
  play: "M7 5l12 7-12 7z",
  more: "M6 12h.5M12 12h.5M18 12h.5",
  edit: "M4 20h4L19 9l-4-4L4 16v4ZM13 7l4 4",
  move: "M5 12h14M15 8l4 4-4 4M9 8l-4 4 4 4",
  trash: "M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13",
  gauge: "M4 16a8 8 0 1 1 16 0M12 16l4-5",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3Z",
  // Domain icons (HUD v2 §5): the kind of a thing is told by icon and position, never by colour. Our own
  // lines; `calendar` and `file` above are the calendar and file icons.
  class: "M4 4h16v10H4zM12 14v3M8 21l4-4 4 4M7.5 8h6M7.5 11h3.5",
  homework: "M5 4h10v16H5zM8 4v16M10.5 9h2.5M10.5 12h2.5M18 5h2v11l-1 3-1-3z",
  lab: "M9 3h6M10 3v6l-5.2 9.6A1.6 1.6 0 0 0 6.2 21h11.6a1.6 1.6 0 0 0 1.4-2.4L14 9V3M7 15h10",
  exam: "M9 3h6v3H9zM7 4.5H5V21h14V4.5h-2M8.5 13.5l2.5 2.5 4.5-4.5",
  message: "M4 5h16v11h-9l-5 4v-4H4z",
  job: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7ZM4.5 12a7.5 7.5 0 0 1 12-6M19.5 12a7.5 7.5 0 0 1-12 6",
  plotter: "M3 5h18M9 5v4M7 9h4l-2 4zM4 19c3-4 5 1 8-1.5S17 15 20 18",
  money: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM14.6 9.3c-.4-.9-1.4-1.5-2.6-1.5-1.5 0-2.6.8-2.6 2s1.1 1.7 2.6 2 2.6.8 2.6 2-1.1 2-2.6 2c-1.3 0-2.3-.6-2.7-1.6M12 5.8v2M12 16.2v2",
};
export const icon = (name, label) => raw(
  `<svg class="jv-icon" viewBox="0 0 24 24" ${label ? `role="img" aria-label="${esc(label)}"` : 'aria-hidden="true"'} focusable="false"><path d="${ICONS[name] || ICONS.help}"/></svg>`);

// ---- time words -----------------------------------------------------------------------------------
const pad = (n) => String(n).padStart(2, "0");
export const asDate = (v) => (v instanceof Date ? v : new Date(v));
/** A date as the contracts write it: local time, to the second, no offset ("2026-11-16T15:40:00"). */
export const localIso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 19);
/** "2d 04h", "5h 20m", "12m", or "Past due". */
export function countdown(due, now) {
  const mins = Math.round((asDate(due) - asDate(now)) / 60000);
  if (mins < 0) return "Past due";
  const d = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60;
  return d ? `${d}d ${pad(h)}h` : h ? `${h}h ${pad(m)}m` : `${m}m`;
}
export const hoursUntil = (due, now) => (asDate(due) - asDate(now)) / 3600000;
export function clockTime(v) {
  const d = asDate(v);
  return `${d.getHours() % 12 || 12}:${pad(d.getMinutes())} ${d.getHours() < 12 ? "am" : "pm"}`;
}
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const dayName = (v) => DAYS[asDate(v).getDay()];
export const shortDate = (v) => { const d = asDate(v); return `${MONTHS[d.getMonth()]} ${d.getDate()}`; };
export function dueWords(due) { const d = asDate(due); return `${DAYS[d.getDay()].slice(0, 3)} ${clockTime(d)}`; }
export function whenWords(ts, now) {
  const d = asDate(ts), n = asDate(now);
  const sameDay = d.toDateString() === n.toDateString();
  return sameDay ? clockTime(d) : `${shortDate(d)}, ${clockTime(d)}`;
}
export const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// ---- radio groups: one Tab stop each, arrow keys move (WAI-ARIA radio group pattern) -------------------
const RADIOS = '[role="radio"]:not([disabled])';
/** Roving tabindex: in every [role=radiogroup] under root only the checked radio (or the first) is a Tab stop. */
export function rove(root) {
  for (const group of root.querySelectorAll('[role="radiogroup"]')) {
    const radios = [...group.querySelectorAll(RADIOS)];
    const on = radios.find((r) => r.getAttribute("aria-checked") === "true") || radios[0];
    radios.forEach((r) => { r.tabIndex = r === on ? 0 : -1; });
  }
}
/** Keydown handler (core/keys.js installs it once): ← → ↑ ↓ Home End move to a radio and choose it. */
export function radioKey(e) {
  if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
  const radio = e.target.closest?.(RADIOS), group = radio?.closest('[role="radiogroup"]');
  if (!group) return;
  const radios = [...group.querySelectorAll(RADIOS)], i = radios.indexOf(radio), n = radios.length;
  const to = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: n - 1 }[e.key];
  if (to === undefined) return;
  e.preventDefault();
  const next = radios[(to + n) % n];
  radios.forEach((r) => { r.tabIndex = r === next ? 0 : -1; });
  next.focus();
  if (next.getAttribute("aria-checked") !== "true") next.click();  // selection follows focus
}

// ---- the base element ------------------------------------------------------------------------------
/** Light-DOM custom element. Subclasses set `static props` / `static attrs` and return html`` from render().
 *  Any descendant with data-act / data-nav emits a bubbling `jv-act` / `jv-nav` event when activated. */
export class Jv extends HTMLElement {
  static props = [];
  static attrs = [];
  static get observedAttributes() { return this.attrs; }

  constructor() {
    super();
    this._p = {};
    this._queued = false;
  }

  static define(tag) {
    for (const name of this.props) {
      Object.defineProperty(this.prototype, name, {
        get() { return this._p[name]; },
        set(v) { if (this._p[name] !== v) { this._p[name] = v; this.update(); } },
        configurable: true,
      });
    }
    if (!customElements.get(tag)) customElements.define(tag, this);
    return this;
  }

  connectedCallback() {
    for (const name of this.constructor.props) {  // values set before the element was defined
      if (Object.prototype.hasOwnProperty.call(this, name)) { const v = this[name]; delete this[name]; this[name] = v; }
    }
    if (!this._wired) {
      this._wired = true;
      this.addEventListener("click", (e) => this._activate(e));
      this.setup?.();
    }
    this._render();
  }

  disconnectedCallback() { this.teardown?.(); }
  attributeChangedCallback(_n, a, b) { if (a !== b) this.update(); }

  update() {
    if (this._queued || !this.isConnected) return;
    this._queued = true;
    queueMicrotask(() => { this._queued = false; if (this.isConnected) this._render(); });
  }

  _render() {
    const out = this.render?.();
    if (out == null) return;
    const active = this.contains(document.activeElement) ? document.activeElement.getAttribute("data-key") : null;
    this.innerHTML = String(out);
    rove(this);
    if (active) this.querySelector(`[data-key="${CSS.escape(active)}"]`)?.focus({ preventScroll: true });
    this.rendered?.();
  }

  _activate(e) {
    const el = e.target.closest?.("[data-act],[data-nav]");
    if (!el || el.disabled) return;  // nested components handle their own first and stop the event
    if (el.dataset.nav) this.emit("jv-nav", { path: el.dataset.nav });
    else {
      let args; try { args = el.dataset.args ? JSON.parse(el.dataset.args) : undefined; } catch { args = undefined; }
      this.emit("jv-act", { action: el.dataset.act, target: el.dataset.target || "", args });
    }
    e.stopPropagation();
  }

  emit(name, detail) { return this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true })); }
  $(sel) { return this.querySelector(sel); }
}
