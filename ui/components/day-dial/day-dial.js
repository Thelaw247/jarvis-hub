// <jv-day-dial>: the day dial around the orb (HUD v2 §6.1; review-glance-feasibility SHOULD 1).
// A 12-hour clock face from an hour ago to 11 hours ahead, so it reads like a watch with no am/pm overlap:
//   12 ticks (longer at 12, 3, 6 and 9) · a 2 px "now" hand in --text
//   4 px arcs: upcoming --line-dim · next (and now) --cyan · done --cyan-hi · moved or missed dashed --text-3
//   due items: 9 px --warn diamonds (done: --cyan-hi) · overdue: --crit triangles (an overdue item older than
//   the face is pinned at its start, an hour ago, so it never drops off)
//   only the next item is labelled, 12 px, in short words: "4:00 · GE 122 · ENGR 1A10" or "4:00 · GE 122 review"
//   (course code + kind, the room only if it is a room code; up to two lines, never an ellipsis)
//   (`private`: no label, no titles)
//
//   .items  = state.day.dial[] (contracts/day.schema.json: ISO start/end, so it crosses midnight)
//   .now    = Date | ISO string; or the attribute `live`: the hub clock, redrawn once a minute
//   private = others may see the screen: shapes only, nothing personal in words
//
// Static on purpose (HUD v2 §7: the ambient screen's 8 running animations all belong to the orb): no CSS
// animation or transition; it redraws when its data changes and, with `live`, once a minute (never while the
// page is hidden). Drawn in pixels for its own size (a ResizeObserver redraws it when that changes), so strokes
// and the 9 px marks stay true at any orb size. Night adds a static bloom (a wide faint copy) behind lit arcs. In the orb it sits in `.dialSlot` at 2.5 R (slot="dial"),
// inside the motes (2.75–2.95 R); the label hangs outside the motes.
// role="img" with a one-line summary (`.summary`). Inside <jv-orb> (itself role="img") that name isn't read
// out, so a view that mounts the dial in the orb should also put `.summary` in text a screen reader reaches
// (`jv-day-dial-summary` { summary } fires whenever it changes, e.g. on the minute).
import { asDate, clockTime, css, esc, Jv } from "../../core/dom.js";
import { store } from "../../core/store.js";
import "./day-dial-scenes.js";

css(import.meta.url);

const MIN = 60_000;
export const SPAN_BEFORE = 60 * MIN;    // the face starts an hour ago …
export const SPAN_AFTER = 11 * 60 * MIN;  // … and runs 11 hours ahead: 12 hours, once round
const PAST = new Set(["done"]);
const OFF = new Set(["moved", "missed"]);

/** Degrees clockwise from 12 o'clock for a moment on a 12-hour face. */
export function clockAngle(t) {
  const d = asDate(t);
  return Math.round(((d.getHours() % 12) * 60 + d.getMinutes() + d.getSeconds() / 60) * 500) / 1000;  // 0.5° a minute
}

/** "4:00": the face's own time words (the face already says which half of the day it is). */
const faceTime = (d) => `${d.getHours() % 12 || 12}:${String(d.getMinutes()).padStart(2, "0")}`;

// The label's short words (HUD v2 §6.1: "4:00 · GE 122 · ENGR 1A10"): the course code plus what kind of thing
// it is, and the room only when it is a room code. Never cut with an ellipsis: the words are short by design.
const CODE = /\b([A-Z]{2,5}) ?(\d{2,3}[A-Z]?)\b/;
const KIND_WORDS = ["pre-lab", "review", "tutorial", "seminar", "midterm", "exam", "quiz", "lab", "lecture", "study"];
const ROOM = /^[A-Z]{2,5} ?\w+$/;
const SHORT_MAX = 22;  // characters: with the time and a room it stays within two 30ch lines

/** "Review GE 122 lecture 21" → "GE 122 review"; "CHEM 142 lab 4" → "CHEM 142 lab"; a class is just its code
 *  ("GE 122"); anything without a course code keeps its own first words ("PPS 7", "Read lab 5 handout"). */
