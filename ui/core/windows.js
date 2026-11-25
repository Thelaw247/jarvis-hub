// The window manager for HUD windows (WINDOWS_RESEARCH §2.1, HUB_TRUST §2a). Pure functions, so they
// are easy to test; the Now view (grid) and the Stage (collage) draw what they return.
//  - the Stage and the hub's canvas with windows up (HUD v3 §14.2): cluster() lays small glass panels out as one
//    aligned cluster left of the docked orb (three width tiers by content, a 16 px gutter, masonry columns on a
//    shared top baseline, media large in the centre, the cluster centred; overlapping only when crowded, never
//    over the orb or the bottom row; the window Jarvis means on top; windows keep their spots when another
//    arrives); panelWidth(), tierOf() and roleOf() size and sort them
//  - on the hub ("On the hub"): a 12-column grid, at most 6 on screen counting the Now card; the window Jarvis is talking about (the
//    newest) is placed first, then anything waiting for a yes, then the rest in the order they came
//  - the rows fit the screen: when they don't, older windows get smaller (never below MIN_SIZE for their
//    kind), then the Now card, then the oldest unpinned windows step aside, so the canvas never scrolls; the
//    canvas then measures what each window holds and steps one more aside if something still can't fit
//  - a window docks into its Rail slot 60 s after it was last used unless pinned ("keep that up")
//  - nothing gets away (HUD v2 §6.2): stepping aside, the 60 s lifetime, a sixth window, "close that" and
//    CLEAR VIEW all **dock** the thing into its Rail slot; only done or archive removes it; moves are a real
//    reorder (`order`), never close + push
//  - nothing is pushed to a screen others can see, and never tier-2 items
//  - the same commands by voice, keyboard or button
//  - a layout can be saved to a branch and brought back (rebuilt from data, not screenshots)
import { windowKind } from "./window-kinds.js";
import { MAX_PUSHED, MAX_WINDOWS, placeWindow } from "./windows-core.js";

export { MAX_PUSHED, MAX_WINDOWS, placeWindow };
export const COLUMNS = 12;
export const LIFETIME_MS = 60_000;
export const SIZES = ["1x1", "2x1", "1x2", "2x2", "3x2", "4x2"];
const SPAN = { "1x1": [3, 1], "2x1": [6, 1], "1x2": [3, 2], "2x2": [6, 2], "3x2": [9, 2], "4x2": [12, 2] };
const GROW = ["1x1", "2x1", "1x2", "2x2", "3x2", "4x2"];

/** Default size for each window type when the push doesn't say. */
export const DEFAULT_SIZE = { branch_card: "1x2", countdown: "1x1", next_up: "1x1", timeline: "2x2", file: "2x2", fact: "2x1", approval: "2x2", timer: "1x1", chart: "2x1", unsorted: "2x1", notice: "2x1" };
export const sizeOf = (w) => (SPAN[w.size] ? w.size : DEFAULT_SIZE[w.type] || windowKind(w.type)?.size || "1x1");

/** Where each window goes: first free spot scanning rows from the top-left. → [{ id, col, row, w, h }] (1-based) */
export function layout(windows, columns = COLUMNS) {
  const taken = [];  // taken[row][col] = true
  const free = (row, col, w, h) => {
    for (let r = row; r < row + h; r++) for (let c = col; c < col + w; c++) if (taken[r]?.[c]) return false;
    return true;
  };
  return windows.map((win) => {
    let [w, h] = SPAN[sizeOf(win)];
    w = Math.min(w, columns);
    for (let row = 0; ; row++) {
      for (let col = 0; col + w <= columns; col++) {
        if (!free(row, col, w, h)) continue;
        for (let r = row; r < row + h; r++) { taken[r] = taken[r] || []; for (let c = col; c < col + w; c++) taken[r][c] = true; }
        return { id: win.id, col: col + 1, row: row + 1, w, h };
      }
    }
  });
}

/** The pushed windows that go on screen, in placing order: the window Jarvis is talking about (the newest)
 *  first, then anything still waiting for his yes, then the rest in the order they came (so they keep their
 *  spots when a new one arrives). At most `limit`: the oldest unpinned ones that aren't asking are evicted
 *  (only an older hub sends more than five; the Now view docks them with reason "evicted").
 *  `waiting`: ids of pending approvals. → { list, lead, evicted } where lead is the newest window's id. */
