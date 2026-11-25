// Life Map engine (V03a, redrawn as a plant in v0.2.1): the branch in focus is a pot of soil at the bottom,
// its children are leaves on curved stems fanning up out of it (at most 7, the rest fold into "+n more"),
// and grandchildren are small leaflets on each stem (a preview of what's inside). Flying in or out takes
// 300 ms (it cuts under reduced motion); d3-zoom gives wheel/pinch zoom and drag. Pure functions first, so
// they can be tested.
import { select, zoom, zoomIdentity } from "../../vendor/d3-lifemap.js";

export const MAX_CHILDREN = 7;
/** The map's drawing space (user units). The pot sits at (0, POT_Y); leaves fan above it. */
export const VIEW = { x: -460, y: -400, w: 920, h: 710 };
export const POT_Y = 150, RX = 275, RY = 345, LIFT = 40;
const MAX_LEAFLETS = 5;

/** Pending approvals per branch, counted on the branch and every branch above it (from state.approvals). */
export function pendingCounts(branches, approvals) {
  const byId = new Map(branches.map((b) => [b.id, b])), out = new Map();
  for (const a of approvals || []) {
    if (a.status !== "pending" || !a.branch_id) continue;
    const seen = new Set();
    for (let b = byId.get(a.branch_id); b && !seen.has(b.id); b = byId.get(b.parent)) { seen.add(b.id); out.set(b.id, (out.get(b.id) || 0) + 1); }
  }
  return out;
}
/** The branches with `pending` worked out from the approvals instead of trusting a stored count. */
export function withPending(branches, approvals) {
  const counts = pendingCounts(branches, approvals);
  return branches.map((b) => ((b.pending || 0) === (counts.get(b.id) || 0) ? b : { ...b, pending: counts.get(b.id) || 0 }));
}

const rank = (b) => (b.status === "proposed" ? 0.5 : 0) + (2 - (b.activity || 0)) + (b.due ? -0.4 : 0) + (b.pending ? -0.6 : 0);
export const byActivity = (a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name);

/** Children the map shows for a branch: no system tray, archived ones leave the plant. */
export function mapChildren(branches, id) {
  return branches.filter((b) => b.parent === id && b.kind !== "system" && b.status !== "archived").sort(byActivity);
}
export function crumbs(branches, id) {
  const out = [];
  for (let b = branches.find((x) => x.id === id); b; b = branches.find((x) => x.id === b.parent)) out.unshift(b);
  return out;
}
/** Which branch the map centres on for a selected branch: itself if it has children, else its parent. */
export function focusFor(branches, id) {
  const b = branches.find((x) => x.id === id) || branches.find((x) => x.kind === "root");
  if (!b) return null;
  return mapChildren(branches, b.id).length || !b.parent ? b.id : b.parent;
}

const r1 = (v) => Math.round(v * 10) / 10;
/** A cubic Bézier: point and unit tangent at t. */
export function cubicAt([p0, p1, p2, p3], t) {
  const u = 1 - t;
  const x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0];
  const y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1];
  const dx = 3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0]);
  const dy = 3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1]);
  const len = Math.hypot(dx, dy) || 1;
  return { x, y, ux: dx / len, uy: dy / len, angle: (Math.atan2(dy, dx) * 180) / Math.PI };
}
/** Fan angles (degrees from straight up) for n stems: spread evenly, wider with more stems. */
export function fanAngles(n) {
  if (n <= 1) return [0];
  const half = Math.min(78, 22 * (n - 1));
  return Array.from({ length: n }, (_, i) => -half + (2 * half * i) / (n - 1));
}
/** A stem from the soil to a node: it leaves the pot going up, then arches out to the leaf. */
export function stemCurve(deg) {
  const a = (deg * Math.PI) / 180, s = Math.sin(a), c = Math.cos(a);
  const x = r1(s * RX), y = r1(POT_Y - LIFT - c * RY);
  const sx = r1(s * 34), sy = POT_Y - 4;
  const p1 = [sx + s * 10, sy - (POT_Y - y) * 0.42 - 20];
  const p2 = [x * 0.62, y + (POT_Y - y) * 0.1 + Math.abs(s) * 70];
  return [[sx, sy], p1, p2, [x, y]];
}

/** The whole picture for one focus. → { focus, parent, crumbs, siblings, ring: [{ branch, angle, x, y, ux, uy, curve, dots }], more } */
export function mapModel(branches, focusId, max = MAX_CHILDREN) {
  const focus = branches.find((b) => b.id === focusId) || branches.find((b) => b.kind === "root");
  if (!focus) return null;
  const kids = mapChildren(branches, focus.id);
  const over = kids.length > max;
  const shown = over ? kids.slice(0, max - 1) : kids;
  const hidden = over ? kids.slice(max - 1) : [];
  // busiest stems in the middle, quieter ones out to the sides, "+n more" always last on the right
  const order = [];
  shown.forEach((k, i) => (i % 2 ? order.unshift(k) : order.push(k)));
  const slots = [...order, ...(over ? ["__more"] : [])];
  const angles = fanAngles(slots.length);
  const ring = [];
  let more = null;
  slots.forEach((k, i) => {
    const curve = stemCurve(angles[i]), end = cubicAt(curve, 1);
    const spot = { angle: angles[i], x: curve[3][0], y: curve[3][1], ux: end.ux, uy: end.uy, curve };
    if (k === "__more") { more = { count: hidden.length, hidden, ...spot }; return; }
    const dots = mapChildren(branches, k.id).slice(0, MAX_LEAFLETS).map((g, j) => {
      const at = cubicAt(curve, 0.55 + j * 0.08), side = j % 2 ? 1 : -1;
      return { branch: g, x: r1(at.x), y: r1(at.y), angle: r1(at.angle + side * 52) };
    });
    ring.push({ branch: k, ...spot, dots });
  });
  const parent = branches.find((b) => b.id === focus.parent) || null;
  return { focus, parent, crumbs: crumbs(branches, focus.id), ring, more,
    siblings: parent ? mapChildren(branches, parent.id).filter((b) => b.id !== focus.id) : [],
    archived: branches.filter((b) => b.parent === focus.id && b.status === "archived"), count: 1 + ring.length + ring.reduce((n, r) => n + r.dots.length, 0) + (more ? 1 : 0) };
}

/** How many CSS px one map unit is drawn at (the SVG keeps its aspect ratio: "meet"). */
export function mapScale(width, height, view = VIEW) { return Math.min(width / view.w, height / view.h); }

/** Fly the map: from where the clicked branch was (fly in) or from a wider view (fly out). Cuts when still. */
export function fly(world, { from = null, out = false } = {}) {
  if (document.documentElement.hasAttribute("data-still") || !world.animate) return null;
  const start = out ? "scale(1.5)" : from ? `translate(${from.x}px, ${from.y}px) scale(0.35)` : "scale(0.92)";
  return world.animate([{ transform: start, opacity: 0.15 }, { transform: "none", opacity: 1 }], { duration: 300, easing: "cubic-bezier(0.45, 0, 0.25, 1)" });
}

/** Wheel / pinch zoom and drag on the map. Returns { reset() }. */
export function attachZoom(svg, viewport) {
  const behaviour = zoom().scaleExtent([0.7, 2.4]).filter((e) => (e.type === "wheel" ? e.ctrlKey || e.metaKey || !e.shiftKey : !e.button) && !e.target.closest?.("a"))
    .on("zoom", (e) => viewport.setAttribute("transform", e.transform.toString()));
  const sel = select(svg).call(behaviour).on("dblclick.zoom", null);
  return { reset: () => sel.call(behaviour.transform, zoomIdentity) };
}
