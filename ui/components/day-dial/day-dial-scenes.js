// Scenes for the day dial: every state side by side (?scene=component:day-dial[&state=<slug>]) and the dial on
// the standby orb (?scene=day-dial-orb[&state=<slug>]). Times are fixed, so screenshots never change.
import { el, params, registerGallery, registerScene } from "../../core/scenes.js";

const D = "2026-11-16";
const at = (t, day = D) => `${day}T${t}:00`;

/** The states, each with its own clock and arcs (contract shape: day.dial[]). */
export const DIAL_SAMPLES = {
  afternoon: {
    label: "Afternoon: done, next, upcoming, due tonight", now: at("15:40"),
    items: [
      { id: "dial-ge", kind: "class", start: at("10:00"), end: at("11:20"), title: "GE 122 lecture 21", where: "ENGR 1A10", state: "done" },
      { id: "dial-chem", kind: "lab", start: at("13:30"), end: at("15:20"), title: "CHEM 142 lab 4", where: "Thorvaldson 173", state: "done" },
      { id: "dial-review", kind: "block", start: at("16:00"), end: at("16:45"), title: "GE 122 review", where: "Your desk", state: "next" },
      { id: "dial-pps", kind: "block", start: at("19:00"), end: at("20:30"), title: "PPS 7 · Q7 to 12", where: "Your desk", state: "upcoming" },
      { id: "dial-webwork", kind: "due", start: at("23:59"), title: "WeBWorK 9", state: "upcoming" },
    ],
  },
  midnight: {
    label: "Crossing midnight", now: at("22:30"),
    items: [
      { id: "dial-pps", kind: "block", start: at("21:00"), end: at("22:15"), title: "PPS 7 · Q7 to 12", where: "Your desk", state: "done" },
      { id: "dial-read", kind: "block", start: at("23:00"), end: at("00:15", "2026-11-17"), title: "Read lab 5 handout", where: "Your desk", state: "next" },
      { id: "dial-webwork", kind: "due", start: at("23:59"), title: "WeBWorK 9", state: "upcoming" },
      { id: "dial-math", kind: "class", start: at("08:30", "2026-11-17"), end: at("09:20", "2026-11-17"), title: "MATH 133", where: "ARTS 101", state: "upcoming" },
    ],
  },
  overdue: {
    label: "Overdue: one older than the face (pinned), one inside it", now: at("15:40"),
    items: [
      { id: "dial-chem", kind: "lab", start: at("13:30"), end: at("15:20"), title: "CHEM 142 lab 4", where: "Thorvaldson 173", state: "done" },
      { id: "dial-quiz", kind: "due", start: at("12:00"), title: "Pre-lab quiz", state: "overdue" },
      { id: "dial-memo", kind: "due", start: at("15:00"), title: "Design memo 2", state: "overdue" },
      { id: "dial-review", kind: "block", start: at("16:00"), end: at("16:45"), title: "GE 122 review", where: "Your desk", state: "next" },
      { id: "dial-lab4", kind: "due", start: at("17:00"), title: "Lab report 4", state: "upcoming" },
    ],
  },
  "all-done": {
    label: "All done", now: at("21:10"),
    items: [
      { id: "dial-pps", kind: "block", start: at("19:00"), end: at("20:30"), title: "PPS 7 · Q7 to 12", where: "Your desk", state: "done" },
      { id: "dial-webwork", kind: "due", start: at("20:45"), title: "WeBWorK 9", state: "done" },
    ],
  },
  moved: {
    label: "Moved and missed (dashed)", now: at("09:10"),
    items: [
      { id: "dial-chemrev", kind: "block", start: at("08:00"), end: at("08:30"), title: "CHEM 142 pre-lab review", state: "moved" },
      { id: "dial-math", kind: "class", start: at("08:30"), end: at("09:20"), title: "MATH 133", where: "ARTS 101", state: "now" },
      { id: "dial-ge", kind: "class", start: at("10:00"), end: at("11:20"), title: "GE 122", where: "ENGR 1A10", state: "next" },
      { id: "dial-gym", kind: "own", start: at("17:00"), end: at("18:00"), title: "Gym", state: "missed" },
    ],
  },
  empty: { label: "Nothing booked", now: at("15:40"), items: [] },
};

const make = (key, extra = {}) => el("jv-day-dial", { items: DIAL_SAMPLES[key].items, now: DIAL_SAMPLES[key].now }, extra);
const cell = (node) => { const box = el("div", { className: "jv-day-dial-cell" }); box.append(node); return box; };

registerGallery("day-dial", [
  ...Object.keys(DIAL_SAMPLES).map((key) => ({ label: DIAL_SAMPLES[key].label, build: () => cell(make(key)) })),
  { label: "Others present: shapes, no words", build: () => cell(make("afternoon", { private: "" })) },
], { about: "A 12-hour face from an hour ago to 11 hours ahead. Static: it redraws once a minute.", columns: "460px" });

// The dial where it lives: around the standby orb (the ambient screen adds the clock and the rest).
registerScene("day-dial-orb", {
  about: "The day dial on the standby orb (&state=afternoon|midnight|overdue|all-done|moved|empty)",
  patch: (s) => { const k = DIAL_SAMPLES[params.get("state")] ? params.get("state") : "afternoon"; s.now = DIAL_SAMPLES[k].now; s.ui = { ...s.ui, ambient: false }; },
  render(stage) {
    const key = DIAL_SAMPLES[params.get("state")] ? params.get("state") : "afternoon";
    const wrap = el("div", { className: "jv-day-dial-scene" });
    const orb = el("jv-orb", { orb: { state: "idle" } }, { state: "standby", size: "centre", dial: "" });  // the orb draws the dial slot only when asked (HUD v3 §14)
    orb.style.cssText = "width:min(420px,52vh);height:min(420px,52vh)";
    const dial = make(key, { slot: "dial" });
    orb.append(dial);
    wrap.append(orb);
    stage.replaceChildren(wrap);
  },
});
