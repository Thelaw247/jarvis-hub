// <jv-caption>: one spoken line with its source chip, above the icon row (the Rail), so any claim can be checked
// at a glance.   .caption = caption contract (+ `shown`, set by the store). Fades in ~150 ms.
// Only while it is being said (HUD v3 §14 decision 7): Jarvis's line shows while the orb is speaking and goes the
// moment he stops; his own words show while Jarvis hears and thinks about them. A line that comes while the orb
// isn't speaking it (quiet hours: shown, not said) stays for its ttl_ms, as before. Either way it never stays
// past ttl_ms. `.orb` is the orb_state (the shell's copy reads the store itself); `sticky` (galleries) keeps it.
// Night: a slim HUD strip with a cyan "Jarvis said" tick (his own words get a quiet "You" tick instead).
// Leaving the screen doesn't lose the line: the hub keeps the last 10 under the Rail's Jarvis slot
// (rail.slots.jarvis.said, contracts v2), so it can always be read back there.
// It is a visual echo of speech; screen readers get the line from core/a11y.js instead (aria-hidden here).
import { css, html, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

/** The orb states during which a line is being said: Jarvis's while he speaks, his own while he is heard. */
export const SAYING = { jarvis: new Set(["speaking"]), you: new Set(["listening", "thinking"]) };

/** Is this caption still up, given the orb now and whether it was being said when it came? (pure; tests call it) */
export function captionLive(caption, orbState, saidLive) {
  if (!caption?.text) return false;
  const who = caption.source?.kind === "you" ? "you" : "jarvis";
  return !saidLive || SAYING[who].has(orbState);
}

class Caption extends Jv {
  static props = ["caption", "orb"];
  static attrs = ["sticky"];
  // the shell's copy follows the store's orb; a sticky (gallery) copy never goes
  connectedCallback() {
    super.connectedCallback();
    if (!this.hasAttribute("sticky") && !this.stopOrb) this.stopOrb = store.watch(["orb"], (s) => { this.orb = s.orb; });
  }
  teardown() { clearTimeout(this.timer); this.stopOrb?.(); this.stopOrb = null; }
  render() {
    const c = this.caption, sticky = this.hasAttribute("sticky"), state = this.orb?.state;
    clearTimeout(this.timer);
    if (!c || !c.text) return html``;
    if (c !== this._seen) {  // a new line: was it being said as it came? (and it never outlives its ttl)
      this._seen = c; this._gone = false;
      this._live = !sticky && SAYING[c.source?.kind === "you" ? "you" : "jarvis"].has(state);
      this._until = Date.now() + (c.ttl_ms || 6000);
    }
    if (!sticky && !captionLive(c, state, this._live)) this._gone = true;  // he stopped: the line folds into the Jarvis slot
    if (this._gone) return html``;
    if (!sticky) this.timer = setTimeout(() => { this._gone = true; this.update(); }, Math.max(0, this._until - Date.now()));
    const his = c.source?.kind === "you";
    return html`<p class="jv-caption${his ? " jv-caption--you" : ""}" aria-hidden="true"><span class="jv-caption__who">${his ? "You" : "Jarvis"}</span><span class="jv-caption__text">${c.text}</span>${c.source && !his ? html`<jv-source-chip></jv-source-chip>` : ""}</p>`;
  }
  rendered() { const chip = this.$("jv-source-chip"); if (chip) chip.source = this.caption?.source; }
}
Caption.define("jv-caption");

const cap = (caption) => el("jv-caption", { caption }, { sticky: true });
registerGallery("caption", [
  { label: "A claim with its source", wide: true, build: () => cap({ text: "PPS 7 is due Wednesday at 8 pm.", source: { kind: "canvas", label: "Canvas" } }) },
  { label: "What he said", wide: true, build: () => cap({ text: "“Pull up PPS 7.”", source: { kind: "you", label: "You · just now" } }) },
  { label: "No source needed", wide: true, build: () => cap({ text: "Understood. Carrying on.", source: null }) },
], { about: "One line, fades in and out; the last ten stay under the Jarvis slot on the Rail. Never more than one at a time." });
