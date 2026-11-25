// Views, tabs and the back stack. Paths live in the URL hash (#/life/ge-122) so deep links and Back work.
// Five tabs only (plan §2): Now · Today · Life · Activity · Controls. Memory lives inside Life,
// Under the hood inside Controls.
import { store } from "./store.js";

export const TABS = [
  { id: "now", label: "Now", path: "/now" },
  { id: "today", label: "Today", path: "/today" },
  { id: "life", label: "Life", path: "/life" },
  { id: "activity", label: "Activity", path: "/activity" },
  { id: "controls", label: "Controls", path: "/controls" },
];

const routes = [];   // { prefix, tag, tab, title }
const stack = [];    // { path, scroll }
const listeners = new Set();
let stage = null;
let current = { path: "", tab: "now", tag: "", params: [] };
let mounted = null;
let pinned = null;   // { path, elsewhere(path) }: a window that only ever shows one view (the Stage, N9)

export function resolve(path) {
  const clean = "/" + String(path || "").replace(/^#?\/?/, "").replace(/\/+$/, "");
  const match = routes.filter((r) => clean === r.prefix || clean.startsWith(r.prefix + "/")).sort((a, b) => b.prefix.length - a.prefix.length)[0];
  if (!match) return { path: "/now", ...routes.find((r) => r.prefix === "/now"), params: [] };
  return { path: clean, ...match, params: clean.slice(match.prefix.length).split("/").filter(Boolean) };
}

function render(next) {
  if (!stage) return;
  const sameView = mounted && mounted.localName === next.tag;
  if (stack.length) stack[stack.length - 1].scroll = stage.scrollTop;
  if (sameView) {
    mounted.params = next.params;
  } else {
    const el = document.createElement(customElements.get(next.tag) ? next.tag : "jv-view-placeholder");
    el.params = next.params;
    el.route = next;
    stage.replaceChildren(el);
    mounted = el;
  }
  current = next;
  document.title = `${next.title} · Jarvis`;
  document.documentElement.dataset.view = next.tab;
  for (const fn of listeners) fn(current);
}

export const router = {
  TABS,
  /** Register a view: a path prefix, the custom element that draws it, and the tab it belongs to. */
  register(prefix, tag, tab, title) { routes.push({ prefix, tag, tab, title: title || tab }); },
  get current() { return current; },
  onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },

  /** Keep this window on one path (the Stage window stays on /stage): going anywhere else calls
   *  `elsewhere(path)` instead (the Stage opens it in the hub), and the hub's nav.go is not followed here. */
  pin(path, elsewhere = () => {}) { pinned = { path: resolve(path).path, elsewhere }; },
  get pinned() { return pinned?.path || null; },

  start(el, initial) {
    stage = el;
    window.addEventListener("hashchange", () => this._arrive(location.hash, true));
    store.onEvent((event) => { if (event.type === "nav.go" && event.data?.path && !pinned) this.go(event.data.path); });
    this._arrive(initial || location.hash || "/now", false);
  },

  _arrive(path, fromHistory) {
    const next = resolve(path);
    if (next.path === current.path) return;
    if (pinned && next.path !== pinned.path) {  // the pinned window stays put (and its URL with it)
      if (fromHistory) history.replaceState(null, "", "#" + current.path);
      return;
    }
    const back = stack.length > 1 && stack[stack.length - 2].path === next.path;
    if (fromHistory && back) stack.pop(); else stack.push({ path: next.path, scroll: 0 });
    if (stack.length > 50) stack.shift();
    render(next);
    const scroll = back ? stack[stack.length - 1].scroll : 0;
    requestAnimationFrame(() => { if (stage) stage.scrollTop = scroll; });
  },

  /** Go to a path ("/life/ge-122"). Feedback is immediate: the view swaps in the same frame. */
  go(path) {
    const next = resolve(path);
    if (next.path === current.path) return;
    if (pinned && next.path !== pinned.path) { pinned.elsewhere(next.path); return; }
    if (location.hash !== "#" + next.path) history.pushState(null, "", "#" + next.path);
    this._arrive(next.path, false);
  },

  /** Back is always safe: the previous view and its scroll position, or Now when there is nothing behind. */
  back() {
    if (pinned) return false;
    if (stack.length > 1) {
      stack.pop();
      const prev = stack[stack.length - 1];
      history.replaceState(null, "", "#" + prev.path);
      render(resolve(prev.path));
      requestAnimationFrame(() => { if (stage) stage.scrollTop = prev.scroll || 0; });
      return true;
    }
    if (current.path !== "/now") { this.go("/now"); return true; }
    return false;
  },
  get depth() { return stack.length; },
  /** Redraw the current view in place (the window changed size). */
  refresh() { mounted?.update?.(); },
};
