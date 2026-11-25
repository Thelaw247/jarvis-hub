// Turns a pushed window (contracts/window) into its content, using data the hub already has, so a widget
// appears with the event and needs no extra call (HUB_TRUST §2a). Every window follows the one anatomy of HUD v2
// §14.2: a kicker row (windowKicker), one hero, at most one line of supporting text, one footer item. Sources,
// details and controls wait in the window's "Why?" drawer (hover or keyboard focus): still real controls.
import { asDate, clockTime, dueWords, shortDate } from "../../core/dom.js";
import { el } from "../../core/scenes.js";
import { windowKind } from "../../core/window-kinds.js";

const allDue = (s) => Object.values(s.cards).flatMap((c) => c.due || []);

export function windowTitle(win, s) {
  if (win.type === "branch_card") return s.branches.find((b) => b.id === win.ref)?.name || win.title;
  return win.title;
}

const lastPart = (text) => String(text || "").split(" · ").pop();
const firstPart = (text) => { const parts = String(text || "").split(" · "); return parts.length > 1 ? parts[0] : ""; };
const bare = (name) => String(name || "").replace(/\.[a-z0-9]+$/i, "");
const APPROVAL_KIND = { calendar: "Calendar", files: "Files", messages: "Messages", memory: "Memory", tree: "Life Map", skills: "Skills" };
const APPROVAL_WORD = { pending: "Your yes", approved: "Done", changed: "Changing", declined: "Declined", expired: "Ran out" };
const FILE_KIND = { pdf: "PDF", slides: "Slides", doc: "Document", sheet: "Sheet", code: "Code", folder: "Folder", image: "Image" };
const mins = (hhmm) => { const [h, m] = String(hhmm || "").split(":").map(Number); return h * 60 + (m || 0); };
const nice = (hhmm) => { const [h, m] = String(hhmm || "").split(":").map(Number); return Number.isFinite(h) ? `${h % 12 || 12}:${String(m || 0).padStart(2, "0")} ${h < 12 ? "am" : "pm"}` : ""; };

/** The next thing on the day's timeline that isn't done (the one under way counts), or null. */
function nextOnDay(s, now) {
  const d = asDate(now), at = d.getHours() * 60 + d.getMinutes();
  return (s.day?.items || []).find((it) => it.state !== "done" && mins(it.end) > at) || null;
}
const approvalStatus = (a, now) => (a.status === "pending" && a.expires && asDate(a.expires) <= asDate(now) ? "expired" : a.status);

/** The window's kicker row and footer (HUD v2 §14.2), from real data only: `heading` // `status` is the kicker
 *  (SOURCE // TOPIC: "GE 122 // PPS 7", "CALENDAR // YOUR YES"), `index` the one index or time top-right
 *  ("P. 3 / 5", "4:00 PM"), `meta` the one footer item under the frame (when it was put up, or "Pinned").
 *  `thread`: the work thread on the window's thing. */
export function windowKicker(win, s, thread, now = s.now) {
  const name = windowTitle(win, s);
  // a title written "Source · Topic" ("CHEM 142 · Lab 4") is the kicker's two halves
  const out = { heading: firstPart(name) || name, status: firstPart(name) ? lastPart(name) : "", index: "", meta: win.pushed ? `Added ${clockTime(win.pushed)}` : "" };
  const kind = windowKind(win.type);  // a kind that brings its own content (core/window-kinds.js) says its own kicker
  if (kind) Object.assign(out, kind.kicker?.(win, s, thread, now));
  else kick(out, win, s, thread, now);
  if (win.pinned) { if (!out.index) out.index = "Pinned"; else if (!out.meta) out.meta = "Pinned"; }  // one index, one footer item
  return out;
}