export function onScreen(windows, { limit = MAX_PUSHED, waiting = new Set() } = {}) {
  const asks = (w) => w.type === "approval" && waiting.has(w.ref);
  let list = [...windows];
  const evicted = [];
  while (list.length > limit) {
    const victim = list.find((w) => !w.pinned && !asks(w)) || list.find((w) => !w.pinned) || list[0];
    list = list.filter((w) => w !== victim);
    evicted.push(victim.id);
  }
  const lead = list.at(-1);
  const rest = list.slice(0, -1);
  return { list: lead ? [lead, ...rest.filter(asks), ...rest.filter((w) => !asks(w))] : [], lead: lead?.id, evicted };
}

const SMALLER = { "4x2": "3x2", "3x2": "2x2", "2x2": "2x1", "2x1": "1x1", "1x2": "1x1" };
// The smallest each kind of window may be made before its content no longer fits (film review M2): below
// this it steps aside into its Rail slot instead of being cut. A branch card is a tall column, a file needs
// room for its picture, a question needs room for what a yes would do.
export const MIN_SIZE = { branch_card: "1x2", file: "2x1", timeline: "2x1", approval: "2x1" };

/** Fit panels into `maxRows` rows of the grid, in the order given. Each panel may carry
 *  `level` (0 ordinary window, 1 the Now card, 2 the window Jarvis means or a question; default 0) and
 *  `rank` (higher = newer or more important; default its position). While the rows run past `maxRows`:
 *  ordinary windows get one step smaller at a time, oldest first; then the Now card; then the oldest unpinned
 *  ordinary windows step aside; last of all the level-2 ones get smaller.
 *  → { spots, rows, sizes: Map(id → size), left: [ids that stepped aside: the Now view docks them, reason "aside"] } */
export function arrange(panels, { columns = COLUMNS, maxRows = Infinity } = {}) {
  let items = panels.map((p, i) => ({ ...p, size: sizeOf(p), rank: p.rank ?? i, level: p.level ?? 0 }));
  const left = [];
  let out;
  const rowsOf = (spots) => spots.reduce((n, s) => Math.max(n, s.row + s.h - 1), 0);
  const fits = () => {
    let spots = layout(items, columns), rows = rowsOf(spots);
    // first-fit packs in placing order; when that runs long, the tall windows (two rows) placed first, after
    // the one that leads, often pack tighter (the order on screen and for the keyboard stays the same)
    if (rows > maxRows && items.length > 2) {
      const tall = (p) => (SPAN[p.size]?.[1] || 1) > 1;
      const alt = layout([items[0], ...items.slice(1).filter(tall), ...items.slice(1).filter((p) => !tall(p))], columns), altRows = rowsOf(alt);
      if (altRows < rows) { spots = items.map((p) => alt.find((a) => a.id === p.id)); rows = altRows; }
    }
    out = { spots, rows };
    return out.rows <= maxRows;
  };
  const byRank = (level) => items.filter((p) => p.level === level).sort((a, b) => a.rank - b.rank);
  const shrink = (level) => {
    for (let changed = true; changed;) {
      changed = false;
      for (const p of byRank(level)) {
        if (!SMALLER[p.size] || p.size === MIN_SIZE[p.type]) continue;
        p.size = SMALLER[p.size];
        changed = true;
        if (fits()) return true;
      }
    }
    return false;
  };
  const drop = () => {
    for (const p of byRank(0).filter((x) => !x.pinned)) {
      items = items.filter((x) => x !== p);
      left.push(p.id);
      if (fits()) return true;
    }
    return false;
  };
  if (!fits()) shrink(0) || shrink(1) || drop() || shrink(2);
  // free cells go first to the window Jarvis means and questions, then newer windows, the Now card last
  const first = [...items].sort((a, b) => (a.level === 1) - (b.level === 1) || b.level - a.level || b.rank - a.rank).map((p) => p.id);
  return { spots: stretch(out.spots, out.rows, columns, first), rows: out.rows, sizes: new Map(items.map((p) => [p.id, p.size])), left };
}

/** Let windows grow into free cells below them, then beside them, so nothing is cut short while the screen
 *  has empty space (the rows themselves stay as they are). */
