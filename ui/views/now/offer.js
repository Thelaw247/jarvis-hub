// The return offer on the home screen ("the hidden trick": HUD v2 §6.4, §9.5, §10; v3 §14 keeps resume points).
// HUD v3 emptied the home, so the offer is never a permanent line. When Jarvis has one (a piece of work he left
// a short while ago), it shows as ONE small glass card under the orb, only while the offer is live:
//   - spoken offers are the shell's caption above the icon row; while anyone is speaking the card steps aside
//   - a tap on it is his yes: the thread opens at his spot (a PDF in the reader, already at the question)
//   - "Not now": it goes, without a word; it stays on the Homework icon and isn't offered again until something
//     changes (he leaves and comes back, or the spot moves)
//   - ignored for IGNORE_MS, or he does something else (opens an icon, another view): that's the answer; the
//     card goes and the Homework icon keeps it
//   - mornings lead with today, others present see nothing personal, tier-2 branches never show here
// Answers live in store.ui.offers = { <thread id>: { at: <the resume point's time>, how } } for this page load:
// a new resume point (he worked on it again) is a new offer. Declines are never mentioned or shown as misses.
import { bridge } from "../../core/bridge.js";
import { asDate, css, html } from "../../core/dom.js";
import { orbView } from "../../core/orbview.js";
import { router } from "../../core/router.js";
import { store } from "../../core/store.js";
import { accepted } from "../reader/reader.js";

css(import.meta.url);

const HOUR = 3_600_000;
export const SHORT_BREAK_H = 3;   // a thread touched within this long: Jarvis offers to pick it up
export const MIN_AWAY_MS = 120_000;  // not the moment he puts it down: only once he has been off it a little
export const IGNORE_MS = 45_000;  // shown this long with no answer: it folds into the Homework icon
const MORNING_FROM = 4, MORNING_TO = 12;  // 4 am to noon, before any work today: mornings lead with today
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const BUSY = new Set(["speaking", "listening", "thinking", "waiting"]);  // an exchange is on: the caption has the floor

/** "Today", "Yesterday", "Tue", or "12 Nov": when he stopped, as the resume card says it. */
export function dayWord(at, now) {
  const a = asDate(at), n = asDate(now);
  const days = Math.round((new Date(n.getFullYear(), n.getMonth(), n.getDate()) - new Date(a.getFullYear(), a.getMonth(), a.getDate())) / 864e5);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : days < 7 ? DAYS[a.getDay()] : `${a.getDate()} ${a.toLocaleString("en-CA", { month: "short" })}`;
}

/** Where the offer takes him: a PDF thread to the reader (/read/<thread>), anything else to its branch. */
export const resumePath = (t) => (t.kind === "pdf" ? `/read/${t.id}` : t.branch ? `/life/${t.branch}` : "/life");

/** The live return offer, or null (pure; the tests call it). → { thread, words, to } */
export function resumeOffer(s, now = store.now()) {
  if (s.presence?.others) return null;
  const n = asDate(now), hidden = new Set((s.branches || []).filter((b) => b.tier === 2).map((b) => b.id));
  const threads = (s.threads || []).filter((t) => t.state !== "done" && !hidden.has(t.branch) && t.resume?.at);
  const touched = (t) => asDate(t.resume.at);
  const startOfDay = new Date(n.getFullYear(), n.getMonth(), n.getDate(), MORNING_FROM);
  const workedToday = threads.some((t) => touched(t) >= startOfDay && touched(t) <= n);
  if (n.getHours() >= MORNING_FROM && n.getHours() < MORNING_TO && !workedToday) return null;
  const thread = threads.filter((t) => n - touched(t) >= MIN_AWAY_MS && n - touched(t) <= SHORT_BREAK_H * HOUR).sort((a, b) => touched(b) - touched(a))[0];
  if (!thread || s.ui?.offers?.[thread.id]?.at === thread.resume.at) return null;  // answered, declined or let go
  return { thread, words: [thread.title, thread.resume.label, dayWord(thread.resume.at, n)].filter(Boolean).join(" · "), to: resumePath(thread) };
}

/** Note his answer to the offer for `thread` (accept · notnow · ignored · acted). */
function answer(thread, how) {
  store.setUi({ offers: { ...(store.state.ui.offers || {}), [thread.id]: { at: thread.resume.at, how } } });
}

/** He left and came back (the screen woke): what he let go or put off may be offered again; a yes stays a yes. */
export function cameBack() {
  const offers = store.state.ui.offers || {}, kept = Object.fromEntries(Object.entries(offers).filter(([, o]) => o.how === "accept"));
  if (Object.keys(kept).length !== Object.keys(offers).length) store.setUi({ offers: kept });
}

/** The card under the orb. One per home view; draw() on every store change, stop() when the view goes. */
export class OfferCard {
  /** Draw (or remove) the card inside the home's centre (`.jv-amb`). */
  draw(centre, s = store.state) {
    const offer = centre ? resumeOffer(s) : null;
    const show = !!offer && !BUSY.has(orbView(s).state);
    let card = centre?.querySelector(".jv-amb__offer");
    if (!show) { card?.remove(); this.rest(); if (!offer) this.thread = null; return; }
    const { thread, words, to } = offer, key = `${thread.id}|${thread.resume.at}|${words}`;
    if (!card || card.dataset.key !== key) {
      card?.remove();
      card = document.createElement("div");
      card.className = "jv-amb__offer"; card.dataset.key = key;
      card.setAttribute("role", "group"); card.setAttribute("aria-label", "Where you stopped");
      card.innerHTML = String(html`<span class="jv-amb__offer-ghost" aria-hidden="true"></span>
        <a class="jv-amb__offer-go" href="#${to}" data-resume="${thread.id}" aria-label="Carry on: ${words}"><jv-thumb size="small" class="jv-amb__offer-thumb"></jv-thumb><span class="jv-amb__offer-text"><span class="jv-amb__offer-kick">Carry on</span><span class="jv-amb__offer-where">${words}</span></span></a>
        <button type="button" class="jv-amb__offer-no">Not now</button>`);
      const thumb = card.querySelector("jv-thumb");
      thumb.thumb = thread.thumb; thumb.setAttribute("text", thread.title);
      card.querySelector(".jv-amb__offer-go").addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        answer(thread, "accept");
        if (thread.kind === "pdf") { accepted(thread.id); bridge.act("resume_accept", thread.id); }  // his tap is the yes: no second card
        router.go(to);
      });
      card.querySelector(".jv-amb__offer-no").addEventListener("click", (e) => { e.stopPropagation(); answer(thread, "notnow"); });
      centre.append(card);
    }
    this.thread = thread;
    // unanswered while he is here and awake: after a while it folds into the Homework icon
    if (s.ui?.ambient) this.rest();
    else if (!this.timer) this.timer = setTimeout(() => { this.timer = null; if (this.thread) answer(this.thread, "ignored"); }, IGNORE_MS);
  }
  rest() { clearTimeout(this.timer); this.timer = null; }
  /** He did something else while the card was up (opened an icon): that's the answer. */
  acted() { if (this.thread) answer(this.thread, "acted"); }
  /** The view is going. If the card was up and he went somewhere else, that was his answer. */
  stop() {
    this.rest();
    const offer = this.thread && resumeOffer(store.state);
    if (offer && offer.thread.id === this.thread.id) answer(offer.thread, "acted");
    this.thread = null;
  }
}
