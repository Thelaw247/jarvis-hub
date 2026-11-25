// Life Map nodes (V03b, redrawn as a plant in v0.2.1): what a branch looks like on the map. The leaf IS the
// node, at the end of a curved stem from the pot, with its name beside it in Lexend.
//   size        = activity in the last 14 days (three leaf sizes)
//   due outline = a thin outline around the leaf that fills as the nearest due date approaches; within 72 h
//                 it turns the notice colour and a "Due 2d" tag appears (words, never colour alone)
//   waiting tag = approvals waiting on this branch or anything inside it ("1 waiting"); the pot shows the
//                 focus's own tags under its name
//   leaflets    = small leaves on the stem, one per branch inside (up to five)
//   dashed      = a proposed branch · lock = private (tier 2)
// Every node is a real link (#/life/<id>) with a spoken label. Labels sit in a `.jv-map__tag` group that
// life.js scales so text never draws smaller than its CSS size, however small the map gets.
// Night HUD (N5b): the same plant structure drawn as a luminous constellation. Each node also carries a
// `.jv-map__mark` (an ice ring, sized by activity, with a circular due arc) and the pot a `.jv-map__core`
// (concentric rings); the theme's CSS shows the leaves and pot in Daylight, the marks and core in Night.
// Every Night node says something inside its ring: how many things are due under it, else its glyph ("PR"),
// "+n" on the more node; a private one shows its lock. Night draws no leaflets (a quiet line-art growth mark).
// The branch Jarvis is on (state.focus) and the path to it are cyan, with a reticle and a "Jarvis" tag.
// Tags carry their glance shape: a diamond for due soon, a hollow square for your yes, a dashed ring for proposed.
import { esc } from "../../core/dom.js";
import { leafPaths, pot } from "../../components/plant/plant.js";
import { POT_Y } from "./map.js";

export const LEAF = [58, 70, 84];
const FAT = 0.42;
const short = (name, n = 20) => (name.length > n ? `${name.slice(0, n - 1)}…` : name);
const f = (v) => String(Math.round(v * 10) / 10);

/** What a Night node says inside its ring (aria-hidden; the node's label says it in words): how many things
 *  are due under it, else its short glyph ("PR"), so no node is an empty disc (film review S8). */
export function markWord(b) {
  if (!b) return "";
  const due = b.counts?.due || 0;
  return due > 0 ? String(due) : String(b.glyph || b.name.slice(0, 2)).slice(0, 3).toUpperCase();
}

export function nodeLabel(b, jarvis = false) {
  const parts = [b.name];
  if (b.tier === 2) parts.push("private");
  if (b.status === "proposed") parts.push("proposed branch");
  if (b.status === "archived") parts.push("archived");
  if (b.due) parts.push(`due in ${b.due.label}${b.due.hours <= 72 ? ", due soon" : ""}`);
  if (b.pending) parts.push(`${b.pending} waiting for your yes`);
  if (jarvis) parts.push("Jarvis is working here");
  return parts.join(", ");
}

/** A stem from the soil to a node, along the curve map.js worked out. */
export function stem(item, jarvis = false) {
  const [p0, p1, p2, p3] = item.curve;
  return `<path class="jv-map__stem${jarvis ? " jv-map__stem--jarvis" : ""}" d="M${f(p0[0])} ${f(p0[1])}C${f(p1[0])} ${f(p1[1])} ${f(p2[0])} ${f(p2[1])} ${f(p3[0])} ${f(p3[1])}"/>`;
}

/** Where a node's label goes: past the leaf tip, beside it (or above it for the upright leaves). */
export function tagSpot(item, length) {
  const { x, y, ux, uy } = item, reach = length + 10;
  const tx = x + ux * reach, ty = y + uy * reach;
  if (Math.abs(ux) < 0.45 && uy < 0) return { x: tx, y: ty - 2, anchor: "middle", above: true };
  return { x: tx + (ux > 0 ? 2 : -2), y: ty, anchor: ux > 0 ? "start" : "end", above: false };
}