function stretch(spots, rows, columns, priority) {
  const taken = new Set();
  const key = (r, c) => r * columns + c;
  spots.forEach((s) => { for (let r = s.row; r < s.row + s.h; r++) for (let c = s.col; c < s.col + s.w; c++) taken.add(key(r, c)); });
  const free = (cells) => cells.every(([r, c]) => !taken.has(key(r, c)));
  const range = (from, n) => Array.from({ length: n }, (_, i) => from + i);
  const grown = new Map();
  for (const id of priority) {
    const spot = spots.find((p) => p.id === id);
    if (!spot) continue;
    const s = { ...spot };
    while (s.row + s.h <= rows && free(range(s.col, s.w).map((c) => [s.row + s.h, c]))) { range(s.col, s.w).forEach((c) => taken.add(key(s.row + s.h, c))); s.h++; }
    while (s.col + s.w <= columns && free(range(s.row, s.h).map((r) => [r, s.col + s.w]))) { range(s.row, s.h).forEach((r) => taken.add(key(r, s.col + s.w))); s.w++; }
    grown.set(id, s);
  }
  return spots.map((p) => grown.get(p.id) || p);
}

// ---- HUD v3 aligned cluster (the Stage and the hub's canvas; HUD v2 §14.2) --------------------------------
// Huw's board reads as one aligned cluster, not a scatter: three width tiers, a 16 px gutter, columns that share
// one top baseline with short windows stacked under their neighbours (masonry, so no holes), the media window
// large in the centre column, and the whole cluster centred in the room left of the docked orb. Nothing is
// pinned to a far corner. Windows overlap only when the screen is crowded (a column closes up), never over the
// orb or the bottom row, and the window Jarvis means is drawn on top.

/** What each kind of window leads with (§14.2: exactly one hero): media (a picture: edge to edge), chart, number
 *  or title. A file without a picture leads with its title. */
export const ROLE = { file: "media", chart: "chart", countdown: "number", timer: "number" };
export const roleOf = (win, { picture = true } = {}) => (win.type === "file" && !picture ? "title" : ROLE[win.type] || windowKind(win.type)?.role || "title");

/** The three width tiers at 1920 px (the Stage screen), before scaling to the screen, and the gutter. */
export const TIER = { S: 300, M: 440, L: 600 };
export const GUTTER = 16;
/** Tiers go by content: one number or a short title is small; a sentence, a chart or a question is medium; media
 *  (a page, a slide, a video frame) is large. `short`: the window's title and line are only a few words. */
export const TIER_OF = { countdown: "S", timer: "S", next_up: "M", file: "M", chart: "M", branch_card: "M", approval: "M", timeline: "M", fact: "M", unsorted: "M", notice: "M" };
export const tierOf = (win, { picture = false, short = false } = {}) =>
  (win.type === "file" && picture ? "L" : windowKind(win.type)?.tier  // a registered kind (core/window-kinds.js) names its own tier
    || (short && win.type !== "chart" && win.type !== "approval" ? "S" : TIER_OF[win.type] || "M"));
const REF_WIDTH = 1840;  // the board's room at 1920 × 1080

/** The panel width for a window on a board `areaWidth` px wide: its tier, scaled to the screen (1440: 225, 330, 450). */
export function panelWidth(win, areaWidth, opts) {
  const f = Math.min(1.2, Math.max(0.75, areaWidth / REF_WIDTH));
  return Math.round(Math.min(TIER[tierOf(win, opts)] * f, areaWidth));
}

/** Lay panels out as one aligned cluster. Pure: the canvas measures the panels and the room, this decides.
 *  panels: [{ id, w, h, centre?, prev?: { x, y } }] in placing order: the first is the window Jarvis means (drawn
 *    on top). `centre`: media, which leads the centre column. `prev` is where its top-left corner stood last time,
 *    so windows stay put when another arrives: the new one takes the nearest aligned spot beside the cluster (under
 *    a column, or a new column). When every panel is new (the first layout, TIDY, a resize, a window gone) the
 *    cluster is laid out afresh: columns on one top baseline, each window a footer and a gutter under the one
 *    above it, the columns as even as they can be, centred in the room.
 *  area: { left, top, right, bottom } the room; keepOut: rects nothing may touch (the docked orb, the Stage's
 *    words): the cluster stays left of the orb and clear of the rest. foot: the room under each panel for its footer.
 *  → [{ id, x, y, w, h, z, covered, col }]: z is higher on top; covered is the share of the panel under others. */