function kick(out, win, s, thread, now) {
  switch (win.type) {
    case "countdown": {
      const due = allDue(s).find((d) => d.id === win.ref);
      if (due) Object.assign(out, firstPart(due.title) ? { heading: firstPart(due.title), status: lastPart(due.title) } : { heading: due.title, status: "Due" });
      break;
    }
    case "next_up": Object.assign(out, { heading: s.now_card?.next_up?.source?.label || "Today", status: "Next", index: s.now_card?.next_up?.when || "" }); break;
    case "branch_card": if (firstPart(s.cards[win.ref]?.status)) out.status = "Status"; else { out.status = out.heading; out.heading = "Life Map"; } break;
    case "timeline": out.heading = "Today"; out.status = "Next"; break;
    case "file": {
      const file = s.files.find((f) => f.id === win.ref);
      if (file) out.heading = bare(file.name);
      if (thread?.resume?.label && thread.resume.label.length <= 10) out.status = thread.resume.label;
      const page = /^Page (\d+) of (\d+)$/.exec(file?.page || "");
      if (page) out.index = `P. ${thread?.resume?.page || page[1]} / ${page[2]}`;
      break;
    }
    case "fact": case "unsorted": {
      const fact = s.facts.find((f) => f.id === win.ref);
      const branch = fact && s.branches.find((b) => b.id === fact.branch_id);
      out.heading = win.type === "unsorted" ? "Unsorted" : branch && branch.kind !== "root" ? branch.name : win.title || "Fact";
      if (fact) out.status = fact.conflict ? "Conflict" : fact.confidence === "guess" ? "Guess" : fact.pinned ? "Rule" : "Fact";
      break;
    }
    case "approval": {
      const a = s.approvals.find((x) => x.id === win.ref);
      if (a) {
        const status = approvalStatus(a, now);
        Object.assign(out, { heading: APPROVAL_KIND[a.category] || "Change", status: APPROVAL_WORD[status] || APPROVAL_WORD.expired, index: status === "pending" && a.expires ? clockTime(a.expires) : "" });  // (how long it waits: the one time)
      }
      break;
    }
    case "timer": if (!out.status) out.heading = win.data?.label || win.title || "Timer"; break;
    case "notice": if (win.data?.kind === "error" && !out.status) out.status = "Problem"; break;
    default: break;
  }
}

// ---- the one anatomy (HUD v2 §14.2): one hero, at most one line; the rest waits in the "Why?" drawer -------
const title = (text) => {  // the words sit in a span, so the active window's plate wraps line by line
  const h = el("h3", { className: "jv-pane__title", title: text });
  h.append(el("span", { textContent: text }));
  return h;
};
const words = (text, cls = "") => el("p", { className: cls, textContent: text });
/** A row of real sources (chips) for the drawer. */
function sources(list, label = "Source") {
  const real = (list || []).filter(Boolean);
  if (!real.length) return null;
  const row = el("p", { className: "jv-more__sources" });
  row.append(el("span", { className: "jv-label", textContent: label }), ...real.map((source) => el("jv-source-chip", { source })));
  return row;
}
/** A resting window's content: `hero` (an element), at most one `line` of supporting text, and `more`: what
 *  the "Why?" drawer holds (sources, details, controls). The drawer is real content, always in the Tab order and
 *  read by screen readers; it is drawn only while the pointer or keyboard focus is on the window (window.css). */
export function pane(kind, hero, line, more = []) {
  const box = el("div", { className: `jv-pane jv-pane--${kind}` });
  box.append(hero);
  if (line) box.append(el("p", { className: "jv-pane__line", textContent: line, title: line }));
  const rest = more.filter(Boolean);
  if (rest.length) {
    const drawer = el("div", { className: "jv-more" }, { role: "group", "aria-label": "Why? Sources and details" });
    drawer.append(el("p", { className: "jv-more__kicker jv-kicker", textContent: "Why?" }, { "aria-hidden": "true" }), ...rest);
    box.append(drawer);
  }
  return box;
}

/** What the hub's Now panel rests on: the next thing (or the one flag), one line, the whole card in the drawer.
 *  → { hero, line } */
export function nowSummary(card, hide = new Set()) {
  const next = hide.has("next") ? null : card?.next_up, flag = hide.has("flag") ? null : card?.flag;
  if (next) return { hero: next.title, line: [next.when, next.where].filter(Boolean).join(" · ") };
  if (flag) return { hero: flag.text, line: "" };
  const day = card?.day;
  if (day?.total) return { hero: `${day.done} / ${day.total}`, line: "done today", number: true };  // no filler: the day's count is the fact
  return { hero: card ? "Nothing booked" : "Nothing on the card yet", line: card ? "The rest of the day is yours." : "Jarvis builds it when your day starts." };
}