/** Each tag's glance shape (HUD v2 §5), centred on (0, 0); shown in Night, where life.js makes room for it. */
const MARK = {
  soon: "M0 -4.6L4.6 0L0 4.6L-4.6 0Z",
  yes: "M-4 -4h8v8h-8Z",
  quiet: "M-4.2 0a4.2 4.2 0 1 0 8.4 0a4.2 4.2 0 1 0 -8.4 0",
  jarvis: "M-3.4 0a3.4 3.4 0 1 0 6.8 0a3.4 3.4 0 1 0 -6.8 0M0 -6v2M0 4v2M-6 0h2M4 0h2",
};
const pill = (cls, text) => `<g class="jv-map__pill jv-map__pill--${cls}"><rect height="22" rx="11"/><path class="jv-map__pill-mark" d="${MARK[cls]}"/><text dominant-baseline="central">${esc(text)}</text></g>`;
/** The label block: name, then any tags. Laid out in unscaled units around (0, 0); life.js scales it. */
function tag(spot, name, pills, extra = "") {
  // up to two tags a row; a third (the "Jarvis" tag beside two others) starts a second row
  const rows = pills.length > 2 ? [pills.slice(0, 2), pills.slice(2)] : pills.length ? [pills] : [];
  const above = spot.above, n = rows.length, lift = Math.max(0, n - 1) * 26;
  const nameY = above ? (n ? -30 - lift : -2) : n ? -4 : 5;
  const rowY = (k) => (above ? -11 - (n - 1 - k) * 26 : 16 + k * 26);
  return `<g class="jv-map__tag" data-x="${f(spot.x)}" data-y="${f(spot.y)}" data-anchor="${spot.anchor}" transform="translate(${f(spot.x)} ${f(spot.y)})"${extra}>
    <text class="jv-map__name" y="${nameY}" text-anchor="${spot.anchor}">${esc(name)}</text>
    ${rows.map((row, k) => `<g class="jv-map__pills" transform="translate(0 ${rowY(k)})">${row.join("")}</g>`).join("")}</g>`;
}

const deg = (ux, uy) => (Math.atan2(uy, ux) * 180) / Math.PI;
function leafShape(L, cls = "jv-map__leaf") {
  const p = leafPaths(L, FAT);
  return `<g class="${cls}"><path class="jv-map__leaf-ring" d="${p.body}"/><path class="jv-map__leaf-body" d="${p.body}"/><path class="jv-map__leaf-light" d="${p.light}"/><path class="jv-map__leaf-rib" d="${p.rib}"/></g>`;
}

/** The Night mark: an ice ring at the leaf's middle (bigger with activity), a circular due arc around it, and for the
 *  branch Jarvis is on a reticle (four ticks). Hidden in Daylight. */
function markSvg(b, x, y, L, { fill = 0, due = false, jarvis = false, word = "" } = {}) {
  const r = f(L * 0.2 + 4), R = f(L * 0.2 + 10), c = `translate(${f(x)} ${f(y)})`;
  // the count (a number, big) or the glyph (letters, smaller), centred in the core
  const text = word ? `<text class="jv-map__mark-word${/^\d+$/.test(word) ? " jv-map__mark-word--count" : ""}" text-anchor="middle" dominant-baseline="central" aria-hidden="true">${esc(word)}</text>` : "";
  const ticks = jarvis ? (() => { const a = L * 0.2 + 13, z = a + 6; return `<path class="jv-map__reticle" d="M0 ${f(-z)}V${f(-a)}M0 ${f(a)}V${f(z)}M${f(-z)} 0H${f(-a)}M${f(a)} 0H${f(z)}"/>`; })() : "";
  return `<g class="jv-map__mark" transform="${c}"><circle class="jv-map__mark-ring" r="${R}"/><circle class="jv-map__mark-core" r="${r}"/>
    ${due ? `<circle class="jv-map__mark-due" r="${R}" pathLength="100" stroke-dasharray="${f(fill * 100)} 100" transform="rotate(-90)"/>` : ""}${ticks}${text}</g>`;
}