export function cluster(panels, { area, keepOut = [], foot = 28, gutter = GUTTER } = {}) {
  const mid = (area.left + area.right) / 2, low = (area.top + area.bottom) / 2;
  const bound = (onlyLow) => {
    let right = area.right;
    for (const k of keepOut) if (k.left > mid && k.bottom > area.top && k.top < area.bottom && (!onlyLow || k.bottom > low)) right = Math.min(right, k.left);
    return Math.max(area.left + 1, right);
  };
  const boxOf = (r) => ({ left: r.x, top: r.y, right: r.x + r.w, bottom: r.y + r.h + foot });
  const touches = (r) => keepOut.some((k) => { const b = boxOf(r); return b.left < k.right && k.left < b.right && b.top < k.bottom && k.top < b.bottom; });
  const rowGap = foot + gutter;

  const layout = (right) => {
    const room = { left: area.left, top: area.top, right, bottom: area.bottom };
    const W = room.right - room.left, H = Math.max(1, room.bottom - room.top);
    const items = panels.map((p, i) => ({ id: p.id, w: Math.max(1, Math.min(p.w, W)), h: Math.max(1, Math.min(p.h, H - foot)), prev: p.prev, centre: !!p.centre, i }));
    const hit = (a, b) => a.x < b.x + b.w + gutter && b.x < a.x + a.w + gutter && a.y < b.y + b.h + rowGap && b.y < a.y + a.h + rowGap;
    const inside = (r) => r.x >= room.left - 0.5 && r.y >= room.top - 0.5 && r.x + r.w <= room.right + 0.5 && r.y + r.h + foot <= room.bottom + 0.5;

    /** A fresh cluster: masonry columns, media leading the centre one, as close to a 2:1 block as the room allows. */
    const fresh = () => {
      const media = items.filter((p) => p.centre), rest = items.filter((p) => !p.centre).sort((a, b) => b.h - a.h || a.i - b.i);
      let best = null;
      for (let k = 1; k <= Math.min(items.length, 6); k++) {
        const cols = Array.from({ length: k }, () => ({ items: [], w: 0, h: 0 }));
        const centre = Math.floor((k - 1) / 2);
        const add = (col, p) => { col.h += (col.items.length ? gutter : 0) + p.h + foot; col.w = Math.max(col.w, p.w); col.items.push(p); };
        media.forEach((p) => add(cols[centre], p));
        for (const p of rest) {  // into the shortest column; a tie goes to the one nearest the centre
          let to = 0;
          cols.forEach((c, j) => { if (c.h < cols[to].h - 0.5 || (Math.abs(c.h - cols[to].h) <= 0.5 && Math.abs(j - centre) < Math.abs(to - centre))) to = j; });
          add(cols[to], p);
        }
        if (cols.some((c) => !c.items.length)) continue;
        const w = cols.reduce((n, c) => n + c.w, 0) + (k - 1) * gutter, h = Math.max(...cols.map((c) => c.h)), least = Math.min(...cols.map((c) => c.h));
        if (w > W + 0.5 && k > 1) continue;
        const fits = h <= H;
        // media belongs in the middle: with media up, prefer an odd number of columns (three or more) when they fit
        const offCentre = media.length && items.length >= 3 && (k < 3 || k % 2 === 0) ? 1.2 : 0;
        const score = fits ? Math.abs(Math.log(w / h / 2)) + 0.8 * (h - least) / h + offCentre : 1000 + h;
        if (!best || score < best.score - 1e-9) best = { cols, w, h, score, fits };
      }
      const x0 = Math.round(room.left + (W - Math.min(best.w, W)) / 2), y0 = Math.round(best.fits ? room.top + (H - best.h) / 2 : room.top);
      const out = [];
      let x = x0;
      best.cols.forEach((col, c) => {
        // media first, then the window Jarvis means, then the rest as they were placed
        col.items.sort((a, b) => b.centre - a.centre || a.i - b.i);
        // crowded: this column closes up evenly, each lower window over the foot of the one above
        const close = col.h > H && col.items.length > 1 ? (col.h - H) / (col.items.length - 1) : 0;
        let y = y0;
        // columns left of the middle hug it (their windows share the right edge); the rest share the left edge
        const hug = c < (best.cols.length - 1) / 2;
        col.items.forEach((p, n) => { out.push({ ...p, x: hug ? x + col.w - p.w : x, y: Math.round(y), col: c, n }); y += p.h + foot + gutter - close; });
        x += col.w + gutter;
      });
      return out;
    };

    /** Everything stays where it stood; each new panel takes an aligned spot beside the cluster. Null when a held
     *  panel no longer fits the room or a new one finds no spot (then the cluster is laid out afresh). */
    const beside = () => {
      const placed = [];
      for (const p of items.filter((q) => q.prev)) {
        const r = { ...p, x: Math.round(p.prev.x), y: Math.round(p.prev.y) };
        if (!inside(r)) return null;
        placed.push(r);
      }
      for (const p of items.filter((q) => !q.prev)) {
        const top = Math.min(...placed.map((q) => q.y)), left = Math.min(...placed.map((q) => q.x));
        // under each window that has nothing below it (on its left edge, and on its right edge)
        const spots = placed.flatMap((q) => [{ x: q.x, y: q.y + q.h + rowGap }, { x: q.x + q.w - p.w, y: q.y + q.h + rowGap }]);
        spots.push({ x: Math.max(...placed.map((q) => q.x + q.w)) + gutter, y: top }, { x: left - gutter - p.w, y: top });  // a new column, right then left
        const free = spots.map((s) => ({ ...p, ...s })).filter((r) => inside(r) && !placed.some((q) => hit(r, q)));
        if (!free.length) return null;
        // the spot that keeps the cluster nearest the middle of the room
        const cx = room.left + W / 2, cy = room.top + H / 2;
        const off = (r) => {
          const all = [...placed, r];
          const l = Math.min(...all.map((q) => q.x)), rr = Math.max(...all.map((q) => q.x + q.w)), t = Math.min(...all.map((q) => q.y)), b = Math.max(...all.map((q) => q.y + q.h));
          return Math.abs((l + rr) / 2 - cx) + Math.abs((t + b) / 2 - cy);
        };
        placed.push(free.reduce((a, b) => (off(b) < off(a) - 1e-9 ? b : a)));
      }
      const above = (q) => placed.filter((o) => o !== q && o.y < q.y && o.x < q.x + q.w && q.x < o.x + o.w).length;
      const lefts = [...new Set(placed.filter((q) => !above(q)).map((q) => q.x))].sort((a, b) => a - b);
      return placed.map((q) => ({ ...q, col: Math.max(0, lefts.findLastIndex((x) => x <= q.x + q.w / 2)), n: above(q) }));
    };
    return (items.some((p) => p.prev) && beside()) || fresh();
  };

  // left of the docked orb; if that puts a panel under the Stage's words (top right), left of those too
  let spots = layout(bound(true));
  if (spots.some(touches)) spots = layout(bound(false));
  // on top: the window Jarvis means, then lower windows over the ones above them in a column (their kickers stay whole)
  const depth = Math.max(0, ...spots.map((s) => s.n)) + 1;
  for (const s of spots) s.z = s.i === 0 ? depth + 1 : s.n + 1;
  const over = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h + foot, b.y + b.h + foot) - Math.max(a.y, b.y));
  return spots.sort((a, b) => a.i - b.i).map((s) => {
    const under = spots.reduce((n, q) => (q !== s && q.z > s.z ? n + over(s, q) : n), 0);
    return { id: s.id, x: s.x, y: s.y, w: s.w, h: s.h, z: s.z, col: s.col, covered: Math.round(Math.min(1, under / (s.w * (s.h + foot))) * 100) / 100 };
  });
}