/** → an Element for the window body. */
export function windowContent(win, s, now) {
  const kind = windowKind(win.type);  // a registered kind draws its own body
  if (kind) return kind.content(win, s, now);
  switch (win.type) {
    case "branch_card": {
      const branch = s.branches.find((b) => b.id === win.ref), card = s.cards[win.ref];
      if (!branch) return missing("That branch is no longer on the map.");
      // "Week 11 of 13 · on track; PPS 7 at question 7": the first part is the hero, the rest the one line
      const status = card?.status || "", lead = firstPart(status);
      return pane("title", title(lead || branch.name), lead ? status.slice(lead.length + 3) : status || branch.summary || "Nothing recorded here yet.",
        [el("jv-branch-card", { card, branch, facts: s.facts, now })]);
    }
    case "countdown": {
      const due = allDue(s).find((d) => d.id === win.ref);
      if (!due) return missing("That deadline is no longer on the list.");
      return pane("number", el("jv-big-number", { due, now }, { bare: "" }), `Due ${dueWords(due.due)}`, [
        words(due.title, "jv-more__lead"),
        due.progress != null ? words(`${Math.round(due.progress * 100)}% done`) : null,
        sources([due.source]),
      ]);
    }
    case "next_up": {
      const next = s.now_card?.next_up;
      if (!next) return missing("Nothing booked. The rest of the day is yours.");
      return pane("title", title(next.title), next.where || "", [sources([next.source])]);  // (the kicker row has the time)
    }
    case "timeline": {
      const items = s.day?.items || [], next = nextOnDay(s, now);
      const list = el("jv-timeline", { items, now }, { compact: true });
      if (!next) return pane("title", title(items.length ? "Nothing left today" : "Nothing booked"), "The rest of the day is yours.", items.length ? [list] : []);
      return pane("title", title(next.title), [nice(next.start), next.where].filter(Boolean).join(" · "), [list]);
    }
    case "file": {
      const file = s.files.find((f) => f.id === win.ref);
      if (!file) return missing("That file isn't available here.");
      // the picture comes with the push (window.thumb), else from the work thread on this file
      const thumb = file.thumb || win.thumb || s.threads?.find((t) => t.ref === file.id)?.thumb;
      const tile = el("jv-file-tile", { file }, { compact: "" });
      // media, large: a page is cropped to its top (the question he is on) in a wide frame
      if (thumb) return pane("media", el("jv-thumb", { thumb, className: "jv-pane__media" }, { ratio: "wide" }), "", [tile]);
      return pane("title", title(bare(file.name)), [FILE_KIND[file.kind] || "Document", file.page].filter(Boolean).join(" · "), [tile]);
    }
    case "fact": case "unsorted": {
      const fact = s.facts.find((f) => f.id === win.ref);
      if (!fact) return missing("That has been forgotten.");
      // a short heading sent with the window (window.data.heading) leads and the statement is the one line; without
      // one the statement itself leads, over where it came from
      const heading = win.data?.heading;
      const line = heading ? fact.statement : [fact.source?.label, fact.last_confirmed ? `confirmed ${shortDate(fact.last_confirmed)}` : ""].filter(Boolean).join(" · ");
      return pane("title", title(heading || fact.statement), line,
        [el("jv-fact-card", { fact, branches: win.type === "unsorted" ? s.branches : undefined }, win.type === "fact" ? { compact: "" } : {})]);
    }
    case "approval": {
      const approval = s.approvals.find((a) => a.id === win.ref);
      return approval ? el("jv-approval-card", { approval, now }, { clean: "" }) : missing("That has already been answered.");
    }
    case "timer": return pane("number", el("jv-big-number", {}, { bare: "", value: win.data?.value || "", unit: win.data?.unit || "" }), win.data?.sub || "");
    case "chart": {
      const d = win.data || {}, heading = d.heading || win.title;
      const chart = (attrs) => el("jv-mini-chart", { data: d.data || [], target: d.target }, { heading, type: d.type || "bar", unit: d.unit || "", ...attrs });
      return pane("chart", chart({ bare: "" }), d.unit ? `${heading} (${d.unit})` : heading, [chart({ numbers: "" })]);
    }
    default: {
      const d = win.data || {};
      return pane("title", title(d.heading || d.text || win.title || "Note"), d.heading ? d.text || "" : "");
    }
  }
}

function missing(text) { return pane("title", title(text), ""); }
