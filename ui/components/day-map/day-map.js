// <jv-day-map .map=${window.data} .now=${Date} tiles="on|off"> — the map window's hero (R2, REACH §5.2): today's
// places on campus with the route between them, in the HUD palette: dark land, faint roads, an ice route, the
// pin it leads with brighter and the only one labelled. Under it, one supporting line ("Next: CHEM 142 lab 4 ·
// Thorvaldson 173 · 1:30 pm").
//  - Leads with `map.focus` (what he asked about) or else the next stop by the clock.
//  - Draws at once from bundled vector data (campus.js): a hand-made, labelled schematic ("Schematic ·
//    approximate"), never presented as an accurate map. Map tiles (CARTO's dark or light basemap without labels,
//    © OpenStreetMap contributors © CARTO) go on top only when they can load: online, against the live hub, and
//    never under automation (tests and screenshots always see the schematic). They show all at once when every
//    tile has arrived (cached tiles: a few ms); one failing tile keeps the schematic and stops trying for 5 min.
//  - Tile use stays polite: one zoom level, the same URL for the same tile every time (so the browser's HTTP
//    cache answers), ≤ ~24 tiles per draw, no panning, no prefetching.
//  - No buttons, no continuous animation; role="img" with the whole day in its label.
// Also registers the `map` window kind (core/window-kinds.js) and its scenes.
import { css } from "../../core/dom.js";
import { bridge } from "../../core/bridge.js";
import { el, params, registerGallery, registerScene, sceneName } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { registerWindowKind } from "../../core/window-kinds.js";
import { CAMPUS } from "./campus.js";

css(import.meta.url);

export const VIEW = { width: 600, height: 360 };  // the map's own units (5:3); it scales with the panel
const TILE = 256;
const PAD = 52;  // room around the pins (the label sits beside the one it leads with)
const MAX_ZOOM = 17;
const TILE_URL = "https://{s}.basemaps.cartocdn.com/{style}/{z}/{x}/{y}{r}.png";
export const CREDIT_TILES = "© OpenStreetMap contributors © CARTO";
export const CREDIT_SCHEMATIC = "Schematic · approximate";
const RETRY_MS = 5 * 60_000;
let failedAt = -Infinity;  // the last time a tile failed: don't keep asking a server we can't reach

// ---- pure helpers (tests import these) -----------------------------------------------------------------------
/** Web Mercator: world pixels at zoom 0 (a 256 px world). */
export function project(lat, lon) {
  const s = Math.sin((lat * Math.PI) / 180);
  return [((lon + 180) / 360) * TILE, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TILE];
}

/** The view that fits every point: a whole tile zoom `z` drawn at `scale` (≤ 1, so tiles are never blown up),
 *  and a function from lat/lon to view units. → { z, scale, ox, oy, at(lat, lon) → [x, y] } */
export function frame(points, { width = VIEW.width, height = VIEW.height, pad = PAD, maxZoom = MAX_ZOOM } = {}) {
  const xy = points.map((p) => project(p.lat, p.lon));
  const xs = xy.map((p) => p[0]), ys = xy.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const fit = Math.min(Math.log2((width - 2 * pad) / Math.max(x1 - x0, 1e-9)), Math.log2((height - 2 * pad) / Math.max(y1 - y0, 1e-9)));
  const z = Math.max(0, Math.min(maxZoom, Math.ceil(fit)));
  const k = 2 ** Math.min(fit, z);  // world px at zoom 0 → view units
  const scale = k / 2 ** z;
  const ox = ((x0 + x1) / 2) * k - width / 2, oy = ((y0 + y1) / 2) * k - height / 2;
  return { z, scale, ox, oy, width, height, at: (lat, lon) => { const [x, y] = project(lat, lon); return [x * k - ox, y * k - oy]; } };
}

/** The tiles that cover the view, with where each sits (view units). → [{ x, y, left, top, size }] */
export function tilesFor(view) {
  const size = TILE * view.scale, n = 2 ** view.z, out = [];
  for (let ty = Math.floor(view.oy / size); ty * size < view.oy + view.height; ty++) {
    if (ty < 0 || ty >= n) continue;
    for (let tx = Math.floor(view.ox / size); tx * size < view.ox + view.width; tx++) out.push({ x: ((tx % n) + n) % n, y: ty, left: tx * size - view.ox, top: ty * size - view.oy, size });
  }
  return out;
}

/** A tile's URL: the same subdomain for the same tile every time, so the HTTP cache answers. */
export function tileUrl({ x, y }, z, { theme = "night", retina = false } = {}) {
  return TILE_URL.replace("{s}", "abcd"[(x + y) % 4]).replace("{style}", theme === "day" ? "light_nolabels" : "dark_nolabels")
    .replace("{z}", z).replace("{x}", x).replace("{y}", y).replace("{r}", retina ? "@2x" : "");
}