/** IDs of windows whose 60 s are up (they dock, reason "lifetime"). lastUsed: Map(id → ms); a window with no
 *  entry counts from `pushedAt`. */
export function expired(windows, now, lastUsed, pushedAt = new Map()) {
  return windows.filter((w) => !w.pinned && now - (lastUsed.get(w.id) ?? pushedAt.get(w.id) ?? now) >= LIFETIME_MS).map((w) => w.id);
}

/** Which windows this screen may show: none of tier 2 on the ambient screen, nothing new when others are present. */
export function visible(windows, { presence = {}, size = "full" } = {}) {
  const shared = size === "ambient" || presence.others;
  return windows.filter((w) => !(shared && w.tier === 2) && !(presence.others && size === "ambient"));
}

/** "Bigger": the next size up that is at least as wide and at least as tall, so a window never gets shorter. */
export function nextSize(size) {
  const from = SPAN[size] ? size : "1x1", [w, h] = SPAN[from];
  return GROW.slice(GROW.indexOf(from) + 1).find((s) => SPAN[s][0] >= w && SPAN[s][1] >= h) || from;
}

/** Turn a spoken or typed command into an action. `active` is the window being talked about (the newest).
 *  "Close that" docks (it waits on the Rail); "done with that" / "archive that" is the one that removes.
 *  → { action, target, args } or null when it isn't a window command. */