export function shortTitle(item = {}) {
  const title = String(item.title || "").trim(), code = title.match(CODE);
  if (code) {
    const lower = title.toLowerCase();
    let word = KIND_WORDS.find((w) => new RegExp(`(^|[^a-z-])${w}([^a-z-]|$)`).test(lower)) || "";
    if (item.kind === "class" && word === "lecture") word = "";  // a class is the code (and its room)
    if (!word && (item.kind === "lab" || item.kind === "exam")) word = item.kind;
    return [`${code[1]} ${code[2]}`, word].filter(Boolean).join(" ");
  }
  const head = title.split(" · ")[0];
  if (head.length <= SHORT_MAX) return head;
  const cut = head.slice(0, SHORT_MAX + 1).replace(/\s+\S*$/, "").replace(/(\s+(and|the|with|of|to|a|for|in|on|at))+$/i, "");
  return cut || head.slice(0, SHORT_MAX);
}
/** The room, only when it is a room code ("ENGR 1A10"; not "Your desk"). */
export const roomCode = (where) => (where && ROOM.test(String(where).trim()) ? String(where).trim() : "");

/** Everything the dial draws, worked out from the data alone (pure: the tests call it).
 *  → { from, to, hand, arcs[{ id, kind, state, look, a0, a1 }], marks[{ id, shape, look, angle, pinned }],
 *      next?{ id, angle, label, words }, summary } */
export function dialModel(items = [], now = new Date(), { private: hide = false } = {}) {
  const n = asDate(now), from = new Date(n - SPAN_BEFORE), to = new Date(+n + SPAN_AFTER);
  const list = (Array.isArray(items) ? items : []).filter((i) => i && i.start && !Number.isNaN(+asDate(i.start)))
    .map((i) => ({ ...i, s: asDate(i.start), e: i.end ? asDate(i.end) : null }))
    .sort((a, b) => a.s - b.s);
  const isMark = (i) => i.kind === "due" || i.state === "overdue";
  // under way: what the server calls now, or an arc around the hand that it hasn't called done, moved or missed
  const underway = (i) => !isMark(i) && (i.state === "now" || (!PAST.has(i.state) && !OFF.has(i.state) && i.s <= n && (i.e || i.s) > n));

  // the next thing: what the server calls next, or else the first arc still ahead
  const ahead = list.filter((i) => !isMark(i) && !PAST.has(i.state) && !OFF.has(i.state) && i.state !== "now" && i.s >= n && i.s < to);
  const next = list.find((i) => i.state === "next" && !isMark(i) && (i.e || i.s) > from && i.s < to) || ahead[0] || null;

  const arcs = [], marks = [];
  for (const i of list) {
    if (isMark(i)) {
      const overdue = i.state === "overdue";
      if (i.s >= to || (!overdue && i.s < from)) continue;  // off the face (an overdue one stays, pinned)
      const pinned = i.s < from;
      marks.push({ id: i.id, title: i.title, shape: overdue ? "triangle" : "diamond", look: overdue ? "overdue" : i.state === "done" ? "done" : "due", angle: clockAngle(pinned ? from : i.s), pinned, at: i.s });
      continue;
    }
    const end = i.e && i.e > i.s ? i.e : new Date(+i.s + 15 * MIN);  // an arc with no end: a short quarter hour
    const s = i.s < from ? from : i.s, e = end > to ? to : end;
    if (e <= s) continue;
    const look = PAST.has(i.state) ? "done" : OFF.has(i.state) ? "off" : i === next || underway(i) ? "next" : "upcoming";
    const a0 = clockAngle(s);
    arcs.push({ id: i.id, kind: i.kind, state: i.state || "upcoming", look, a0, a1: a0 + Math.round(((e - s) / MIN) * 500) / 1000 });
  }

  let label = null;
  if (next && next.s < to) {
    const at = next.s < from ? from : next.s;
    const words = [faceTime(next.s), shortTitle(next), roomCode(next.where)].filter(Boolean);
    label = { id: next.id, angle: clockAngle(at), label: hide ? null : words.join(" · "), words };
  }
  const current = list.find(underway) || null;
  return { from, to, hand: clockAngle(n), arcs, marks, next: label, summary: summarise(list, next, current, n, from, to, hide, isMark) };
}