const minutes = (hhmm) => { const [h, m] = String(hhmm || "0:0").split(":").map(Number); return h * 60 + m; };
const clock = (hhmm) => { const m = minutes(hhmm), h = Math.floor(m / 60); return `${h % 12 || 12}:${String(m % 60).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`; };
const dayMinutes = (now) => now.getHours() * 60 + now.getMinutes();
const sameDay = (data, now) => !data.day || data.day === `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

/** What the map leads with. → { stop (or null when the day's stops are done), index (1-based), word: Next | Now |
 *  Earlier | Later, place (the place id the bright pin is on) } */
export function leadOf(data, now = new Date()) {
  const stops = data?.stops || [];
  const t = sameDay(data, now) ? dayMinutes(now) : -1;  // another day's map: nothing has happened yet
  const over = (s) => minutes(s.end || s.start) <= t;
  const nextIndex = stops.findIndex((s) => !over(s));
  const i = data?.focus ? stops.findIndex((s) => s.ref === data.focus) : nextIndex;
  if (i < 0) return { stop: null, index: 0, word: "Done", place: data?.start || null };
  const s = stops[i];
  const word = minutes(s.start) <= t && !over(s) ? "Now" : over(s) ? "Earlier" : i === nextIndex ? "Next" : "Later";
  return { stop: s, index: i + 1, word, place: s.place };
}

/** The one supporting line (≤ ~90 characters). */
export function lineOf(data, now = new Date()) {
  const { stop, word, place } = leadOf(data, now);
  if (!stop) return `Nothing else on campus today · ${data?.places?.find((p) => p.id === place)?.name || "home"}`;
  return `${word}: ${stop.title.split(" · ")[0]} · ${stop.where || ""} · ${clock(stop.start)}`.replace(" ·  · ", " · ");
}

/** The route: the place the day starts from, then each stop's place (a repeat is one point). → place ids */
export function routeOf(data) {
  const ids = [data?.start, ...(data?.stops || []).map((s) => s.place)].filter(Boolean);
  return ids.filter((id, i) => id !== ids[i - 1]);
}

/** Which side of its pin the label goes: the first of right, left, above, below that stays inside the view and
 *  clear of the route (estimated in view units: 12 px mono caps with tracking ≈ 8.6 per character). */
export function labelSide([x, y], chars, route, { width = VIEW.width, height = VIEW.height } = {}) {
  const w = chars * 8.6, h = 16, gap = 16;
  const boxes = { right: [x + gap, y - h / 2, x + gap + w, y + h / 2], left: [x - gap - w, y - h / 2, x - gap, y + h / 2],
    above: [x - w / 2, y - gap - h, x + w / 2, y - gap], below: [x - w / 2, y + gap, x + w / 2, y + gap + h] };
  const inside = ([l, t, r, b]) => l >= 4 && t >= 4 && r <= width - 4 && b <= height - 22;  // the credit sits bottom-right
  const crosses = ([l, t, r, b]) => route.slice(1).some(([x2, y2], i) => {
    const [x1, y1] = route[i], n = Math.max(2, Math.ceil(Math.hypot(x2 - x1, y2 - y1) / 3));
    for (let k = 0; k <= n; k++) { const px = x1 + ((x2 - x1) * k) / n, py = y1 + ((y2 - y1) * k) / n; if (px >= l && px <= r && py >= t && py <= b) return true; }
    return false;
  });
  const sides = Object.keys(boxes);
  return sides.find((s) => inside(boxes[s]) && !crosses(boxes[s])) || sides.find((s) => inside(boxes[s])) || "right";
}

/** May this map ask for tiles? Never under automation (tests, screenshots) or in scenes, unless forced. */
export function tilesAllowed(node) {
  const forced = node?.getAttribute?.("tiles") ?? params.get("tiles");
  if (forced === "off") return false;
  if (forced === "on") return true;
  return navigator.onLine && !navigator.webdriver && bridge.mode === "server" && performance.now() - failedAt > RETRY_MS;
}

// ---- the element ---------------------------------------------------------------------------------------------
const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
const pts = (list) => list.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
const pct = (v, of) => `${((v / of) * 100).toFixed(3)}%`;

class MapView extends HTMLElement {
  set map(v) { this._map = v; if (this.isConnected) this.render(); }
  get map() { return this._map; }
  set now(v) { this._now = v; if (this.isConnected) this.render(); }
  get now() { return this._now || store.now(); }
  connectedCallback() { this.render(); }
  disconnectedCallback() { this._tiles?.forEach((img) => { img.onload = img.onerror = null; }); }

  render() {
    const data = this._map;
    if (!data?.places?.length) { this.replaceChildren(el("p", { className: "jv-muted", textContent: "No places to show today." })); return; }
    const t0 = performance.now();
    const now = this.now, places = new Map(data.places.map((p) => [p.id, p])), lead = leadOf(data, now);
    const view = frame(data.places);
    const { width: W, height: H } = view;
    const root = el("div", { className: "jv-day-map" });
    root.dataset.mode = "schematic";
    const box = el("div", { className: "jv-day-map__view" });
    box.style.aspectRatio = `${W} / ${H}`;

    // 1. the schematic (always drawn first: the first paint never waits for the network)
    const base = svg("svg", { class: "jv-day-map__schematic", viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true", preserveAspectRatio: "xMidYMid slice" });
    base.append(svg("rect", { class: "jv-day-map__land", x: 0, y: 0, width: W, height: H }));
    for (const r of CAMPUS.roads) base.append(svg("polyline", { class: "jv-day-map__road", points: pts(r.line.map(([la, lo]) => view.at(la, lo))) }));
    for (const g of CAMPUS.greens) base.append(svg("polygon", { class: "jv-day-map__green", points: pts(g.ring.map(([la, lo]) => view.at(la, lo))) }));
    for (const b of CAMPUS.buildings) base.append(svg("polygon", { class: "jv-day-map__building", points: pts(b.ring.map(([la, lo]) => view.at(la, lo))) }));
    box.append(base);

    // 2. map tiles on top, shown only once every one has loaded
    if (tilesAllowed(this)) box.append(...this.tileLayer(view));

    // 3. the route and the pins
    const over = svg("svg", { class: "jv-day-map__overlay", viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true", preserveAspectRatio: "xMidYMid slice" });
    const route = routeOf(data).filter((id) => places.has(id)).map((id) => view.at(places.get(id).lat, places.get(id).lon));
    if (route.length > 1) over.append(svg("polyline", { class: "jv-day-map__route", points: pts(route) }));
    // the leg into the place it leads with, a step brighter
    const ids = routeOf(data), legEnd = lead.stop ? ids.indexOf(lead.place, 1) : -1;
    if (legEnd > 0) over.append(svg("polyline", { class: "jv-day-map__route jv-day-map__route--lead", points: pts(route.slice(legEnd - 1, legEnd + 1)) }));
    for (const p of data.places) {
      const [x, y] = view.at(p.lat, p.lon), on = p.id === lead.place;
      const g = svg("g", { class: `jv-day-map__pin${on ? " jv-day-map__pin--lead" : ""}${p.home ? " jv-day-map__pin--home" : ""}`, transform: `translate(${x.toFixed(1)} ${y.toFixed(1)})` });
      g.dataset.place = p.id;
      if (on) g.append(svg("circle", { class: "jv-day-map__ring", r: 11 }));
      g.append(p.home ? svg("rect", { class: "jv-day-map__dot", x: -4.5, y: -4.5, width: 9, height: 9 }) : svg("circle", { class: "jv-day-map__dot", r: on ? 5.5 : 4 }));
      over.append(g);
    }
    box.append(over);

    // 4. the label, only on the pin it leads with (HTML, so it stays the same size at every panel width)
    const leadPlace = places.get(lead.place);
    if (leadPlace) {
      const [x, y] = view.at(leadPlace.lat, leadPlace.lon), text = leadPlace.short || leadPlace.name;
      const label = el("span", { className: "jv-day-map__label", textContent: text });
      label.style.left = pct(x, W);
      label.style.top = pct(y, H);
      label.dataset.side = labelSide([x, y], text.length, route, view);
      box.append(label);
    }
    box.append(el("p", { className: "jv-day-map__credit", textContent: CREDIT_SCHEMATIC }));
    root.append(box, el("p", { className: "jv-day-map__line", textContent: lineOf(data, now) }));

    const order = routeOf(data).map((id) => places.get(id)?.name).filter(Boolean);
    root.setAttribute("role", "img");
    root.setAttribute("aria-label", `Map of today on campus: ${order.join(", then ")}. ${lineOf(data, now)}.`);
    this.replaceChildren(root);
    this.root = root;
    this.dataset.drawMs = String(Math.round(performance.now() - t0));
  }

  /** The tile images (hidden until all have loaded) and the static tint that pulls them into the HUD palette. */
  tileLayer(view) {
    const theme = document.documentElement.dataset.theme === "day" ? "day" : "night";
    const layer = el("div", { className: "jv-day-map__tiles" });
    layer.hidden = true;
    const tiles = tilesFor(view), retina = devicePixelRatio > 1;
    let left = tiles.length;
    this._tiles = tiles.map((t) => {
      const img = el("img", { alt: "", decoding: "async", draggable: false });
      img.style.left = pct(t.left, view.width);
      img.style.top = pct(t.top, view.height);
      img.style.width = pct(t.size + 0.5, view.width);  // a hair of overlap: no seams between tiles
      img.style.height = pct(t.size + 0.5, view.height);
      img.onload = () => { if (--left === 0 && this.root?.dataset.mode !== "failed") this.showTiles(layer); };
      img.onerror = () => { failedAt = performance.now(); this.dropTiles(layer); };
      img.src = tileUrl(t, view.z, { theme, retina });
      layer.append(img);
      return img;
    });
    return [layer, el("div", { className: "jv-day-map__tint" }, { "aria-hidden": "true" })];
  }

  showTiles(layer) {
    if (!this.root) return;
    layer.hidden = false;
    this.root.dataset.mode = "tiles";
    this.root.querySelector(".jv-day-map__credit").textContent = CREDIT_TILES;
  }

  dropTiles(layer) {
    this._tiles?.forEach((img) => { img.onload = img.onerror = null; });
    layer.nextElementSibling?.remove();  // the tint
    layer.remove();
    if (this.root) { this.root.dataset.mode = "schematic"; this.root.querySelector(".jv-day-map__credit").textContent = CREDIT_SCHEMATIC; }
  }
}
if (!customElements.get("jv-day-map")) customElements.define("jv-day-map", MapView);

// ---- the `map` window kind -----------------------------------------------------------------------------------
registerWindowKind("map", {
  role: "media",  // the map fills the panel edge to edge
  width: 600,     // the L tier (HUD v2 §14.2)
  size: "2x2",    // on the hub's grid
  content: (win, _s, now) => el("jv-day-map", { map: win.data, now }),
  kicker: (win) => {
    const { stop, index } = leadOf(win.data, store.now());
    return { heading: "Map", status: "Today", index: stop ? `${index} / ${win.data.stops.length}` : "" };
  },
});

// ---- scenes --------------------------------------------------------------------------------------------------
// Scenes draw the contract example (contracts/examples/map.json: the demo day at 3:40 pm), fetched only in scene mode.
const EXAMPLE = sceneName ? await fetch("/contracts/examples/map.json", { cache: "no-store" }).then((r) => r.json()).catch(() => null) : null;
const D = "2026-11-16";
const mapWindow = (patch = {}) => ({ id: "w-map-today", type: "map", title: "Map", pushed: `${D}T15:40:20`, data: { ...structuredClone(EXAMPLE), ...patch } });
const at = (hhmm) => new Date(`${D}T${hhmm}:00`);
const sample = (data, now, attrs = {}) => {
  const w = el("jv-window", {}, { heading: "Map", status: "Today", index: leadOf(data, now).stop ? `${leadOf(data, now).index} / ${data.stops.length}` : "", meta: "Added 3:40 pm", "window-id": "w-map", media: true, opens: true, ...attrs });
  w.append(el("jv-day-map", { map: data, now }));
  return w;
};
if (EXAMPLE) {
  registerGallery("day-map", [
    { label: "Next: the lab (1:05 pm)", build: () => sample(EXAMPLE, at("13:05"), { active: true }) },
    { label: "Asked where the lab is (3:40 pm, after it)", build: () => sample({ ...EXAMPLE, focus: "d-chem" }, at("15:40")) },
    { label: "During the lab (2:10 pm)", build: () => sample(EXAMPLE, at("14:10")) },
    { label: "Next: back home (3:40 pm)", build: () => sample(EXAMPLE, at("15:40")) },
    { label: "Day done (9 pm)", build: () => sample(EXAMPLE, at("21:00")) },
  ], { about: "The map window: today's places on campus with the route, the pin it leads with brighter and the only one labelled, one line under it. Offline (and in every scene) it is a labelled schematic from bundled shapes, never presented as an accurate map.", columns: "600px" });
  const stage = (about, patch) => registerScene(about[0], { path: "/stage", about: about[1], patch });
  stage(["stage-map", "The map window on the Stage: the lab is next (1:05 pm)"], (s) => {
    s.now = `${D}T13:05:00`; s.windows = [{ ...mapWindow(), pushed: `${D}T13:05:00` }]; s.approvals = []; s.caption = null;
  });
  stage(["stage-map-asked", "“Show me where my lab is” at 3:40 pm: the map leads with the lab, among other windows"], (s) => {
    const due = s.windows.find((w) => w.type === "countdown") || { id: "w-due-pps7", type: "countdown", title: "Due", ref: "due-pps7" };
    s.windows = [due, mapWindow({ focus: "d-chem" })]; s.approvals = [];
    s.caption = { text: "CHEM 142 lab 4 is in Thorvaldson 173.", source: { kind: "jarvis", label: "Jarvis" }, ttl_ms: 600000 };
  });
}
