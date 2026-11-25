// The only door between the UI and a backend. Live and demo modes talk to the hub server;
// scene mode (?scene=) answers locally from the fixture so every state can be opened without a server.
// Scene mode mirrors the hub's v2 rules (jarvis_hub/events.py Hub.act): close, the 60 s lifetime, stepping
// aside and CLEAR VIEW **dock** (window.dock); moves are window.order; recall, seen, archive, resume_save and
// resume_accept work as on the hub. window.close is only sent for done (an answered approval), archive and
// pure views. The Rail's derived items and the marks the hub makes are not worked out here (server only).
import { asDate, localIso } from "./dom.js";
import { store } from "./store.js";

let mode = "server";
const stamp = (ms = 0) => localIso(new Date(store.now().getTime() + ms));  // contract times are local, like the hub's
const emit = (type, data) => store.apply({ v: 2, type, ts: stamp(), data });
const DOCK_REASONS = new Set(["closed", "lifetime", "evicted", "aside", "cleared", "expired"]);
const SLOTS = new Set(["yes", "today", "homework", "messages", "jarvis", "parked"]);
/** Clear one mark (or all of them, ref null), as the hub's _seen does: only when something changes. */
function seen(ref) {
  const marks = store.state.marks || {};
  if (ref === null ? !Object.keys(marks).length : !(ref in marks)) return;
  emit("marks.updated", { marks: ref === null ? {} : Object.fromEntries(Object.entries(marks).filter(([k]) => k !== ref)) });
}
/** Reorder the windows on screen: one real reorder, never close + push (no false "new" marks). */
function reorder(order) {
  const ids = order.map((w) => w.id);
  if (ids.join("\n") !== store.state.windows.map((w) => w.id).join("\n")) emit("window.order", { ids });
}
let seq = 0;
const ASK_AGAIN = "It comes back with that change, for your yes.";  // no "Got it", no "Okay" (HUD v2 §9.2); a "no" gets no words
const GROW = { "1x1": "2x1", "2x1": "2x2", "1x2": "2x2", "2x2": "3x2", "3x2": "4x2", "4x2": "4x2" };  // "bigger": wider, never shorter

/** Packages that own actions of their own (R3 reach: jarvis_hub/reach.py on_act) mirror them for scenes here:
 *  fn(action, target, args, { emit, stamp }) → a result, or nothing to let the rules below run. */
const sceneHooks = [];
export const addSceneAct = (fn) => { sceneHooks.push(fn); };

