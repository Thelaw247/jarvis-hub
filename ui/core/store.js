// The one place UI state lives. Views read it and subscribe; events (live or scene) are folded in by apply().
// Shapes are the contracts in /contracts (v2). Never add a field here that the contracts don't have,
// except the UI-only `ui` slice.
//
// v2 (Night HUD): nothing gets away. `windows` holds only the windows on screen; a window that is closed,
// pushed out by a sixth, cleared or whose approval ran out is docked into its Rail slot
// (`rail.slots.<slot>.items[].window`), never deleted. The Rail, the "since you looked" `marks`, work `threads`
// and the `focus` cue live on the server; the server sends rail.updated / marks.updated after anything changes them.
import { placeWindow } from "./windows-core.js";

export const SLOTS = ["yes", "today", "homework", "messages", "jarvis", "parked"];  // rail.schema.json
const PURE_VIEWS = new Set(["chart", "next_up", "map"]);  // views of nothing in particular: they just close
const SLOT_OF = { approval: "yes", timeline: "today", timer: "today", countdown: "homework", file: "homework", fact: "jarvis", unsorted: "jarvis", notice: "jarvis", branch_card: "parked" };
const KIND_OF = { approval: "approval", timeline: "event", timer: "event", countdown: "due", file: "file", fact: "fact", unsorted: "fact", notice: "notice", branch_card: "branch", agent_task: "job" };
const emptyRail = () => ({ slots: Object.fromEntries(SLOTS.map((name) => [name, name === "jarvis" ? { items: [], said: [] } : { items: [] }])) });
const wholeRail = (rail) => ({ ...rail, slots: { ...emptyRail().slots, ...(rail?.slots || {}) } });  // a v1 state has no Rail yet
/** The Rail slot a window docks into, or null for a pure view. Mirrors jarvis_hub/events.py slot_for. */
export const slotFor = (w) => (SLOTS.includes(w.slot) ? w.slot : PURE_VIEWS.has(w.type) ? null : SLOT_OF[w.type] || "jarvis");
const railDrop = (rail, gone) => ({ ...rail, slots: Object.fromEntries(Object.entries(rail.slots).map(([name, slot]) => [name, { ...slot, items: slot.items.filter((i) => !gone(i)) }])) });
const railPut = (rail, item) => {  // one item per ref in the whole Rail, newest first in its slot
  const next = railDrop(rail, (i) => i.ref === item.ref);
  next.slots[item.slot] = { ...next.slots[item.slot], items: [item, ...next.slots[item.slot].items] };
  return next;
};
const railItems = (rail) => SLOTS.flatMap((name) => rail.slots[name].items);

const empty = () => ({
  v: 2, mode: "scene", now: new Date().toISOString(),
  orb: { state: "idle" }, presence: { here: true, others: false },
  now_card: null, branches: [], cards: {}, facts: [], actions: [], approvals: [], windows: [], jobs: [],
  day: null, settings: { interruption: "balanced", theme: "night", motion: "full" }, metrics: null,
  caption: null, toasts: [], files: [], learned_today: 0, demo: null,
  rail: emptyRail(), marks: {}, threads: [], focus: null,
  reach: null, tasks: [],  // R3: contracts/reach and contracts/agent_task (optional in the state)
  ui: { ambient: false, online: true, log: [] },
});

const state = empty();
const subs = new Set();
let pending = null;
let clock = { base: Date.now(), at: performance.now(), frozen: false };

function changed(...keys) {
  if (!pending) {
    pending = new Set();
    queueMicrotask(() => { const keysNow = pending; pending = null; for (const fn of [...subs]) fn(state, keysNow); });
  }
  keys.forEach((k) => pending.add(k));
}

/** Take a window off the screen and fold it into its Rail slot, kept whole for recall (events.py dock_window). */
function dock(win, at, slot) {
  state.windows = state.windows.filter((w) => w.id !== win.id);
  slot = SLOTS.includes(slot) ? slot : slotFor(win);
  if (!slot) return;
  const item = { ref: win.ref || win.id, slot, kind: KIND_OF[win.type] || "notice", title: win.title, at, window: { ...win, docked: true, slot } };
  for (const key of ["thumb", "tier"]) if (key in win) item[key] = win[key];
  state.rail = railPut(state.rail, item);
}

