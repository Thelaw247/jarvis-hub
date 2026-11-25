// Scenes for the Core orb: every state at full, laptop and strip sizes (?scene=orb-<state>[&size=laptop]),
// and the side-by-side gallery (?scene=component:orb). Extra address options for looking at motion:
//   &motion=full&freeze=<ms>   let it run that long, then hold every animation still (screenshots of a beat)
import { el, params, registerGallery, registerScene } from "../../core/scenes.js";
import { ALERT_WORDS, ORB_WORDS } from "./orb-parts.js";

const ORB = {  // what the orb_state contract would carry for each look
  standby: { state: "idle" }, idle: { state: "idle" }, listening: { state: "listening", level: 0.7 },
  thinking: { state: "thinking" }, speaking: { state: "speaking", level: 0.65 },
  waiting: { state: "waiting", countdown_s: 7, window_s: 10 }, muted: { state: "muted" },
  offline: { state: "offline", message: "Can't reach the hub. It will reconnect on its own." },
};
const LOOKS = [
  ["standby", "standby"], ["idle", "idle"], ["listening", "listening"], ["thinking", "thinking"], ["speaking", "speaking"],
  ["waiting", "waiting"], ["alert-warn", "idle", "warn"], ["alert-crit", "idle", "crit"], ["muted", "muted"], ["offline", "offline"],
];
const wordOf = (state, alert) => (alert ? ALERT_WORDS[alert] : ORB_WORDS[state]);
const make = (state, size, alert, extra = {}) =>
  el("jv-orb", { orb: { ...(ORB[state] || ORB.idle) } }, { state, size, ...(alert ? { alert } : {}), ...extra });

/** Hold every animation still after `ms` (only with ?freeze=), so a screenshot can show a moving beat. */
function freezeLater() {
  const ms = Number(params.get("freeze"));
  if (!Number.isFinite(ms) || !params.has("freeze")) return;
  setTimeout(() => document.getAnimations().forEach((a) => a.pause()), ms);
}

function stageWith(stage, orb, caption, state) {
  const wrap = el("div", { className: "jv-orb-scene" });
  const cap = el("p", { className: "jv-kicker jv-orb-scene__cap", textContent: caption });
  wrap.append(orb, cap);
  if (state === "standby") {  // the host puts the small clock and date under the standby sphere (HUD v3 §14)
    const clock = el("jv-clock", {}, { live: "", small: "" });
    wrap.insertBefore(clock, cap);
  }
  stage.replaceChildren(wrap);
  freezeLater();
}

for (const [name, state, alert] of LOOKS) {
  registerScene(`orb-${name}`, {
    about: `The Core orb: ${wordOf(state, alert)}`,
    patch: (s) => { s.orb = { ...(ORB[state] || ORB.idle) }; s.ui = { ...s.ui, ambient: false }; },
    render(stage) {
      // the scene's caption: its name, then the word the orb says, unless they are the same word ("speaking")
      const label = name.replace("-", " "), word = wordOf(state, alert);
      stageWith(stage, make(state, "centre", alert), label === word.toLowerCase() ? word : `${label} // ${word}`, state);
    },
  });
}

// The wake beats: the full tilt-snap (first wake of the day or after ≥ 4 h) and the ordinary 250 ms tighten.
for (const [name, wake] of [["wake", "full"], ["tighten", "tighten"]]) {
  registerScene(`orb-${name}`, {
    about: wake === "full" ? "First wake of the day: rings tilted on a diagonal axle snap flat (1.2 s)" : "Every other wake: the dotted ring tightens (250 ms)",
    patch: (s) => { s.orb = { state: "listening", level: 0.7 }; },
    render(stage) {
      const orb = make("idle", "centre", "", { wake });
      stageWith(stage, orb, `wake // ${wake}`, "idle");
      requestAnimationFrame(() => { orb.orb = { ...ORB.listening }; orb.setAttribute("state", "listening"); });
    },
  });
}

// Docking: outer layers retract, then the orb slides into the corner as mini rings.
registerScene("orb-docked", {
  about: "Docked: the orb slides to the bottom-right and keeps its mini rings",
  patch: (s) => { s.orb = { state: "speaking", level: 0.6 }; },
  render(stage) {
    const orb = make("speaking", "centre", "", { "dock-to": ".jv-orb-scene" });
    stageWith(stage, orb, "docked // mini rings", "speaking");
    requestAnimationFrame(() => requestAnimationFrame(() => orb.setAttribute("docked", "")));
  },
});

// Docked while he listens: white rings only (no blue), the thin white energy ring following his voice.
registerScene("orb-docked-listening", {
  about: "Docked among windows while listening: white rings only, no blue",
  patch: (s) => { s.orb = { state: "listening", level: 0.7 }; },
  render(stage) {
    const orb = make("listening", "centre", "", { "dock-to": ".jv-orb-scene" });
    stageWith(stage, orb, "docked // listening", "listening");
    requestAnimationFrame(() => requestAnimationFrame(() => orb.setAttribute("docked", "")));
  },
});

// The day dial is off by default (HUD v3 §14); a host that wants it (Today) adds the `dial` attribute.
registerScene("orb-dial", {
  about: "With the day dial (attribute dial): the dial at 2.5 R round the bare ticks",
  patch: (s) => { s.orb = { state: "idle" }; },
  render(stage) {
    const orb = make("idle", "centre", "", { dial: "" });
    orb.append(el("jv-day-dial", {}, { slot: "dial", live: "" }));
    stageWith(stage, orb, "idle // with the day dial", "idle");
  },
});

// The strip (Laptop A): still orbs, state by colour and a word, nothing moves.
registerScene("orb-strip", {
  size: "strip", about: "Strip size: still, state by colour and word",
  render(stage) {
    const grid = el("div", { className: "jv-orb-strip-scene" });
    for (const [name, state, alert] of LOOKS) {
      const row = el("div", { className: "jv-orb-strip-scene__item" });
      row.append(make(state, "strip", alert), el("span", { textContent: wordOf(state, alert) }));
      row.dataset.state = name;
      grid.append(row);
    }
    stage.replaceChildren(grid);
  },
});

registerGallery("orb", [
  ...LOOKS.map(([name, state, alert]) => ({ label: name === "idle" ? "Idle" : wordOf(state, alert), build: () => make(state, "centre", alert) })),
  { label: "Docked mini rings", wide: true, build: () => { const row = el("div", { className: "jv-orb-row" }); LOOKS.forEach(([, s, a]) => row.append(make(s, "corner", a))); return row; } },
  { label: "Strip sizes (never animate)", wide: true, build: () => { const row = el("div", { className: "jv-orb-row" }); LOOKS.forEach(([, s, a]) => row.append(make(s, "strip", a))); return row; } },
], { about: "The Core: Huw's orb, layer by layer. Each state is a colour, a shape and a word; reduced motion and the strip hold a still pose.", columns: "300px" });
