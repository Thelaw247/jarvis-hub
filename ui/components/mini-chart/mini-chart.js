// <jv-mini-chart heading="…" type="bar|line" unit="ms" tone="neutral|growth">: a small chart in token colours.
//   .data = [{ label, value }]   .target = number (optional reference line, labelled)
// Dataviz rules: one series, one hue; every value is labelled directly (on top) and every bar or point has its
// short label underneath (12 px mono in Night: MON … FRI); a real data table sits behind "Show the numbers" and
// is what screen readers get. No colour carries meaning on its own.
// Drawn in HTML (not a scaled picture), so it fits whatever height its window gives it: the plot takes the
// room that is left and the bars scale to it, every bar at least 2 px tall, and no bar is ever cut off. Text
// stays 12 px at any size. Line charts draw the line in a stretched SVG with a non-scaling stroke.
import { css, html, Jv, raw } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const pct = (v) => `${(Math.round(v * 10000) / 100).toFixed(2)}%`;
const clean = (t) => String(t ?? "").replace(/[<&"]/g, "");
/** Short labels under the bars: a day name becomes its first three letters ("Monday" → "Mon"). */
export const shortLabel = (t) => { const s = String(t ?? "").trim(); return /^(mon|tues?|wed(nes)?|thu(rs)?|fri|sat(ur)?|sun)(day)?$/i.test(s) ? s.slice(0, 3) : s; };

/** Where every value sits, as shares of the plot's height (0 at the axis, 1 at the top). Pure (tests use it). */
export function chartModel(data = [], { type = "bar", target } = {}) {
  const line = type === "line", values = data.map((d) => Number(d.value) || 0);
  const max = Math.max(...values, Number(target) || 0) * 1.08 || 1;
  const min = line && values.length ? Math.min(...values) * 0.9 : 0;
  const share = (v) => (max === min ? 0.5 : Math.max(0, Math.min(1, (v - min) / (max - min))));
  return { points: data.map((d, i) => ({ label: d.label, value: values[i], v: share(values[i]), x: (i + 0.5) / data.length })), target: target ? share(Number(target)) : null };
}

class MiniChart extends Jv {
  static props = ["data", "target"];
  static attrs = ["heading", "type", "unit", "tone", "bare", "numbers"];
  render() {
    const data = this.data || [], unit = this.getAttribute("unit") || "", heading = this.getAttribute("heading") || "Chart";
    if (!data.length) return html`<p class="jv-muted">No numbers yet.</p>`;
    const table = html`<table><caption class="${this.hasAttribute("numbers") ? "jv-mini-chart__caption" : "jv-sr"}">${heading}${this.hasAttribute("numbers") && unit ? ` (${unit})` : ""}</caption><thead><tr><th scope="col">Item</th><th scope="col">${unit || "Value"}</th></tr></thead>
        <tbody>${data.map((d) => html`<tr><th scope="row">${d.label}</th><td class="jv-num">${d.value}</td></tr>`)}</tbody></table>`;
    // `numbers`: the data table alone (a window's "Why?" drawer holds it; screen readers get the chart from it)
    if (this.hasAttribute("numbers")) return html`<div class="jv-mini-chart__table jv-mini-chart__table--open">${table}</div>`;
    const bare = this.hasAttribute("bare");  // a window's hero: the plot and its labels, nothing else
    const line = this.getAttribute("type") === "line";
    const m = chartModel(data, { type: line ? "line" : "bar", target: this.target });
    const fmt = (v) => `${Math.round(v * 10) / 10}${unit && unit.length <= 2 ? unit : ""}`;
    const value = (p) => `<span class="jv-mini-chart__value" style="left:${pct(p.x)};bottom:${pct(p.v)}">${clean(fmt(p.value))}</span>`;
    let marks;
    if (line) {
      const pts = m.points.map((p) => `${(p.x * 100).toFixed(2)},${((1 - p.v) * 100).toFixed(2)}`).join(" ");
      marks = `<svg class="jv-mini-chart__svg" viewBox="0 0 100 100" preserveAspectRatio="none" focusable="false"><polyline class="jv-mini-chart__line" points="${pts}" vector-effect="non-scaling-stroke"/></svg>`
        + m.points.map((p) => `<span class="jv-mini-chart__dot" style="left:${pct(p.x)};bottom:${pct(p.v)}"></span>`).join("");
    } else {
      marks = m.points.map((p) => `<span class="jv-mini-chart__bar" style="left:${pct(p.x)};height:max(2px, ${pct(p.v)})"></span>`).join("");
    }
    const target = m.target != null ? `<span class="jv-mini-chart__target" style="bottom:${pct(m.target)}"><span class="jv-mini-chart__target-label">target ${clean(fmt(this.target))}</span></span>` : "";
    const labels = m.points.map((p) => `<span class="jv-mini-chart__label">${clean(shortLabel(p.label))}</span>`).join("");
    return html`<figure class="jv-mini-chart jv-mini-chart--${this.getAttribute("tone") || "neutral"} ${line ? "jv-mini-chart--line" : "jv-mini-chart--bars"}${bare ? " jv-mini-chart--bare" : ""}" style="--n:${data.length}">
      ${bare ? "" : html`<figcaption class="jv-mini-chart__caption">${heading}${unit ? html` <span class="jv-mini-chart__unit">(${unit})</span>` : ""}</figcaption>`}
      <div class="jv-mini-chart__plot" aria-hidden="true"><div class="jv-mini-chart__area">${raw(target + marks + m.points.map(value).join(""))}</div></div>
      <div class="jv-mini-chart__labels" aria-hidden="true">${raw(labels)}</div>
      ${bare ? "" : html`<details class="jv-mini-chart__table"><summary class="jv-link" data-key="table">Show the numbers</summary>${table}</details>`}
    </figure>`;
  }
}
MiniChart.define("jv-mini-chart");

const WEEK = [{ label: "Mon", value: 2.5 }, { label: "Tue", value: 3 }, { label: "Wed", value: 1.5 }, { label: "Thu", value: 2 }, { label: "Fri", value: 1 }];
registerGallery("mini-chart", [
  { label: "Bars with a target", build: (s) => el("jv-mini-chart", { data: s.metrics.latency.map((l) => ({ label: l.stage.split(" ")[0], value: l.p95_ms })), target: 800 }, { heading: "Slowest replies, p95", unit: "ms" }) },
  { label: "A trend (growth tone)", build: (s) => el("jv-mini-chart", { data: s.metrics.eval.map((e) => ({ label: e.week, value: e.score })) }, { heading: "Know De Wet score", type: "line", tone: "growth", unit: "%" }) },
  { label: "A week, short (every bar kept)", build: () => { const c = el("jv-mini-chart", { data: WEEK }, { heading: "Study hours planned", unit: "h", tone: "growth" }); c.style.height = "150px"; return c; } },
  { label: "No numbers yet", build: () => el("jv-mini-chart", { data: [] }, { heading: "Spend" }) },
], { about: "One series, labelled directly, with the numbers behind it as a table. It fits the height it is given.", columns: "360px" });