/** One line for screen readers: what's next, then counts. */
function summarise(list, next, current, now, from, to, hide, isMark) {
  const onFace = list.filter((i) => (isMark(i) ? (i.state === "overdue" || i.s >= from) && i.s < to : (i.e || i.s) > from && i.s < to));
  const done = onFace.filter((i) => !isMark(i) && PAST.has(i.state)).length;
  const later = onFace.filter((i) => !isMark(i) && i !== next && i !== current && !PAST.has(i.state) && !OFF.has(i.state) && i.s > (next?.s || now)).length;
  const due = onFace.filter((i) => i.kind === "due" && i.state !== "overdue" && i.state !== "done").length;
  const overdue = onFace.filter((i) => i.state === "overdue").length;
  const moved = onFace.filter((i) => !isMark(i) && OFF.has(i.state)).length;
  const parts = [`Day dial, ${clockTime(from)} to ${clockTime(to)}.`];
  if (current) parts.push(hide ? `Under way until ${clockTime(current.e || current.s)}.` : `Now: ${current.title}, until ${clockTime(current.e || current.s)}.`);
  if (next) parts.push(hide ? `Next at ${clockTime(next.s)}.` : `Next: ${next.title} at ${clockTime(next.s)}${next.where ? `, ${next.where}` : ""}.`);
  else if (current) { /* said above */ }
  else if (done && !later && !due && !overdue) parts.push("All done; nothing else booked.");
  else if (!onFace.length) parts.push("Nothing booked.");
  const counts = [done && `${done} done`, later && `${later} more later`, due && `${due} due`, overdue && `${overdue} overdue`, moved && `${moved} moved or missed`].filter(Boolean);
  if (counts.length && !(done && !later && !due && !overdue && !next && !moved && !current)) parts.push(`${counts.join(", ")}.`);
  return parts.join(" ");
}

// ---- drawing --------------------------------------------------------------------------------------------
const f = (v) => Math.round(v * 100) / 100;
const pt = (c, r, deg) => { const a = (deg * Math.PI) / 180; return [f(c + r * Math.sin(a)), f(c - r * Math.cos(a))]; };
function arcPath(c, r, a0, a1) {
  const sweep = a1 - a0, gap = sweep > 6 ? 1.2 : 0;  // a hair of space between touching arcs
  const [x0, y0] = pt(c, r, a0 + gap), [x1, y1] = pt(c, r, a1 - gap);
  return `M${x0} ${y0}A${f(r)} ${f(r)} 0 ${sweep - 2 * gap > 180 ? 1 : 0} 1 ${x1} ${y1}`;
}
function markPath(c, r, m) {
  const [x, y] = pt(c, r, m.angle);
  if (m.shape === "diamond") return `M${x} ${f(y - 4.5)}L${f(x + 4.5)} ${y}L${x} ${f(y + 4.5)}L${f(x - 4.5)} ${y}Z`;
  return `M${x} ${f(y - 5)}L${f(x + 5.2)} ${f(y + 4)}L${f(x - 5.2)} ${f(y + 4)}Z`;  // a triangle, point up, ~10 px
}

class DayDial extends Jv {
  static props = ["items", "now"];
  static attrs = ["live", "private"];

  setup() {
    this.setAttribute("role", "img");
    this._ro = "ResizeObserver" in window ? new ResizeObserver(() => { if (this.offsetWidth !== this._w) this.update(); }) : null;
    this._onVisible = () => { if (!document.hidden && this._stale) { this._stale = false; this.update(); } };
  }
  connectedCallback() {
    super.connectedCallback();
    this._ro?.observe(this);
    document.addEventListener("visibilitychange", this._onVisible);
  }
  teardown() {
    clearTimeout(this._tick);
    this._ro?.disconnect();
    document.removeEventListener("visibilitychange", this._onVisible);
  }

  time() { return this.hasAttribute("live") || this.now == null ? store.now() : asDate(this.now); }

  /** The model it shows now (for views that want its words, e.g. a screen-reader line outside the orb). */
  get model() { return dialModel(this.items || [], this.time(), { private: this.hasAttribute("private") }); }
  get summary() { return this.getAttribute("aria-label") || this.model.summary; }