const upsert = (list, item, front) => {
  const i = list.findIndex((x) => x.id === item.id);
  if (i >= 0) return list.map((x, j) => (j === i ? item : x));
  return front ? [item, ...list] : [...list, item];
};

export const store = {
  state,
  /** Replace the whole state (first load, scene load, demo restart). */
  load(next, { frozen = false } = {}) {
    Object.assign(state, empty(), next, { rail: wholeRail(next.rail), ui: { ...empty().ui, ...(next.ui || {}), log: [] } });
    clock = { base: new Date(next.now).getTime(), at: performance.now(), frozen };
    changed(...Object.keys(state));
  },
  /** Shallow patch of top-level keys. */
  set(patch) { Object.assign(state, patch); changed(...Object.keys(patch)); },
  setUi(patch) { state.ui = { ...state.ui, ...patch }; changed("ui"); },
  /** The hub clock: real time in live mode, the demo day's clock in demo mode, frozen in scenes. */
  now() { return new Date(clock.frozen ? clock.base : clock.base + (performance.now() - clock.at)); },
  subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
  /** Call fn now and whenever one of `keys` changes. Returns an unsubscribe function. */
  watch(keys, fn) {
    fn(state);
    return this.subscribe((s, changedKeys) => { if (keys.some((k) => changedKeys.has(k))) fn(s); });
  },
  byId: (key, id) => state[key].find((x) => x.id === id),
  branch: (id) => state.branches.find((b) => b.id === id),
  children: (id) => state.branches.filter((b) => b.parent === id),
  pendingApprovals: () => state.approvals.filter((a) => a.status === "pending"),
  /** A Rail slot's items (things, by ref). */
  slot: (name) => state.rail.slots[name]?.items || [],
  /** A thing on the Rail, by its ref or by the id of its docked window. */
  railItem: (target) => railItems(state.rail).find((i) => i.ref === target) || railItems(state.rail).find((i) => i.window?.id === target),
  /** The "since you looked" mark on a thing ({ what, at }), if any. Clear it with bridge.act("seen", ref). */
  mark: (ref) => state.marks[ref] || null,
  thread: (id) => state.threads.find((t) => t.id === id),
  /** True while Jarvis means this thing (ui.focus): its `until` hasn't passed on the hub clock. */
  focused(ref) { const f = state.focus; return !!f && f.ref === ref && (!f.until || new Date(f.until) > this.now()); },

  /** Fold one event envelope into the state. Mirrors jarvis_hub/events.py apply_event. */
  apply(event) {
    const { type, data } = event;
    // a voice-level tick (~12 a second while someone talks): only the orbs listen to it, nothing else re-renders
    // (v0.11.2: every tick re-rendered the shell, which made Jarvis's caption flicker)
    if (type === "orb.state" && data && state.orb && data.state === state.orb.state && "level" in data
        && Object.keys(data).every((k) => k === "level" || k === "state")) {
      state.orb = { ...state.orb, level: data.level };
      changed("orb_level");
      return;
    }
    const at = event.ts || state.now;
    state.ui = { ...state.ui, log: [{ type, ts: event.ts, at: performance.now() }, ...state.ui.log].slice(0, 30) };
    const keys = ["ui"];
    switch (type) {
      case "orb.state": state.orb = data; keys.push("orb"); break;
      case "nowcard.updated": state.now_card = data; keys.push("now_card"); break;
      case "branch.updated":
        state.branches = upsert(state.branches, data.branch);
        if (data.card) state.cards = { ...state.cards, [data.branch.id]: data.card };
        keys.push("branches", "cards"); break;
      case "window.push": {
        state.rail = railDrop(state.rail, (i) => i.window?.id === data.id);  // recalled: back on screen
        if (data.docked) dock(data, at);  // pushed straight into its slot
        else {
          const before = state.windows;
          state.windows = placeWindow(before, data);
          // when a 6th arrives the oldest unpinned window docks; it is never deleted
          before.filter((w) => w.id !== data.id && !state.windows.some((x) => x.id === w.id)).forEach((w) => dock(w, at));
        }
        keys.push("windows", "rail"); break;
      }
      case "window.dock":
        state.windows.filter((w) => data.all || w.id === data.id).forEach((w) => dock(w, at, data.slot));
        keys.push("windows", "rail"); break;
      case "window.order": {  // a real reorder: nothing closes, nothing counts as new
        const rank = new Map(data.ids.map((id, i) => [id, i]));
        const place = (w) => (rank.has(w.id) ? rank.get(w.id) : rank.size);
        state.windows = state.windows.map((w, i) => [w, i]).sort((a, b) => place(a[0]) - place(b[0]) || a[1] - b[1]).map(([w]) => w);
        keys.push("windows"); break;
      }
      case "window.close":  // only for done, archive and pure views; a v1 "close everything" docks instead
        if (data.all) { state.windows.forEach((w) => dock(w, at)); keys.push("rail"); }
        else state.windows = state.windows.filter((w) => w.id !== data.id);
        keys.push("windows"); break;
      case "rail.updated": state.rail = wholeRail(data); keys.push("rail"); break;
      case "marks.updated": state.marks = data.marks; keys.push("marks"); break;
      case "thread.updated":
        state.threads = data.archived ? state.threads.filter((t) => t.id !== data.id) : upsert(state.threads, data.thread, true);
        keys.push("threads"); break;
      case "ui.focus": state.focus = data.ref ? data : null; keys.push("focus"); break;
      case "caption.show": state.caption = { ...data, shown: performance.now() }; keys.push("caption"); break;
      case "approval.pending": state.approvals = upsert(state.approvals, data, true); keys.push("approvals"); break;
      case "approval.resolved":
        state.approvals = state.approvals.map((a) => (a.id === data.id ? { ...a, status: data.status } : a));
        if (data.status === "expired") {  // it ran out unanswered: it docks under Your yes instead of vanishing
          const approval = state.approvals.find((a) => a.id === data.id);
          state.windows.filter((w) => w.type === "approval" && w.ref === data.id).forEach((w) => dock(w, at, "yes"));
          if (approval && !store.railItem(data.id)) state.rail = railPut(state.rail, { ref: data.id, slot: "yes", kind: "approval", title: approval.title, at });
        } else state.rail = railDrop(state.rail, (i) => i.ref === data.id);  // answered: done, so it leaves the Rail
        keys.push("approvals", "windows", "rail"); break;
      case "activity.added": state.actions = upsert(state.actions, data, true); keys.push("actions"); break;
      case "job.progress":
        state.jobs = upsert(state.jobs, data).filter((j) => j.state === "running"); keys.push("jobs"); break;
      case "toast": state.toasts = upsert(state.toasts, data); keys.push("toasts"); break;
      case "presence.changed": state.presence = { ...state.presence, ...data }; keys.push("presence"); break;
      case "fact.updated":
        state.facts = data.forgotten ? state.facts.filter((f) => f.id !== data.id) : upsert(state.facts, data.fact, true);
        keys.push("facts"); break;
      case "day.updated": state.day = data; keys.push("day"); break;
      case "metrics.updated": state.metrics = data; keys.push("metrics"); break;  // v0.18.0: Under the hood, live
      case "settings.updated": state.settings = data; keys.push("settings"); break;
      case "reach.updated": state.reach = data; keys.push("reach"); break;  // R3: what Jarvis can do
      case "task.updated": state.tasks = upsert(state.tasks, data.task, true); keys.push("tasks"); break;  // R3: a Claude agent task
      default: break;  // nav.go is handled by the router
    }
    changed(...keys);
    for (const fn of eventSubs) fn(event);
  },
  onEvent(fn) { eventSubs.add(fn); return () => eventSubs.delete(fn); },
};
const eventSubs = new Set();
