// <jv-glance state="soon" word="Soon · Wed 8 pm" size="rail|inline|hero" value="0.6" bare scan>   (label = word; label="" = bare)
// A glance code (HUD v2 §5): every state is a shape + a colour + one word, never colour alone.
//   done      filled cyan-hi disc with a dark check (≥ 16 px)          silent
//   progress  open ring with a progress arc in the ice line colour     silent      value = 0…1
//   jarvis    reticle (thin ring + 4 ticks), cyan; `scan` adds a scan bar (one reticle on screen at most)
//   soon      diamond in corner brackets, warn                          needs you soon
//   yes       hollow square in corner brackets, warn                    waiting for your yes
//   critical  triangle in corner brackets, crit; the brackets move ±2 px at ~1 Hz for 5 s, then hold still
//   parked    dashed ring, text-3
// Corner brackets mean only "wants you" (soon, your yes, critical). The accessible name is the word
// (role="img"), and the word is drawn beside the shape unless `bare` (then only screen readers hear it).
// `glance(state, opts)` returns the same markup as an html`` value, for components that draw their own.
import { css, html, raw } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

/** The seven glance codes: default word and what each one means. */
export const GLANCE = {
  done: { word: "Done", means: "Finished" },
  progress: { word: "In progress", means: "Under way" },
  jarvis: { word: "Jarvis", means: "Jarvis is on it" },
  soon: { word: "Soon", means: "Needs you soon" },
  yes: { word: "Your yes", means: "Waiting for your yes" },
  critical: { word: "Now", means: "Critical or overdue" },
  parked: { word: "Parked", means: "Parked for later" },
};
export const GLANCE_STATES = Object.keys(GLANCE);
/** States that want him: the only ones drawn in corner brackets, and the ones that count toward "≤ 4 amber/red". */
export const WANTS_YOU = new Set(["soon", "yes", "critical"]);

const BRACKETS = '<path class="jv-glance__brackets" d="M2 7.5V2h5.5M16.5 2H22v5.5M22 16.5V22h-5.5M7.5 22H2v-5.5"/>';
const clamp = (v) => Math.max(0, Math.min(1, Number(v) || 0));

function shape(state, value) {
  switch (state) {
    case "done": return '<circle class="jv-glance__fill" cx="12" cy="12" r="9.5"/><path class="jv-glance__check" d="M7.6 12.4l3 3 5.8-6.2"/>';
    case "progress": {
      // with a real value: a dim track and a bright arc; without one, just the open ring (no made-up number)
      if (value == null || value === "") return '<circle class="jv-glance__arc" cx="12" cy="12" r="8.5" pathLength="100" stroke-dasharray="78 100" transform="rotate(-90 12 12)"/>';
      const pct = Math.round(clamp(value) * 100);
      return `<circle class="jv-glance__track" cx="12" cy="12" r="8.5"/><circle class="jv-glance__arc" cx="12" cy="12" r="8.5" pathLength="100" stroke-dasharray="${pct} 100" transform="rotate(-90 12 12)"/>`;
    }
    case "jarvis": return '<circle class="jv-glance__ring" cx="12" cy="12" r="6"/><path class="jv-glance__ticks" d="M12 1.5v4.5M12 18v4.5M1.5 12H6M18 12h4.5"/><circle class="jv-glance__fill" cx="12" cy="12" r="1.6"/>';
    case "soon": return `${BRACKETS}<path class="jv-glance__fill jv-glance__diamond" d="M12 6.2 17.8 12 12 17.8 6.2 12Z"/>`;
    case "yes": return `${BRACKETS}<path class="jv-glance__line jv-glance__square" d="M7.5 7.5h9v9h-9Z"/>`;
    case "critical": return `${BRACKETS}<path class="jv-glance__fill jv-glance__triangle" d="M12 6 18.2 17H5.8Z"/>`;
    case "parked": return '<circle class="jv-glance__dashed" cx="12" cy="12" r="8.5"/>';
    default: return "";
  }
}

/** One glance code as markup: shape + word, named by its word.
 *  opts: { word, size: "rail" | "inline" | "hero", value (progress 0…1), bare (word for screen readers only),
 *          scan (jarvis: add the scan bar), cls (extra class) } */
export function glance(state, { word, size = "inline", value, bare = false, scan = false, cls = "" } = {}) {
  const s = GLANCE[state] ? state : "progress";
  const name = word || GLANCE[s].word;
  return html`<span class="jv-glance jv-glance--${s} jv-glance--${size}${cls ? ` ${cls}` : ""}" role="img" aria-label="${name}" data-glance="${s}">${raw(
    `<svg class="jv-glance__shape" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${shape(s, value)}</svg>`)}${
    bare ? "" : html`<span class="jv-glance__word" aria-hidden="true">${name}</span>`}${
    s === "jarvis" && scan ? raw('<span class="jv-glance__scan" aria-hidden="true"><span class="jv-glance__chunk"></span></span>') : ""}</span>`;
}

class Glance extends HTMLElement {
  static observedAttributes = ["state", "word", "label", "size", "value", "bare", "scan"];
  connectedCallback() { this.draw(); }
  attributeChangedCallback() { if (this.isConnected) this.draw(); }
  draw() {
    const a = (n) => this.getAttribute(n);
    // `label` is another name for `word`; label="" asks for the shape alone (screen readers still get the default word)
    this.innerHTML = String(glance(a("state"), { word: a("word") || a("label") || undefined, size: a("size") || "inline", value: a("value"), bare: this.hasAttribute("bare") || a("label") === "", scan: this.hasAttribute("scan") }));
  }
}
if (!customElements.get("jv-glance")) customElements.define("jv-glance", Glance);

// ---- scenes: every state at every size, in a row so shapes can be compared ---------------------------------
const row = (size, extra = {}) => () => {
  const box = el("div", { className: "jv-glance-demo" });
  box.innerHTML = String(html`${GLANCE_STATES.map((s) => glance(s, { size, ...(extra[s] || {}) }))}`);
  return box;
};
const words = { progress: { word: "Q7 of 12", value: 0.58 }, soon: { word: "Soon · Wed 8 pm" }, critical: { word: "Now · Lab 4 report" }, jarvis: { scan: true } };
registerGallery("glance", [
  { label: "Every state, inline", wide: true, build: row("inline", words) },
  { label: "Every state, rail (16 px)", wide: true, build: row("rail") },
  { label: "Every state, hero", wide: true, build: row("hero", { progress: { value: 0.58, word: "Q7 of 12" } }) },
  { label: "Shape only (word for screen readers)", wide: true, build: () => {
    const box = el("div", { className: "jv-glance-demo" });
    box.innerHTML = String(html`${GLANCE_STATES.map((s) => glance(s, { size: "inline", bare: true }))}`);
    return box;
  } },
  { label: "Progress steps", build: () => {
    const box = el("div", { className: "jv-glance-demo" });
    box.innerHTML = String(html`${[0, 0.25, 0.5, 0.75, 1].map((v) => glance("progress", { value: v, word: `${Math.round(v * 100)}%` }))}`);
    return box;
  } },
  { label: "As an element", build: () => el("jv-glance", {}, { state: "yes", word: "Your yes · Week plan" }) },
], { about: "Every state is a shape, a colour and a word. Brackets only mean “wants you”. Critical moves for 5 s, then holds still." });
