// The home screen's centre (HUD v3 §14 decisions 1, 6, 7: closer to Huw). Drawn by now.js into
// `.jv-now__ambient` on the calm home (windows go to the Stage) and, "On the hub", while the Now view rests.
// Nothing else is on it: the icon row (the Rail, with the page dots) and the status word are the shell's.
//   - awake: the orb alone in the middle of the grid, white rings (P1's v3 orb); no clock, no date, no "what's
//     next" line, no day dial around it (what's next is one tap away in Today and on the Today icon's badge)
//   - resting (store.ui.ambient, or nobody here): standby, Huw's standby screen: the small translucent
//     particle sphere with a small mono clock and a tiny tracked date under it
//   - Jarvis's spoken line is the shell's caption above the icon row, only while he says it
//   - Daylight keeps a small day plant; Night has no plant or decoration
// Others present: nothing personal is on this screen any more (the clock and date are not personal; the plant
// steps aside). The orb keeps the same box and centre in both states, so waking never moves it.
// The structure keeps now.js's contract: `.jv-now__centre > jv-orb` is the orb that docks (slideOrbToDock()),
// and everything else hides while it slides.
import { css } from "../../core/dom.js";
import { orbView, stillAwake } from "../../core/orbview.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

/** What the home's orb shows (pure; the tests call it): standby (the sphere, with the clock under it) when it
 *  has nothing else to say and the screen rests or nobody is here; otherwise the orb's own state. */
export function homeLook(s, view = orbView(s)) {
  const standby = view.state === "standby" || (view.state === "idle" && !!s.ui?.ambient);
  return { state: standby ? "standby" : view.state, clock: standby };
}

/** Draw (or update) the home's centre into `root` (now.js's `.jv-now__ambient`). */
export function drawAmbient(root, s = store.state) {
  if (!root.querySelector(".jv-amb")) {
    root.innerHTML = `<div class="jv-now__centre jv-amb">
        <jv-orb size="centre" class="jv-amb__orb"></jv-orb>
        <div class="jv-amb__time" hidden><jv-clock live small class="jv-amb__clock"></jv-clock></div>
        <p class="jv-amb__next" hidden></p>
      </div>
      <jv-plant kind="day" class="jv-now__plant jv-amb__plant"></jv-plant>`;
  }
  const $ = (sel) => root.querySelector(sel);
  const others = !!s.presence?.others;

  // the orb: standby while resting with nothing else to say, else what the store says
  const orb = $(".jv-amb__orb"), view = orbView(s);
  let look = homeLook(s, view);
  // after a turn the rings stay out a moment before going back into the sphere (not the instant he stops)
  if (stillAwake(s.orb?.state || "idle", "home", () => drawAmbient(root, store.state)) && look.state === "standby"
      && view.state !== "standby") look = { state: "idle", clock: false };
  if (view.wake) orb.setAttribute("wake", view.wake); else orb.removeAttribute("wake");
  if (view.alert) orb.setAttribute("alert", view.alert); else orb.removeAttribute("alert");
  if (orb.getAttribute("state") !== look.state) orb.setAttribute("state", look.state);
  orb.orb = s.orb;

  // the small clock and the tiny date: only under the standby sphere
  const time = $(".jv-amb__time");
  if (time.hidden === look.clock) time.hidden = !look.clock;
  root.toggleAttribute("data-standby", look.clock);

  // one quiet line for what's next (v0.18.0): on the one-window hub this is where the Now card's headline lives
  // while nothing is up. Not on the Stage's calm home (the Stage says it), not when others are in the room.
  const next = $(".jv-amb__next"), up = s.now_card?.next_up;
  const line = up && !others && s.settings?.stage !== "window" ? ["Next", up.title, up.when, up.where].filter(Boolean).join(" · ") : "";
  if (next.textContent !== line) next.textContent = line;
  next.hidden = !line;

  // Daylight keeps a small day plant (Night hides it in CSS: no decoration on the Night screen)
  const plant = $("jv-plant"), day = s.now_card?.day;
  plant.hidden = s.settings?.plants === false || !day || others;
  if (day) Object.assign(plant, { done: day.done, total: day.total });
}

// ---- scenes ----------------------------------------------------------------------------------------------
// now-ambient (now.js) is the afternoon at the fixture's clock; these add the other moments of the screen.
registerScene("now-ambient-others", { path: "/now", about: "Standby with others present: the sphere and the clock, nothing personal anywhere (tier-2 things off the icon row)", patch: (s) => {
  s.ui = { ambient: true };
  s.presence = { here: true, others: true };
} });
registerScene("now-ambient-midnight", { path: "/now", about: "Standby late at night: the small clock says 10:30 pm", patch: (s) => {
  s.ui = { ambient: true }; s.approvals = []; s.caption = null;
  s.now = "2026-11-16T22:30:00";
} });
registerScene("now-ambient-caption", { path: "/now", about: "Resting, and Jarvis speaks: the rings come back and his line shows above the icon row while he says it", patch: (s) => {
  s.ui = { ambient: true };
  s.orb = { state: "speaking", level: 0.6 };
  s.caption = { text: "That's PPS 7 to question eight. First up tomorrow: MATH 133 at 8:30.", source: { kind: "jarvis", label: "Jarvis" }, ttl_ms: 600000 };
} });
