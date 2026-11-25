// The strip (V07, N8): Laptop A's small always-on-top bar (360 × 96). Nothing here animates, ever (C37), and
// nothing here makes a sound (no earcons are loaded at size=strip).
//   Row 1  a still orb (state by colour, `orbView()`: Standby when nobody is at the hub, the critical alert from
//          the Rail) and its word · on the right the Rail's worst glance shape + word and "N new" (things on
//          the Rail with a "since you looked" mark; a static cyan notch, never a red badge)
//   Row 2  what matters next: the critical thing, else what waits for his yes, else next up
//   Row 3  after game mode, one visual line: "While you played: Homework 1, Messages 2" (marks made while it
//          was on, by Rail slot). It stays until those marks are seen, and goes when the next game starts.
// Game mode (`settings.game_mode = on` or `now_card.moment = game`): nothing shows except a critical thing.
// Words match the status line ("Listening" when idle). Tier-2 things never show when others are present.
//
// When game mode started isn't in the contracts, so the strip notes it itself when it sees game mode come on
// and go off (`ui.gameSince` / `ui.gameEnded`, the UI-only slice; scenes set them). A strip opened while a game
// is already running counts from when it opened.
import { glance } from "../../components/glance/glance.js";
import { ALERT_WORDS, ORB_WORDS } from "../../components/orb/orb-parts.js";
import { GLANCE_WORD, SLOT_WORD, SLOTS, slotView, worstOf } from "../../components/rail/rail.js";
import { asDate, css, html, localIso } from "../../core/dom.js";
import { orbView } from "../../core/orbview.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { inGame } from "../../sounds/earcons.js";

css(import.meta.url);

const WORDS = { ...ORB_WORDS, idle: "Listening" };  // the same word the status line uses

/** What the strip shows, worked out from the store. Pure, so it can be tested without drawing. */
export function stripView(s = store.state) {
  const shared = !!s.presence?.others;
  const views = SLOTS.map((name) => slotView(name, s.rail, s.marks || {}, { shared }));
  const critical = views.flatMap((x) => x.items).find((i) => i.state === "critical") || null;
  const v = orbView(s);
  const state = s.settings?.muted && v.state !== "offline" ? "muted" : v.state;
  const alert = v.alert || (critical ? "crit" : null);
  const worst = worstOf(views.filter((x) => x.worst).map((x) => ({ state: x.worst })));
  return {
    game: inGame(s), state, alert, critical, worst,
    word: alert ? ALERT_WORDS[alert] : WORDS[state] || WORDS.idle,
    worstIn: worst ? views.filter((x) => x.worst === worst).map((x) => SLOT_WORD[x.name]) : [],
    fresh: views.reduce((n, x) => n + x.marked.length, 0),
    recap: inGame(s) ? [] : recapOf(s, shared),
  };
}

/** "While you played": marks made between ui.gameSince and ui.gameEnded, counted by the Rail slot of their
 *  thing (what Jarvis said counts under Jarvis). Seen marks are gone from `marks`, so they drop out by themselves. */
export function recapOf(s, shared = false) {
  const from = s.ui?.gameSince, to = s.ui?.gameEnded;
  if (!from || !to) return [];
  const a = asDate(from).getTime(), b = asDate(to).getTime();
  const during = (ref) => { const t = asDate(s.marks[ref]?.at).getTime(); return t >= a && t <= b; };
  return SLOTS.map((name) => [SLOT_WORD[name], slotView(name, s.rail, s.marks || {}, { shared }).marked.filter(during).length])
    .filter(([, n]) => n > 0);
}

/** Note when game mode comes on and goes off (once per change), on the hub clock. */
function trackGame(s) {
  const on = inGame(s), ui = s.ui || {};
  if (on && (!ui.gameSince || ui.gameEnded)) store.setUi({ gameSince: localIso(store.now()), gameEnded: null });
  else if (!on && ui.gameSince && !ui.gameEnded) store.setUi({ gameEnded: localIso(store.now()) });
}

