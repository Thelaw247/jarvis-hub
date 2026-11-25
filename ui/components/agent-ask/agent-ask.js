// Agent permission asks on the hub's one approval card (REACH §5.5). An ask is an ordinary approval
// (contracts/approval) with category "agent": it sits in Your yes, uses <jv-approval-card>, its read-back is made by
// code on the hub (jarvis_hub/reach.py read_back) and the voice grammar is the same (yes / allow / go ahead; no).
// Only the answers differ: Allow · Deny · and, after the second similar ask in the same task, Allow for this task
// (approve with args { scope: "task" }); "Change it" doesn't apply to an agent's tool call.
// This registers those answers with the card's answers hook (approval-card.js registerAnswers); every other
// approval renders exactly as before.
import { store } from "../../core/store.js";
import { registerAnswers } from "../approval-card/approval-card.js";

/** True when the ask is the second (or later) of its kind in its task: then "Allow for this task" is offered. */
export function offersTaskAllow(approvalId, tasks = store.state.tasks || []) {
  for (const task of tasks) {
    const ask = (task.asks || []).find((a) => a.id === approvalId);
    if (ask) return (ask.similar || 1) >= 2;
  }
  return false;
}

registerAnswers("agent", (approval) => ({
  yes: "Allow", no: "Deny", kind: "Claude",
  extra: offersTaskAllow(approval.id) ? { label: "Allow for this task", args: { scope: "task" }, key: "task" } : null,
}));
