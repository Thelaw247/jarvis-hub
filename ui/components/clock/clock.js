// <jv-clock>: the clock, in two sizes.
//   default  the big thin clock, with the date and one "next up" line (Today and older layouts)
//   small    (attribute) Huw's standby clock (HUD v3 §14): a small mono time with a tiny tracked date under it,
//            for under the standby sphere. Never dominates; no "next up" line. Its size comes from the host:
//            --jv-clock-size (CSS) sets the digits' font size; the default is about 1/30 of the screen's width.
//   .now = Date | ISO string   .next = "Review GE 122 lecture 21 · 4:00 pm"   attribute `live` follows the hub clock
// Shows hours and minutes only (no seconds ticking for attention); it redraws when the minute changes.
import { asDate, css, dayName, html, Jv, shortDate } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

class Clock extends Jv {
  static props = ["now", "next"];
  static attrs = ["live", "small"];
  setup() { if (this.hasAttribute("live")) this.timer = setInterval(() => { if (!document.hidden && this.minute !== this.stamp()) this.update(); }, 5000); }
  teardown() { clearInterval(this.timer); }
  time() { return this.hasAttribute("live") ? store.now() : asDate(this.now || store.now()); }
  stamp() { const d = this.time(); return d.getHours() * 60 + d.getMinutes(); }
  render() {
    const d = this.time(), small = this.hasAttribute("small");
    this.minute = this.stamp();
    const h = d.getHours() % 12 || 12, m = String(d.getMinutes()).padStart(2, "0"), half = d.getHours() < 12 ? "am" : "pm";
    return html`<div class="jv-clock${small ? " jv-clock--small" : ""}">
      <time class="jv-clock__time" datetime="${String(d.getHours()).padStart(2, "0")}:${m}"><span class="jv-sr">The time is </span>${h}:${m}<span class="jv-clock__half">${half}</span></time>
      <p class="jv-clock__date">${dayName(d)}, ${shortDate(d)}</p>
      ${this.next && !small ? html`<p class="jv-clock__next"><span class="jv-label">Next</span> ${this.next}</p>` : ""}
    </div>`;
  }
}
Clock.define("jv-clock");

registerGallery("clock", [
  { label: "With next up", wide: true, build: (s) => el("jv-clock", { now: s.now, next: "Review GE 122 lecture 21 · 4:00 pm" }) },
  { label: "Nothing next", wide: true, build: () => el("jv-clock", { now: "2026-11-16T21:05:00" }) },
  { label: "Small (standby)", wide: true, build: (s) => el("jv-clock", { now: s.now }, { small: "" }) },
  { label: "Small, morning", wide: true, build: () => el("jv-clock", { now: "2026-11-17T07:05:00" }, { small: "" }) },
], { about: "Night: JetBrains Mono with a tiny tracked date. Small: Huw's standby clock, for under the standby sphere. Daylight: Lexend. Hours and minutes only." });