export function nodeSvg(item, { selected = false, privateScreen = false, plants = true, jarvis = false } = {}) {
  const b = item.branch, L = LEAF[b.activity || 0], { x, y, ux, uy } = item;
  const hidden = b.tier === 2 && privateScreen;
  const soon = b.due && b.due.hours <= 72;
  const fill = b.due ? Math.max(0.08, Math.min(1, 1 - b.due.hours / 336)) : 0;
  const cls = ["jv-map__node", `jv-map__node--${b.status}`, selected ? "jv-map__node--selected" : "", soon ? "jv-map__node--soon" : "", jarvis ? "jv-map__node--jarvis" : ""].join(" ");
  const halo = leafPaths(L * 1.3, FAT * 1.12).body;
  const pills = [
    soon && !hidden ? pill("soon", `Due ${b.due.label}`) : "",
    b.pending && !hidden ? pill("yes", `${b.pending} waiting`) : "",
    b.status === "proposed" ? pill("quiet", "Proposed") : "",
    jarvis && !hidden ? pill("jarvis", "Jarvis") : "",
  ].filter(Boolean);
  const mid = [x + ux * L * 0.5, y + uy * L * 0.5];
  const label = hidden ? "Private branch" : nodeLabel(b, jarvis);
  return `<a class="${cls}" href="#/life/${esc(b.id)}" data-id="${esc(b.id)}" data-nav="/life/${esc(b.id)}" aria-label="${esc(label)}">
    <title>${esc(hidden ? "Private" : nodeLabel(b, jarvis))}</title>
    ${markSvg(b, mid[0], mid[1], L, { fill, due: !!b.due && !hidden, jarvis: jarvis && !hidden, word: b.tier === 2 ? "" : markWord(b) })}
    <g transform="translate(${f(x)} ${f(y)}) rotate(${f(deg(ux, uy))})">
      ${b.due && !hidden ? `<path class="jv-map__due-track" transform="translate(${f(-L * 0.15)} 0)" d="${halo}"/><path class="jv-map__due" pathLength="100" stroke-dasharray="${f(fill * 100)} 100" transform="translate(${f(-L * 0.15)} 0)" d="${halo}"/>` : ""}
      ${plants ? leafShape(L) : `<ellipse class="jv-map__disc" cx="${f(L / 2)}" rx="${f(L / 2)}" ry="${f(L * 0.3)}"/>`}
    </g>
    ${b.tier === 2 ? `<path class="jv-map__lock" transform="translate(${f(mid[0])} ${f(mid[1])})" d="M-5.5 -1h11v8h-11zM-3.5 -1v-2.5a3.5 3.5 0 0 1 7 0v2.5"/>` : ""}
    ${tag(tagSpot(item, L), hidden ? "Private" : short(b.name), pills)}
  </a>`;
}

/** A leaflet on a stem: one branch inside the node at its end. Decorative; the node's label carries it. */
export function dotSvg(dot) {
  const b = dot.branch, L = 15 + (b.activity || 0) * 3, p = leafPaths(L, 0.4);
  return `<g class="jv-map__dot" transform="translate(${dot.x} ${dot.y}) rotate(${dot.angle})"><title>${esc(b.tier === 2 ? "Private" : b.name)}</title><path class="jv-map__leaflet" d="${p.body}"/></g>`;
}

export function moreSvg(more) {
  const L = LEAF[0];
  return `<a class="jv-map__node jv-map__node--more" href="#/life" data-more="1" aria-label="${more.count} more branches. Show them as a list">
    <g transform="translate(${f(more.x)} ${f(more.y)}) rotate(${f(deg(more.ux, more.uy))})">${leafShape(L)}</g>
    ${markSvg(null, more.x + more.ux * L * 0.5, more.y + more.uy * L * 0.5, L, { word: `+${more.count}` })}
    ${tag(tagSpot(more, L), `+${more.count} more`, [])}</a>`;
}

/** The focus: a pot of soil the stems grow out of, with its name under it. Earth and green, never the orb. */
export function centreSvg(focus) {
  const name = focus.kind === "root" ? "Your life" : short(focus.name, 22);
  const pills = [focus.due && focus.due.hours <= 72 ? pill("soon", `Due ${focus.due.label}`) : "", focus.pending ? pill("yes", `${focus.pending} waiting`) : ""].filter(Boolean);
  return `<g class="jv-map__centre" aria-hidden="true">
    <ellipse class="jv-map__shade" cx="0" cy="${POT_Y + 100}" rx="90" ry="9"/>
    <ellipse class="jv-map__soil" cx="0" cy="${POT_Y}" rx="66" ry="8"/>
    ${pot(0, POT_Y - 2, 136, 100, 96).replace(/jv-plant__/g, "jv-map__")}
    <g class="jv-map__core" transform="translate(0 ${POT_Y + 42})"><circle class="jv-map__core-halo" r="58"/><circle class="jv-map__core-ring" r="46"/>
      <circle class="jv-map__core-dots" r="36"/><circle class="jv-map__core-in" r="22"/><path class="jv-map__core-ticks" d="M0 -58v8M0 50v8M-58 0h8M50 0h8"/>
      ${focus.counts?.due ? `<text class="jv-map__mark-word jv-map__mark-word--count" text-anchor="middle" dominant-baseline="central">${esc(String(focus.counts.due))}</text>` : ""}</g>
    ${tag({ x: 0, y: POT_Y + 128, anchor: "middle", above: false }, name, pills, ' data-centre="1"').replace("jv-map__name", "jv-map__name jv-map__centre-name")}</g>`;
}