export function command(text, windows, activeId) {
  const t = String(text || "").toLowerCase().trim().replace(/[.!?]+$/, "");
  const active = activeId || windows[windows.length - 1]?.id;
  const named = windows.find((w) => t.includes(String(w.title).toLowerCase()))?.id;
  const target = named || active;
  if (/^(close all|close everything|clear( the)? (screen|view)|clear view)$/.test(t)) return { action: "close_all", target: "all" };
  if (/^(mark (it )?all (as )?seen|i've seen (it all|everything))$/.test(t)) return { action: "seen", target: "all" };
  if (!target) return null;
  if (/^close( that| it| this)?$/.test(t) || (named && t.startsWith("close "))) return { action: "dock", target, args: { reason: "closed" } };
  if (/^(done with (that|it|this)|archive (that|it|this))$/.test(t) || (named && /^(archive|done with) /.test(t))) {
    const w = windows.find((x) => x.id === target);
    return { action: "archive", target: w?.ref || target };
  }
  if (/^(keep that up|keep it up|pin that|pin it|pin this)$/.test(t) || (named && /^(pin|keep) /.test(t))) return { action: "pin", target };
  if (/^(unpin that|unpin it|let that go)$/.test(t)) return { action: "unpin", target };
  if (/^(bigger|make (that|it) bigger|enlarge)$/.test(t)) return { action: "resize", target, args: { size: nextSize(sizeOf(windows.find((w) => w.id === target))) } };
  if (/^(full ?screen)$/.test(t)) return { action: "resize", target, args: { size: "4x2" } };
  const side = t.match(/^put (?:the |that |it )?(.*?) ?on the (left|right)$/);
  if (side) return { action: "move", target, args: { to: side[2] } };
  return null;
}

// ---- saved layouts: stored per branch as window descriptions (type, ref, size), rebuilt from data later ----
const KEY = "jarvis.layouts.v1";
const read = (storage) => { try { return JSON.parse(storage.getItem(KEY) || "{}"); } catch { return {}; } };

export function saveLayout(branchId, windows, storage = localStorage) {
  const all = read(storage);
  all[branchId] = windows.filter((w) => w.tier !== 2).map(({ id, type, title, ref, size, data }) => ({ id, type, title, ref, size, data }));
  storage.setItem(KEY, JSON.stringify(all));
  return all[branchId].length;
}
export function savedLayout(branchId, storage = localStorage) { return read(storage)[branchId] || []; }
export function restoreLayout(branchId, storage = localStorage) {
  return savedLayout(branchId, storage).reduce((list, w) => placeWindow(list, { ...w, pinned: true }), []);
}

/** Tracks when each window was last used and docks the ones whose time is up: `dock(id)` is called for each
 *  (core/presence.js sends the `dock` action with reason "lifetime"; nothing is ever deleted by the clock). */
export class WindowClock {
  constructor(dock, now = () => performance.now()) { this.dock = dock; this.now = now; this.used = new Map(); this.pushed = new Map(); this.kept = new Set(); }
  /** A window he placed or sized by hand stays until he closes it or lets it go (v0.17.0): he arranged it. */
  keep(id, on = true) { if (on) this.kept.add(id); else this.kept.delete(id); }
  seen(windows) {
    const ids = new Set(windows.map((w) => w.id));
    for (const w of windows) if (!this.pushed.has(w.id)) this.pushed.set(w.id, this.now());
    for (const id of [...this.pushed.keys()]) if (!ids.has(id)) { this.pushed.delete(id); this.used.delete(id); }
  }
  touch(id) { this.used.set(id, this.now()); }
  tick(windows) {
    this.seen(windows);
    for (const id of [...this.kept]) if (!this.pushed.has(id)) this.kept.delete(id);
    const gone = expired(windows.filter((w) => !this.kept.has(w.id)), this.now(), this.used, this.pushed);
    gone.forEach((id) => this.dock(id));
    return gone;
  }
}