  /** With `live`: one redraw at the start of the next minute (none while the page is hidden). */
  schedule(now) {
    clearTimeout(this._tick);
    if (!this.hasAttribute("live") || !this.isConnected) return;
    const wait = MIN - (now.getSeconds() * 1000 + now.getMilliseconds()) + 20;
    this._tick = setTimeout(() => { if (document.hidden) this._stale = true; else this.update(); }, wait);
  }

  render() {
    const now = this.time(), m = dialModel(this.items || [], now, { private: this.hasAttribute("private") });
    if (this.getAttribute("aria-label") !== m.summary) { this.setAttribute("aria-label", m.summary); this.emit("jv-day-dial-summary", { summary: m.summary }); }
    this.schedule(now);
    const w = this.offsetWidth;
    this._w = w;
    if (!w) { this.innerHTML = ""; this._sig = null; return null; }  // drawn once it has a size (the observer calls back)
    const sig = JSON.stringify([w, m.hand.toFixed(1), m.arcs, m.marks, m.next]);
    if (sig === this._sig) return null;  // nothing on the face changed this minute
    this._sig = sig;
    const c = w / 2, r = w / 2;
    const ticks = Array.from({ length: 12 }, (_, k) => {
      const long = k % 3 === 0, [x0, y0] = pt(c, r - 3, k * 30), [x1, y1] = pt(c, r - (long ? 12 : 7), k * 30);
      return `M${x0} ${y0}L${x1} ${y1}`;
    }).join("");
    const byLook = (look) => m.arcs.filter((a) => a.look === look).map((a) => arcPath(c, r, a.a0, a.a1)).join("");
    const [hx0, hy0] = pt(c, r - 16, m.hand), [hx1, hy1] = pt(c, r + 8, m.hand);
    let label = "";
    if (m.next) {
      const [lx0, ly0] = pt(c, r + 4, m.next.angle), [lx1, ly1] = pt(c, r * 1.075, m.next.angle);
      const [x, y] = pt(c, r * 1.25, m.next.angle), a = (m.next.angle * Math.PI) / 180;
      const tx = f(-50 + 50 * Math.sin(a)), ty = f(-50 - 50 * Math.cos(a));
      const align = Math.sin(a) > 0.3 ? "left" : Math.sin(a) < -0.3 ? "right" : "center";  // two lines hug the dial
      label = `<path class="jv-day-dial__leader" d="M${lx0} ${ly0}L${lx1} ${ly1}"/>`;
      if (m.next.label) {
        const [time, ...rest] = m.next.words;
        // each part stays whole; the label breaks only between parts (two short lines at most, never an ellipsis)
        this._label = `<p class="jv-day-dial__label" style="left:${x}px;top:${y}px;transform:translate(${tx}%,${ty}%);text-align:${align}" aria-hidden="true"><span class="jv-day-dial__part jv-day-dial__time">${esc(time)}</span>${rest.map((t) => ` <span class="jv-day-dial__part">· ${esc(t)}</span>`).join("")}</p>`;
      } else this._label = "";
    } else this._label = "";
    const svg = `<svg class="jv-day-dial__svg" viewBox="0 0 ${f(w)} ${f(w)}" aria-hidden="true" focusable="false">
      <circle class="jv-day-dial__face" cx="${f(c)}" cy="${f(c)}" r="${f(r)}"/>
      <path class="jv-day-dial__ticks" d="${ticks}"/>
      ${["done", "next"].map((look) => { const d = byLook(look); return d ? `<path class="jv-day-dial__bloom jv-day-dial__bloom--${look}" d="${d}"/>` : ""; }).join("")}
      ${["upcoming", "off", "done", "next"].map((look) => { const d = byLook(look); return d ? `<path class="jv-day-dial__arc jv-day-dial__arc--${look}" d="${d}"/>` : ""; }).join("")}
      ${label}
      <path class="jv-day-dial__hand" d="M${hx0} ${hy0}L${hx1} ${hy1}"/>
      ${m.marks.map((k) => `<path class="jv-day-dial__mark jv-day-dial__mark--${k.look}" d="${markPath(c, r, k)}"/>`).join("")}
    </svg>`;
    return { toString: () => svg + this._label };
  }
}
DayDial.define("jv-day-dial");
