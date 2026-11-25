// <jv-plant kind="day|sprig|potted|leaf">: Pen Reader's leaf family (tools/make_plants.py), drawn in the browser
// from the same leaf shape so every plant reads as one family. Colours come from the plant tokens.
//   kind="day": a vine that grows a leaf for each thing done today.  .done / .total  (progress, never a streak)
// Exports the leaf and pot geometry for the Life Map (the focus is a pot, branches are leaves on stems).
import { css, Jv, raw } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const f = (v) => String(Math.round(v * 10) / 10);

/** One leaf lying along +x from its base at the origin: dark body, light upper half, rib. */
export function leafPaths(length, fat = 0.36) {
  const L = length, W = length * fat;
  return {
    body: `M0 0C${f(0.28 * L)} ${f(-W)} ${f(0.72 * L)} ${f(-0.86 * W)} ${f(L)} 0C${f(0.72 * L)} ${f(0.86 * W)} ${f(0.28 * L)} ${f(W)} 0 0Z`,
    light: `M0 0C${f(0.28 * L)} ${f(-W)} ${f(0.72 * L)} ${f(-0.86 * W)} ${f(L)} 0Z`,
    rib: `M0 0L${f(0.8 * L)} 0`,
  };
}
export function leaf(length, fat = 0.36, cls = "") {
  const p = leafPaths(length, fat);
  return `<g class="jv-leaf ${cls}"><path class="jv-leaf__body" d="${p.body}"/><path class="jv-leaf__light" d="${p.light}"/><path class="jv-leaf__rib" d="${p.rib}"/></g>`;
}
const placed = (x, y, angle, inner, extra = "") => `<g transform="translate(${f(x)} ${f(y)}) rotate(${f(angle)})"${extra}>${inner}</g>`;

function bezier(p0, p1, p2, p3, t) {
  const u = 1 - t;
  const x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0];
  const y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1];
  const dx = 3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0]);
  const dy = 3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1]);
  return [x, y, (Math.atan2(dy, dx) * 180) / Math.PI];
}
/** Catmull-Rom through the points, as cubic segments. */
export function smooth(points) {
  const segs = [];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)], p1 = points[i], p2 = points[i + 1], p3 = points[Math.min(i + 2, points.length - 1)];
    segs.push([p1, [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6], [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6], p2]);
  }
  return segs;
}
export const pathOf = (segs) => `M${f(segs[0][0][0])} ${f(segs[0][0][1])}` + segs.map(([, c1, c2, p]) => `C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p[0])} ${f(p[1])}`).join("");
function along(segs, fraction) {
  const pos = fraction * segs.length, i = Math.min(Math.floor(pos), segs.length - 1);
  return bezier(...segs[i], pos - i);
}
/** A clay pot whose rim top-centre is (cx, top). Shared with the Life Map, where the focus is the pot. */
export function pot(cx, top, wTop, wBot, h) {
  const rimH = h * 0.2, rimW = wTop + h * 0.14;
  const body = `M${f(cx - wTop / 2)} ${f(top + rimH - 1)}L${f(cx + wTop / 2)} ${f(top + rimH - 1)}L${f(cx + wBot / 2)} ${f(top + h - 5)}Q${f(cx + wBot / 2 - 1)} ${f(top + h)} ${f(cx + wBot / 2 - 6)} ${f(top + h)}L${f(cx - wBot / 2 + 6)} ${f(top + h)}Q${f(cx - wBot / 2 + 1)} ${f(top + h)} ${f(cx - wBot / 2)} ${f(top + h - 5)}Z`;
  const shade = `M${f(cx + wTop * 0.12)} ${f(top + rimH - 1)}L${f(cx + wTop / 2)} ${f(top + rimH - 1)}L${f(cx + wBot / 2)} ${f(top + h - 5)}Q${f(cx + wBot / 2 - 1)} ${f(top + h)} ${f(cx + wBot / 2 - 6)} ${f(top + h)}L${f(cx + wBot * 0.2)} ${f(top + h)}Z`;
  return `<path class="jv-plant__pot" d="${body}"/><path class="jv-plant__pot2" d="${shade}"/><rect class="jv-plant__pot3" x="${f(cx - rimW / 2)}" y="${f(top)}" width="${f(rimW)}" height="${f(rimH)}" rx="${f(rimH * 0.35)}"/>`;
}