/** What the demo backend does for each action, mirrored for scenes (jarvis_hub/events.py Hub.act). */
function sceneAct(action, target, args = {}) {
  for (const hook of sceneHooks) { const out = hook(action, target, args, { emit, stamp }); if (out) return out; }
  const s = store.state;
  const fact = () => structuredClone(s.facts.find((f) => f.id === target) || null);
  const receipt = (what, why, category, extra = {}) => emit("activity.added", {
    id: `a-ui-${++seq}`, ts: stamp(), kind: "done", what, why, category,
    sources: [{ kind: "you", label: "You · just now" }],
    undo: { until: stamp(864e5), label: "24 h" }, ...extra });
  const toast = (id, kind, text) => emit("toast", { id, kind, text, ttl_ms: 5000 });
  const calm = () => emit("orb.state", { state: s.settings?.muted ? "muted" : "idle" });
  for (const a of s.approvals.filter((x) => x.status === "pending" && x.expires && asDate(x.expires) <= store.now())) {
    emit("approval.resolved", { id: a.id, status: "expired" });  // an offer that ran out docks under Your yes (the store does it)
    if (s.orb?.state === "waiting" && !s.approvals.some((x) => x.status === "pending")) calm();
  }
  if (target.startsWith("branch:")) { toast(`t-${target}`, "info", "Branches can't be changed in demo mode yet. Nothing was changed."); return { ok: true }; }
  if (action === "set" && target.startsWith("source:")) {
    emit("settings.updated", { ...s.settings, sources: (s.settings.sources || []).map((x) => (x.id === target.slice(7) ? { ...x, on: !!args.value, status: args.value ? "ok" : "off" } : x)) });
    return { ok: true };
  }
  switch (action) {
    case "approve": case "decline": case "change": {
      if (action === "change" && (s.day?.proposals || []).some((p) => p.id === target)) {  // Tweak on a proposed change
        emit("day.updated", { ...s.day, proposals: s.day.proposals.filter((p) => p.id !== target) });
        toast(`t-${target}`, "info", ASK_AGAIN);
        break;
      }
      const a = s.approvals.find((x) => x.id === target);
      const status = { approve: "approved", decline: "declined", change: "changed" }[action];
      if (a && a.status === status) return { ok: true };  // the same answer twice (a double click): already done
      if (a && a.status === "expired") return { ok: false, message: "This offer ran out. Nothing was done." };
      if (!a || a.status !== "pending") return { ok: false, message: "That one has already been answered." };
      emit("approval.resolved", { id: target, status });
      emit("window.close", { id: `w-${target}` });  // answered, so done: the one case a thing's window closes
      calm();
      if (status === "approved") {
        const offer = `o-${target.replace(/^ap-/, "")}`;  // once it's done, the now card stops offering it
        if (s.now_card?.ready_to_offer?.some((o) => o.id === offer)) emit("nowcard.updated", { ...s.now_card, ready_to_offer: s.now_card.ready_to_offer.filter((o) => o.id !== offer) });
        receipt(a.title, "You said yes.", a.category || "calendar", { result: `Done. ${a.consequences[0]}`, branch_id: a.branch_id || "you" });
      } else if (status === "declined") {  // a "no" is a receipt too: a quiet row with nothing to undo
        receipt(a.title, "You said no. Nothing was changed.", a.category || "calendar", { id: `declined-${target}`, undo: null, branch_id: a.branch_id || "you" });
      } else toast(`t-${target}`, "info", String(args.text || "").trim() ? ASK_AGAIN : "Tell me what to change and it comes back for your yes.");
      break;
    }
    case "undo": {
      const r = s.actions.find((x) => x.id === target);
      if (r?.undone) return { ok: true };  // undo pressed twice: it is already undone
      if (!r || !r.undo) return { ok: false, message: "That can't be undone any more." };
      if (asDate(r.undo.until) <= store.now()) return { ok: false, message: "The undo window has passed." };
      emit("activity.added", { ...r, undone: true });
      toast(`t-undo-${target}`, "success", "Undone.");
      break;
    }
    case "pin": case "unpin": case "resize": {
      const w = s.windows.find((x) => x.id === target);
      if (!w) break;
      const size = args.size || GROW[w.size || "1x1"] || "2x1";
      if (action === "resize" && !(size in GROW)) return { ok: false, message: "Windows come in 1x1, 2x1, 1x2, 2x2, 3x2 and 4x2." };
      emit("window.push", action === "resize" ? { ...w, size } : { ...w, pinned: action === "pin" });
      break;
    }
    case "move": {
      const w = s.windows.find((x) => x.id === target);
      if (w) { const rest = s.windows.filter((x) => x !== w); reorder(args.to === "left" ? [w, ...rest] : [...rest, w]); }
      break;
    }
    case "order": {
      const ids = args.ids;
      if (!Array.isArray(ids) || !ids.every((i) => typeof i === "string")) return { ok: false, message: "A new order needs the window ids. Nothing was moved." };
      const byId = new Map(s.windows.map((w) => [w.id, w]));
      reorder([...ids.filter((i) => byId.has(i)).map((i) => byId.get(i)), ...s.windows.filter((w) => !ids.includes(w.id))]);
      break;
    }
    case "close": case "dock": {  // closing docks the thing into its Rail slot; only a pure view really closes
      if (!s.windows.some((w) => w.id === target)) break;
      const event = { id: target, reason: DOCK_REASONS.has(args.reason) ? args.reason : "closed" };
      if (SLOTS.has(args.slot)) event.slot = args.slot;
      emit("window.dock", event);
      break;
    }
    case "close_all": if (s.windows.length) emit("window.dock", { all: true, reason: "cleared" }); break;  // CLEAR VIEW
    case "recall": {  // bring a docked thing back as the window it was
      const item = store.railItem(target);
      if (!item?.window) return { ok: false, message: "That isn't on the Rail any more." };
      const { docked: _docked, ...win } = item.window;
      emit("window.push", { ...win, pushed: stamp() });
      seen(item.ref);
      break;
    }
    case "seen": seen(target === "all" ? null : target); break;
    case "archive": {  // done with it: the only way a thing leaves the Rail
      const item = store.railItem(target), ref = item ? item.ref : target;
      s.windows.filter((w) => w.id === target || w.ref === ref).forEach((w) => emit("window.close", { id: w.id }));
      const slots = Object.fromEntries(Object.entries(s.rail.slots).map(([name, slot]) => [name, { ...slot, items: slot.items.filter((i) => i.ref !== ref) }]));
      if (JSON.stringify(slots) !== JSON.stringify(s.rail.slots)) emit("rail.updated", { ...s.rail, slots });
      seen(ref);
      break;
    }
    case "resume_save": case "resume_accept": {
      const thread = structuredClone(s.threads.find((t) => t.id === target) || null);
      if (!thread) return { ok: false, message: "I can't find that piece of work any more." };
      if (action === "resume_accept") {
        if (!thread.resume) return { ok: false, message: "There's no saved spot for that yet." };
        thread.resume = { ...thread.resume, source: "confirmed" };
      } else {  // a local note, not an outward write: it needs no yes
        const label = String(args.label || "").slice(0, 80);
        if (!label || ("page" in args && !Number.isInteger(args.page)) || ("y" in args && typeof args.y !== "number") || ("seconds" in args && typeof args.seconds !== "number")) return { ok: false, message: "A saved spot needs a label and, if given, a page number or seconds. Nothing was saved." };
        thread.resume = { label, at: stamp(), source: args.confirmed === true ? "confirmed" : "inferred", ...("page" in args ? { page: args.page } : {}), ...("y" in args ? { y: args.y } : {}), ...("seconds" in args ? { seconds: args.seconds } : {}) };
      }
      thread.updated = stamp();
      emit("thread.updated", { thread });
      break;
    }
    case "confirm": case "edit": case "pin_rule": case "keep_mine": case "use_theirs": case "file": {
      const f = fact();
      if (!f) return { ok: false, message: "I can't find that any more." };
      const you = { kind: "you", label: "You · today" };
      if (action === "confirm") { Object.assign(f, { confidence: "sure", source: you, last_confirmed: stamp() }); delete f.basis; }
      if (action === "edit") { f.history = [{ was: f.statement, when: "until today" }, ...(f.history || [])]; Object.assign(f, { statement: String(args.statement ?? f.statement).slice(0, 400), confidence: "sure", source: you, last_confirmed: stamp() }); }
      if (action === "pin_rule") f.pinned = !f.pinned;
      if (f.conflict && (action === "keep_mine" || action === "use_theirs")) f.conflict.kept = action === "keep_mine" ? "mine" : "theirs";
      if (action === "file") { f.branch_id = args.branch_id || f.guess_branch_id || f.branch_id; delete f.guess_branch_id; }
      emit("fact.updated", { fact: f });
      break;
    }
    case "forget": emit("fact.updated", { id: target, forgotten: true }); toast(`t-forget-${target}`, "info", "Forgotten."); break;
    case "mute": case "unmute":
      emit("settings.updated", { ...s.settings, muted: action === "mute" });
      emit("orb.state", { state: action === "mute" ? "muted" : "idle" });
      break;
    case "set": emit("settings.updated", { ...s.settings, [target]: args.value }); break;
    case "revoke": emit("settings.updated", { ...s.settings, standing_permissions: (s.settings.standing_permissions || []).filter((p) => p.id !== target) }); break;
    case "apply": case "skip": {
      const p = (s.day.proposals || []).find((x) => x.id === target);
      if (p) {
        emit("day.updated", { ...s.day, proposals: s.day.proposals.filter((x) => x !== p) });
        if (action === "apply") receipt(p.text, "You applied a proposed change.", "calendar", { result: p.changes[0] });
      }
      break;
    }
    case "open": emit("nav.go", { path: target }); break;
    case "less": toast(`t-less-${target}`, "info", "Less of this from now on."); break;
    case "wrong": toast(`t-wrong-${target}`, "info", "I'll check that and stop relying on it."); break;
    case "ask": emit("caption.show", { text: "In demo mode I can't answer new questions yet.", source: null, ttl_ms: 5000 }); break;
    default: break;
  }
  return { ok: true };
}

export const bridge = {
  get mode() { return mode; },
  /** Load the first state. Scene mode reads the contract fixture; otherwise the hub server. */
  async loadState({ scene = false } = {}) {
    mode = scene ? "scene" : "server";
    const response = await fetch(scene ? "/contracts/examples/state.json" : "/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`The hub answered ${response.status}`);
    const state = await response.json();
    if (scene) state.mode = "scene";
    return state;
  },
  /** Send a user action. Resolves to { ok, message? }; never throws. */
  async act(action, target = "", args) {
    if (mode === "scene") return sceneAct(action, target, args);
    try {
      const response = await fetch("/api/act", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, target, args }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) return { ok: false, message: "That didn't go through. Try again in a moment." };
      return body;
    } catch {
      return { ok: false, message: "The hub isn't answering. Check that Jarvis is running, then try again." };
    }
  },
};
