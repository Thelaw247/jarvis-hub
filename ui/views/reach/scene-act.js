// Scene mode's mirror of jarvis_hub/reach.py on_act (core/bridge.js addSceneAct), so every Reach and Tasks control
// works in ?scene= without a hub: reach settings, Stop, Allow / Allow for this task / Deny on an agent's ask, Undo.
// The demo task's steps only play on the hub (they need its clock); in a scene "start" says so.
import { store } from "../../core/store.js";

const NEVER = /(^|\\)(appdata|windows|program files( \(x86\))?|programdata|\.ssh|\.gnupg|\$recycle\.bin)(\\|$)/i;
const LIVE = new Set(["running", "waiting", "parked"]);

/** The folders he typed, cleaned like the hub does (reach.py clean_folders), or null. */
export function cleanFolders(value) {
  if (!Array.isArray(value) || !value.every((v) => typeof v === "string")) return null;
  const out = [];
  for (const raw of value) {
    const path = raw.replace(/\//g, "\\").split(/\s+/).filter(Boolean).join(" ").replace(/^[\\ ]+|[\\ ]+$/g, "");
    if (!path) continue;
    if (path.split("\\").includes("..") || path.length > 260 || NEVER.test(path) || /^[a-z]:\\?$/i.test(path)) return null;
    if (!out.some((p) => p.toLowerCase() === path.toLowerCase())) out.push(path);
  }
  return out.length <= 20 ? out : null;
}

export function sceneReach(action, target, args = {}, { emit, stamp }) {
  const s = store.state;
  const say = (task, who, text) => { task.transcript = [...(task.transcript || []), { at: stamp(), who, text }]; };
  const toast = (text, kind = "info") => emit("toast", { id: `t-r3-${Date.now()}`, kind, text, ttl_ms: 5000 });
  if (action === "set" && target.startsWith("reach:")) {
    const reach = structuredClone(s.reach);
    if (!reach) return { ok: false, message: "Reach settings aren't loaded yet. Nothing was changed." };
    if (target.startsWith("reach:tool:")) {
      const tool = reach.tools.find((t) => t.id === target.slice(11));
      if (!tool || typeof args.value !== "boolean") return { ok: false, message: "That tool can't be changed like that. Nothing was changed." };
      if (args.value && tool.status === "needs_sign_in") return { ok: false, message: `${tool.name} needs you to sign in first. Nothing was changed.` };
      tool.on = args.value;
      if (tool.status === "connected" || tool.status === "off") tool.status = tool.on ? "connected" : "off";
    } else if (target === "reach:folders") {
      const folders = cleanFolders(args.value);
      if (!folders) return { ok: false, message: "That folder stays off limits: system folders, AppData and whole drives are never reachable." };
      reach.folders = folders;
    } else if (target === "reach:caps") {
      const task = Number(args.task_usd), day = Number(args.day_usd);
      if (!(task >= 0.1 && task <= 50 && day >= 0.1 && day <= 200)) return { ok: false, message: "A task cap goes from $0.10 to $50, a day cap from $0.10 to $200. Nothing was changed." };
      if (task > day) return { ok: false, message: "One task can't cost more than the whole day's cap. Nothing was changed." };
      reach.caps = { ...reach.caps, task_usd: Math.round(task * 100) / 100, day_usd: Math.round(day * 100) / 100 };
    }
    emit("reach.updated", reach);
    return { ok: true };
  }
  const taskOf = (id) => structuredClone((s.tasks || []).find((t) => t.id === id) || null);
  if (action === "start") { toast("The demo task plays on the hub: open the hub in demo mode and press Run it."); return { ok: true }; }
  if (action === "stop") {
    const task = taskOf(target);
    if (!task) return { ok: false, message: "I can't find that task any more." };
    if (!LIVE.has(task.state)) return { ok: true };
    for (const ask of task.asks) if (ask.answer === "waiting") { ask.answer = "denied"; emit("approval.resolved", { id: ask.id, status: "declined" }); emit("window.close", { id: `w-${ask.id}` }); }
    say(task, "you", "Stop that.");
    Object.assign(task, { state: "stopped", ended: stamp(), why: "You stopped it." });
    task.steps = task.steps.map((x) => ({ ...x, state: x.state === "done" ? "done" : "skipped" }));
    emit("task.updated", { task });
    return { ok: true };
  }
  if (action === "approve" || action === "decline") {
    const approval = s.approvals.find((a) => a.id === target);
    if (approval?.category !== "agent") return null;
    const task = structuredClone((s.tasks || []).find((t) => t.asks.some((a) => a.id === target)) || null);
    if (!task || approval.status !== "pending") return { ok: false, message: "That one has already been answered." };
    const ask = task.asks.find((a) => a.id === target);
    if (action === "approve") {
      const forTask = args.scope === "task";
      if (forTask && (ask.similar || 1) < 2) return { ok: false, message: "Allow for this task comes after the second ask like this one. Nothing was allowed." };
      ask.answer = forTask ? "allowed_for_task" : "allowed";
      if (forTask) task.allowed = [...new Set([...(task.allowed || []), ask.kind])];
      say(task, "you", forTask ? "Allow for the rest of this task." : "Allow.");
      task.state = "running";
    } else {
      ask.answer = "denied";
      say(task, "you", args.text ? `No. ${args.text}` : "No.");
      Object.assign(task, { state: "stopped", ended: stamp(), why: "You said no." });
    }
    emit("approval.resolved", { id: target, status: action === "approve" ? "approved" : "declined" });
    emit("window.close", { id: `w-${target}` });
    emit("orb.state", { state: s.settings?.muted ? "muted" : "idle" });
    emit("task.updated", { task });
    return { ok: true };
  }
  if (action === "undo") {
    const task = taskOf(target.startsWith("a-task-") ? target.slice(2) : target);
    if (!task) return null;
    if (task.state === "undone") return { ok: true };
    if (LIVE.has(task.state)) return { ok: false, message: "Stop the task first, then undo it." };
    if (!task.undo || !task.files.length) return { ok: false, message: "That task didn't change anything, so there's nothing to undo." };
    if (new Date(task.undo.until) <= store.now()) return { ok: false, message: "The undo window has passed." };
    const back = [...task.files].reverse().map((f) => ({ path: f.path, change: f.change === "created" ? "deleted" : "restored", where: f.change === "created" ? "undo bin, 30 days" : "back where it was" }));
    Object.assign(task, { state: "undone", undo: null, files: [...task.files, ...back] });
    emit("task.updated", { task });
    const receipt = s.actions.find((a) => a.id === `a-${task.id}`);
    if (receipt && !receipt.undone) emit("activity.added", { ...receipt, undone: true });
    toast("Undone. What it made is in the undo bin for 30 days.", "success");
    return { ok: true };
  }
  return null;
}