class StripView extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<section class="jv-strip" aria-label="Jarvis"></section>`;
    this.box = this.firstElementChild;
    this.sig = null;
    this.stop = store.watch(["orb", "now_card", "settings", "approvals", "presence", "rail", "marks", "ui"], (s) => { trackGame(s); this.draw(s); });
  }
  disconnectedCallback() { this.stop?.(); }

  draw(s) {
    const v = stripView(s);
    const sig = JSON.stringify([v, s.now_card?.next_up, s.approvals.filter((a) => a.status === "pending").map((a) => a.title)]);
    if (sig === this.sig) return;
    this.sig = sig;
    const hidden = v.game && !v.critical;
    this.box.className = `jv-strip${hidden ? " jv-strip--hidden" : ""}${v.recap.length ? " jv-strip--recap" : ""}`;
    if (hidden) { this.box.innerHTML = String(html`<p class="jv-sr">Jarvis is hidden while game mode is on. Only something critical shows here.</p>`); return; }
    this.box.innerHTML = String(html`
      <jv-orb size="strip" state="${v.state}"></jv-orb>
      <p class="jv-strip__state">${v.word}</p>
      ${v.game ? "" : this.railBit(v)}
      <p class="jv-strip__next">${this.nextLine(s, v)}</p>
      ${v.recap.length ? html`<p class="jv-strip__recap">While you played: ${v.recap.map(([w, n]) => `${w} ${n}`).join(", ")}</p>` : ""}`);
    if (v.alert) this.box.querySelector("jv-orb").setAttribute("alert", v.alert);
  }

  /** The Rail at a glance: its worst state (shape + word) and how many things are new since he looked. */
  railBit(v) {
    const worst = v.critical ? null : v.worst;  // a critical thing is already named on the line below
    if (!worst && !v.fresh) return "";
    const said = [worst ? `Worst on the Rail: ${GLANCE_WORD[worst]} (${v.worstIn.join(", ")})` : "", v.fresh ? `${v.fresh} new since you looked` : ""];
    return html`<p class="jv-strip__rail" role="img" aria-label="${said.filter(Boolean).join(". ")}">
      ${worst ? glance(worst, { size: "rail", word: GLANCE_WORD[worst] }) : ""}
      ${v.fresh ? html`<span class="jv-strip__new"><span class="jv-strip__notch"></span>${v.fresh} new</span>` : ""}</p>`;
  }

  /** The one thing that matters next: critical first, then what waits for his yes, then next up. */
  nextLine(s, v) {
    if (v.critical) return html`${glance("critical", { size: "rail", word: GLANCE_WORD.critical })} <b>${v.critical.title}</b>${v.critical.detail ? html` · ${v.critical.detail}` : ""}`;
    const pending = s.approvals.filter((a) => a.status === "pending");
    if (pending.length && v.state === "waiting") return html`<b>${pending[0].title}</b>${pending.length > 1 ? ` and ${pending.length - 1} more` : ""}`;
    if (pending.length) return html`<b>${pending.length} waiting for your yes</b>`;
    const next = s.now_card?.next_up;
    return next ? html`<span class="jv-strip__label">Next</span> <b>${next.title}</b> · <span class="jv-num">${next.when}</span>` : "Nothing booked";
  }
}
if (!customElements.get("jv-view-strip")) customElements.define("jv-view-strip", StripView);

// ---- scenes (the demo day at 3:40 pm Monday) ----------------------------------------------------------------
const D = "2026-11-16";
const quiet = (s) => { s.approvals = []; s.rail.slots.yes = { items: [] }; };  // nothing waiting for a yes, anywhere
const overdue = (s) => {
  const pps = s.rail.slots.homework.items.find((i) => i.ref === "due-pps7");
  Object.assign(pps, { state: "critical", detail: "Overdue since Wed 8 pm" });
  s.rail.slots.homework.worst = "critical";
};
registerScene("strip", { path: "/strip", size: "strip", about: "Laptop A strip: listening, next up, the Rail's worst state and what's new", patch: quiet });
registerScene("strip-waiting", { path: "/strip", size: "strip", about: "Something waiting for a yes", patch: (s) => { s.orb = { state: "waiting", countdown_s: 7, window_s: 10 }; } });
registerScene("strip-muted", { path: "/strip", size: "strip", about: "Muted", patch: (s) => { quiet(s); s.settings.muted = true; s.orb = { state: "muted" }; } });
registerScene("strip-standby", { path: "/strip", size: "strip", about: "Nobody at the hub: Standby", patch: (s) => { quiet(s); s.presence = { here: false, others: false }; } });
registerScene("strip-critical", { path: "/strip", size: "strip", about: "Something critical: a red ring, Critical, and the thing named", patch: (s) => { quiet(s); overdue(s); } });
registerScene("strip-game", { path: "/strip", size: "strip", about: "Game mode: hidden", patch: (s) => { s.settings.game_mode = "on"; } });
registerScene("strip-game-critical", { path: "/strip", size: "strip", about: "Game mode with something critical: only that shows", patch: (s) => { quiet(s); overdue(s); s.settings.game_mode = "on"; } });
registerScene("strip-after-game", { path: "/strip", size: "strip", about: "After game mode: one still line of what came in while he played", patch: (s) => {
  quiet(s);
  s.ui = { ...(s.ui || {}), gameSince: `${D}T13:00:00`, gameEnded: `${D}T15:39:00` };
  s.rail.slots.messages.items.push({ ref: "msg-sam-lab", slot: "messages", kind: "message", title: "Sam · lab partners", at: `${D}T14:05:00` });
  s.marks = { ...s.marks, "msg-sam-lab": { what: "New: Sam asked about Thursday's lab", at: `${D}T14:05:00` } };
} });