const LEAVES = 12;
/** The day plant: a vine in a pot. `grown` 0..1 decides how many of its 12 leaves are out; it blooms at 1. */
export function dayPlant(grown) {
  const g = Math.max(0, Math.min(1, grown || 0));
  const segs = smooth([[48, 394], [53, 340], [43, 284], [53, 228], [43, 172], [52, 116], [47, 62], [49, 34]]);
  const shown = Math.round(g * LEAVES);
  const reach = shown ? 0.13 + (0.8 * (shown - 1)) / (LEAVES - 1) + 0.05 : 0.08;
  const out = [`<path class="jv-plant__stem" pathLength="100" stroke-dasharray="${f(reach * 100)} 100" d="${pathOf(segs)}"/>`,
    placed(48, 386, -150, leaf(15, 0.4)), placed(48, 382, -32, leaf(17, 0.4))];
  for (let n = 0; n < shown; n++) {
    const frac = 0.13 + (0.8 * n) / (LEAVES - 1);
    const [x, y, a] = along(segs, frac);
    out.push(placed(x, y, a + (n % 2 === 0 ? 1 : -1) * 58, leaf(31 - (13 * n) / (LEAVES - 1), 0.37)));
  }
  if (g >= 1) {
    const [x, y] = along(segs, 1);
    const petals = Array.from({ length: 5 }, (_, k) => `<ellipse class="jv-plant__petal" cx="0" cy="-6.2" rx="3.6" ry="5.4" transform="rotate(${k * 72})"/>`).join("");
    out.push(`<g transform="translate(${f(x)} ${f(y - 3)})">${petals}<circle class="jv-plant__eye" r="3"/></g>`);
  }
  out.push('<ellipse class="jv-plant__soil" cx="48" cy="396" rx="24" ry="3.4"/>', pot(48, 394, 50, 38, 42));
  return { viewBox: "0 0 96 440", inner: out.join("") };
}
function sprig() {
  const segs = smooth([[2, 30], [30, 20], [62, 13], [96, 12]]);
  const out = [`<path class="jv-plant__stem" d="${pathOf(segs)}"/>`];
  for (let n = 0; n < 7; n++) { const [x, y, a] = along(segs, 0.14 + (0.8 * n) / 6); out.push(placed(x, y, a + (n % 2 === 0 ? -1 : 1) * 50, leaf(17 - n, 0.38))); }
  const [x, y, a] = along(segs, 1);
  out.push(placed(x, y, a, leaf(12, 0.4)));
  return { viewBox: "0 0 112 40", inner: out.join("") };
}
function potted() {
  const base = [150, 226], out = ['<path class="jv-plant__wash" d="M150 22C212 14 276 60 280 128C284 196 244 262 170 268C96 274 26 232 20 158C14 84 82 30 150 22Z"/>', '<ellipse class="jv-plant__shade" cx="150" cy="287" rx="62" ry="7"/>'];
  const stems = [[-66, 128, 0.44, 5], [-36, 164, 0.3, 7], [-4, 190, 0.08, 8], [30, 170, 0.26, 7], [62, 134, 0.42, 5]];
  for (const k of [0, 4, 1, 3, 2]) {
    const [ang, length, bend, count] = stems[k], r = (ang * Math.PI) / 180;
    const p0 = base, p1 = [base[0] + Math.sin(r) * 5, base[1] - length * 0.36], p2 = [base[0] + Math.sin(r) * length * 0.3, base[1] - length * 0.64];
    const p3 = [base[0] + Math.sin(r) * length, base[1] - Math.cos(r) * length * (1 - bend * 0.55)];
    out.push(`<g class="${k % 2 ? "jv-plant__frond--deep" : ""}"><path class="jv-plant__stem" d="M${f(p0[0])} ${f(p0[1])}C${f(p1[0])} ${f(p1[1])} ${f(p2[0])} ${f(p2[1])} ${f(p3[0])} ${f(p3[1])}"/>`);
    for (let n = 0; n < count; n++) {
      const [x, y, a] = bezier(p0, p1, p2, p3, 0.44 + (0.5 * n) / (count - 1));
      for (const side of [1, -1]) out.push(placed(x, y, a + side * (56 - (10 * n) / (count - 1)), leaf(27 - (11 * n) / (count - 1), 0.36)));
    }
    const [x, y, a] = bezier(p0, p1, p2, p3, 1);
    out.push(placed(x, y, a, leaf(17, 0.38)), "</g>");
  }
  out.push('<ellipse class="jv-plant__soil" cx="150" cy="228" rx="46" ry="5"/>', pot(150, 224, 92, 68, 62));
  return { viewBox: "0 0 300 310", inner: out.join("") };
}
const oneLeaf = () => ({ viewBox: "0 0 16 16", inner: placed(2.5, 13.5, -45, leaf(15, 0.42)) });

class Plant extends Jv {
  static attrs = ["kind"];
  static props = ["done", "total"];
  render() {
    const kind = this.getAttribute("kind") || "day";
    const total = this.total || 0, done = Math.min(this.done || 0, total);
    const art = kind === "sprig" ? sprig() : kind === "potted" ? potted() : kind === "leaf" ? oneLeaf() : dayPlant(total ? done / total : 0);
    const label = kind === "day" && total ? `Day plant: ${done} of ${total} done today` : "";
    return raw(`<svg class="jv-plant jv-plant--${kind}" viewBox="${art.viewBox}" preserveAspectRatio="xMidYMax meet" ${label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"'} focusable="false">${art.inner}</svg>`);
  }
}
Plant.define("jv-plant");

const plant = (done, total) => el("jv-plant", { done, total }, { kind: "day" });
registerGallery("plant", [
  { label: "Morning (0 of 6)", build: () => plant(0, 6) },
  { label: "Afternoon (4 of 6)", build: () => plant(4, 6) },
  { label: "All done (blooms)", build: () => plant(6, 6) },
  { label: "Potted (empty states)", build: () => el("jv-plant", {}, { kind: "potted" }) },
  { label: "Sprig and leaf", build: () => { const row = el("div", { className: "jv-plant-row" }); row.append(el("jv-plant", {}, { kind: "sprig" }), el("jv-plant", {}, { kind: "leaf" })); return row; } },
], { about: "Pen Reader's leaf family. The day plant grows with what got done; it never shrinks to scold.", columns: "200px" });
