// The Core orb's geometry and markup (HUD v2 §4; research-huw-visuals §2, §6). Pure: no DOM, no store.
// Units: R (the core's radius) = 36; the whole orb is a 220-unit square centred on 0, so the motes at 2.95 R
// just fit. Each MOVING layer is its own small <svg> inside its own composited <div> (WebView2 can't move
// parts of one SVG on the GPU); moving layers have no filters, still layers carry the baked bloom.

export const R = 36;
export const BOX = 220;  // units across the orb's box
const f = (n) => Number(n.toFixed(2));

// The words for each state: the status line, the strip and screen readers use these. At rest Jarvis is
// "Listening" (for his name); "Hearing you" while he speaks.
export const ORB_WORDS = {
  idle: "Listening", listening: "Hearing you", thinking: "Thinking", speaking: "Speaking",
  waiting: "Waiting for your yes", muted: "Muted", offline: "Offline", standby: "Standby",
};
// Words for an alert on top of any state (shape + colour + word).
export const ALERT_WORDS = { warn: "Needs you", crit: "Critical" };
// The short word drawn on the orb itself (under the core) when it must say its state in words:
// reduced motion, muted, offline, alerts. Idle and standby say nothing; waiting says AWAITING YES in the core.
export const RING_WORDS = { listening: "Hearing you", thinking: "Thinking", speaking: "Speaking", muted: "Muted", offline: "Offline" };

// Every state the component takes: the contract's orb_state values, plus standby (the ambient screen) and
// alert (an alert with no other state). Unknown values fall back to idle.
export const STATES = ["standby", "idle", "listening", "thinking", "speaking", "waiting", "muted", "offline", "alert"];
export const LEVEL_STATES = new Set(["listening", "speaking"]);          // the energy ring follows a voice level
// v0.14.0: at rest the soft light follows the room too (his ask: brighter and dimmer with the sound around us)
export const AMBIENT_STATES = new Set(["idle", "thinking", "standby"]);
export const REST_STATES = new Set(["idle", "standby", "muted", "offline"]);  // → listening = a wake

/** Inset (in % of the orb's box) that makes a square layer of half-size `e` units, centred. */
const inset = (e) => `${f(50 - (e / BOX) * 100)}%`;

const svg = (e, body, cls = "") => `<svg class="jv-orb__svg ${cls}" viewBox="${-e} ${-e} ${2 * e} ${2 * e}" aria-hidden="true" focusable="false">${body}</svg>`;
/** A layer box: `e` half-size in units; `inner` is what goes in it (spinners, then an svg). */
const layer = (name, e, inner, { cls = "", k, delay } = {}) =>
  `<div class="jv-orb__L jv-orb__L--${name} ${cls}" style="inset:${inset(e)}${k != null ? `;--k:${k}` : ""}${delay != null ? `;--wd:${delay}ms` : ""}">${inner}</div>`;
const spin = (inner, extra = false) => `<div class="jv-orb__spin">${extra ? `<div class="jv-orb__spin2">${inner}</div>` : inner}</div>`;

/** Deterministic points: a small LCG so every orb (and every screenshot) draws the same particles. */
function ball(n, seed, radius) {
  let s = seed;
  const rnd = () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296);
  return Array.from({ length: n }, () => {  // a point inside a ball, seen from the front
    const a = rnd() * Math.PI * 2, c = rnd() * 2 - 1, r = radius * Math.cbrt(rnd()) * Math.sqrt(1 - c * c);
    return [f(r * Math.cos(a)), f(r * Math.sin(a))];
  });
}
const dotsPath = (pts) => pts.map(([x, y]) => `M${x} ${y}h0`).join("");

// the energy ring's band (inner edge, outer edge, middle, width) and where its outer glow ends
const EN_IN = 1.15 * R, EN_OUT = 1.42 * R, EN_MID = (EN_IN + EN_OUT) / 2, EN_GLOW = 4.6 * R;
/** The band's light, as [radius, opacity] stops: a tight bloom (falls by e every 0.14 R) plus a wide, faint tail
 *  (every 1 R) outside; a soft spill inward over 0.4 R; zero at both ends, so no edge shows anywhere. */
export function glowCurve() {
  // v0.6.1 (serious mode, his pick from the comparison page): a soft light hidden behind the core, in a muted
  // steel blue. It falls off smoothly from the centre and is gone by about 3 R; it never changes size. At rest it is
  // dim; while he speaks it brightens, and brighter still while Jarvis speaks (opacity only, orb.css).
  // v0.6.2: the blue carries out into the light itself (no bright rim hugging the core, then grey)
  const pts = [[0, 0.9], [0.87 * R, 0.62], [1.2 * R, 0.48], [1.5 * R, 0.36], [1.8 * R, 0.26], [2.1 * R, 0.18], [2.5 * R, 0.105], [2.9 * R, 0.057], [3.3 * R, 0.027], [3.8 * R, 0.008], [4.2 * R, 0]];
  pts.push([EN_GLOW, 0]);
  return pts;
}
export const EN_W = EN_OUT - EN_IN;
const RD = 1.9 * R;    // dotted ring
const RT = 2.0 * R;    // cardinal ticks
const RH = 2.2 * R;    // hash marks
export const DIAL_R = 2.5 * R;  // the day dial's ring (drawn in the dial slot only when the orb has the `dial` attribute)

// The particle sphere for standby: three fields of dots inside a ball, turning at different speeds and ways
// (near, middle, far: bigger and brighter in front), so it reads as a slowly drifting 3D cloud. In standby the
// sphere layer is scaled up (orb.css) so it is about as wide as the awake orb's hash ring, with the wordmark on it.
const FIELDS = [ball(16, 11, 41), ball(20, 23, 40), ball(22, 37, 38)];
// Motes: single dots at 2.75–2.95 R, in two groups that twinkle out of step.
const mote = (deg, k) => { const a = (deg * Math.PI) / 180, r = (2.75 + 0.2 * k) * R; return [f(r * Math.cos(a)), f(r * Math.sin(a))]; };
const MOTES = [[mote(-112, 0.2), mote(-18, 0.9), mote(58, 0.4), mote(161, 1)], [mote(-64, 0.7), mote(22, 0.1), mote(118, 0.8), mote(212, 0.3)]];

/** Hash marks: 4 bars per diagonal at 2.2 R, stacked outward; path k holds bar k of all four groups, so the
 *  loop lights them in order by changing four opacities. */
function hashPaths() {
  return [0, 1, 2, 3].map((k) => {
    const r = RH - 3 + k * 2.6;
    return [45, 135, 225, 315].map((deg) => {
      const a = (deg * Math.PI) / 180, cx = r * Math.cos(a), cy = r * Math.sin(a), tx = -Math.sin(a) * 3.2, ty = Math.cos(a) * 3.2;
      return `M${f(cx - tx)} ${f(cy - ty)}L${f(cx + tx)} ${f(cy + ty)}`;
    }).join("");
  });
}

// Glyphs drawn in the core when muted or offline (in R units, centred).
const GLYPHS = {
  muted: "M-5 -2v5a5 5 0 0 0 8.5 3.5M5 1v-7a5 5 0 0 0-9.4-2.4M0 10v5M-12 -12l24 24",
  offline: "M-11 -3a16 16 0 0 1 22 0M-6.5 2a9 9 0 0 1 13 0M0 8.5v0.2M-12 -12l24 24",
};

/** The full orb (size "centre") or its mini rings (size "corner"). `id` keeps gradient/filter ids unique. */
export function orbMarkup(id, { corner = false } = {}) {
  const g = (n) => `${id}-${n}`;
  const parts = [];
  // halo: a soft radial bloom of the orb blue, 0–1.7 R: only the faint glow at rest (idle, thinking, standby); off
  // while listening or speaking, where the glow hugs the band instead. Still: it never scales.
  parts.push(layer("halo", 64, `${svg(64, `<defs><radialGradient id="${g("halo")}" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="62">
      <stop offset="0" class="jv-orb__stop" stop-opacity="0.5"/><stop offset="0.58" class="jv-orb__stop" stop-opacity="0.32"/><stop offset="1" class="jv-orb__stop" stop-opacity="0"/></radialGradient></defs>
      <circle r="62" fill="url(#${g("halo")})"/>`)}`));
  // standby: a translucent sphere of drifting particles (the still body carries a baked soft edge)
  if (!corner) {
    parts.push(layer("sphere", 48, `${svg(48, `<defs><radialGradient id="${g("sph")}" gradientUnits="userSpaceOnUse" cx="-7" cy="-9" r="50">
        <stop offset="0" class="jv-orb__stop" stop-opacity="0.2"/><stop offset="0.75" class="jv-orb__stop" stop-opacity="0.09"/><stop offset="1" class="jv-orb__stop" stop-opacity="0"/></radialGradient>
        <filter id="${g("soft")}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.4"/></filter></defs>
        <circle r="44" fill="url(#${g("sph")})"/><circle class="jv-orb__sphere-glow" r="43.5" filter="url(#${g("soft")})"/>
        <circle class="jv-orb__sphere-edge" r="43.5"/>`)}
      ${FIELDS.map((pts, i) => `<div class="jv-orb__field jv-orb__field--${i}">${svg(48, `<path class="jv-orb__particles" d="${dotsPath(pts)}"/>`)}</div>`).join("")}`));
  }
  // energy ring, 1.15–1.42 R: drawn only while listening or speaking (HUD v3 §14 decision 5). Its glow is light,
  // not a ring (v0.5.2, his reference): bright on the band, then a falloff that runs far out, smooth to nothing
  // (a tight bloom plus a wide, faint tail, like a lens), and a little light spilling inward toward the core.
  // Its own layer ("glow"): the only thing the voice changes, and only its opacity. Then the band itself: a
  // lighter line on its outer edge (--orb-edge), the body (--orb-band), a shade toward the inner edge
  // (--orb-deep), the dark gap and the core's outline. All static gradients, no filter. Nothing ever scales.
  const at = (r) => f(r / EN_GLOW);
  const glowStops = glowCurve().map(([r, o]) => `<stop offset="${at(r)}" class="jv-orb__stop" stop-opacity="${o.toFixed(3)}"/>`).join("");
  parts.push(layer("glow", f(EN_GLOW + 2), `<div class="jv-orb__lvl">${svg(f(EN_GLOW + 2), `<defs><radialGradient id="${g("en")}" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="${f(EN_GLOW)}">${glowStops}</radialGradient></defs>
      <circle class="jv-orb__en-bloom" r="${f(EN_GLOW)}" fill="url(#${g("en")})"/>`)}</div>`));
  parts.push(layer("energy", 68, svg(68, `<defs><radialGradient id="${g("sh")}" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="${f(EN_OUT)}">
      <stop offset="${f(EN_IN / EN_OUT)}" class="jv-orb__stop-deep" stop-opacity="1"/><stop offset="${f((EN_IN + 0.4 * EN_W) / EN_OUT)}" class="jv-orb__stop-deep" stop-opacity="0.5"/>
      <stop offset="${f((EN_IN + 0.8 * EN_W) / EN_OUT)}" class="jv-orb__stop-deep" stop-opacity="0"/></radialGradient>
      <filter id="${g("ensoft")}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.4"/></filter></defs>
      <circle class="jv-orb__en-ring" r="${f(EN_MID)}" pathLength="100"/>
      <circle class="jv-orb__en-shade" r="${f(EN_MID)}" stroke="url(#${g("sh")})"/>
      <circle class="jv-orb__en-hi" r="${f(EN_OUT - 0.6)}"/>
      <circle class="jv-orb__en-soft" r="${f(EN_MID)}" filter="url(#${g("ensoft")})"/>
      <circle class="jv-orb__en-src" r="${f(EN_MID)}"/>
      <circle class="jv-orb__en-edge" r="${f(EN_IN)}" pathLength="100"/>`)));
  // core: dark disc, thin near-white outline with baked bloom, our own letter-spaced JARVIS (still)
  parts.push(layer("core", 41, svg(41, `<defs><filter id="${g("bloom")}" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="1.8"/></filter></defs>
      <circle class="jv-orb__core-bloom" r="${R}" filter="url(#${g("bloom")})"/>
      <circle class="jv-orb__core" r="${R}"/>
      <text class="jv-orb__mark" x="1.5" y="0.5" text-anchor="middle" dominant-baseline="central">JARVIS</text>
      <g class="jv-orb__yes"><text class="jv-orb__yes-1" x="0.5" y="-6" text-anchor="middle" dominant-baseline="central">AWAITING</text>
        <text class="jv-orb__yes-2" x="1.6" y="8" text-anchor="middle" dominant-baseline="central">YES</text></g>
      <path class="jv-orb__glyph jv-orb__glyph--muted" d="${GLYPHS.muted}"/>
      <path class="jv-orb__glyph jv-orb__glyph--offline" d="${GLYPHS.offline}"/>`)));
  // inner arcs (near-white, HUD v3): a thin pair just outside the core at 1.1 R, and the brighter, thicker arc
  // with its faint partner at 1.55 R, just outside the energy ring as in Huw's reels; counter-rotating. Every ring
  // turns inside a centred, square wrapper (.jv-orb__spin); the two arc pairs have a second one nested in it
  // (.jv-orb__spin2: the extra speed while thinking or speaking; two, to stay inside the 8-animation budget). Speed changes by letting the inner one run or hold, so the angle never jumps and
  // nothing but a rotation about the centre is ever on a ring.
  parts.push(layer("arcs-a", 42, spin(svg(42, `<circle class="jv-orb__arc" r="${f(1.1 * R)}" pathLength="360" stroke-dasharray="70 40 40 210"/>`), true), { cls: "jv-orb__tilt", k: -1, delay: 60 }));
  parts.push(layer("arcs-b", 58, spin(svg(58, `<circle class="jv-orb__arc jv-orb__arc--hi" r="${f(1.55 * R)}" pathLength="360" stroke-dasharray="44 316" stroke-dashoffset="-92"/>
      <circle class="jv-orb__arc jv-orb__arc--faint" r="${f(1.55 * R)}" pathLength="360" stroke-dasharray="70 290" stroke-dashoffset="-220"/>`), true), { cls: "jv-orb__tilt", k: 1, delay: 0 }));
  // outer thin arc, 1.7 R: slow drift
  parts.push(layer("outer", 64, spin(svg(64, `<circle class="jv-orb__outer" r="${f(1.7 * R)}" pathLength="360" stroke-dasharray="64 296"/>`), true), { cls: "jv-orb__tilt", k: 2, delay: 120 }));
  // dotted ring, 1.9 R: 48 dots from one dashed circle; slow opposite rotation; tightens on an ordinary wake
  parts.push(layer("dots", 71, spin(svg(71, `<circle class="jv-orb__dots" r="${f(RD)}" pathLength="48"/>`), true), { cls: "jv-orb__tilt", k: -2, delay: 180 }));
  // thinking: a chase of bright dots runs round the dotted ring (the layer hops dot to dot)
  parts.push(layer("chase", 71, spin(svg(71, `<circle class="jv-orb__chase jv-orb__chase--tail" r="${f(RD)}" pathLength="48" stroke-dasharray="0 1 0 1 0 1 0 45"/>
      <circle class="jv-orb__chase" r="${f(RD)}" pathLength="48" stroke-dasharray="0 1 0 47" stroke-dashoffset="-4"/>`))));
  // waiting for a yes: only this dim dotted ring drains over the answer window (never a number)
  parts.push(layer("drain", 71, svg(71, `<defs><mask id="${g("drain")}" maskUnits="userSpaceOnUse" x="-71" y="-71" width="142" height="142">
      <circle class="jv-orb__drain-mask" r="${f(RD)}" pathLength="48" transform="rotate(-93.75)"/></mask></defs>
      <circle class="jv-orb__dots jv-orb__dots--drain" r="${f(RD)}" pathLength="48" mask="url(#${g("drain")})"/>`)));
  if (corner) return parts.join("");

  // ---- outer layers (retract first when docking) ----
  // cardinal ticks at 2.0 R (still, baked bloom): four plain dashes
  const ticks = `M0 ${-RT}V${-RT - 5}M${RT} 0H${RT + 5}M0 ${RT}V${RT + 5}M${-RT} 0H${-RT - 5}`;
  parts.push(layer("ticks", 80, svg(80, `<defs><filter id="${g("tb")}" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="1.4"/></filter></defs>
      <path class="jv-orb__ticks-bloom" d="${ticks}" filter="url(#${g("tb")})"/><path class="jv-orb__ticks" d="${ticks}"/>`), { cls: "jv-orb__outerL jv-orb__tilt", k: 2, delay: 220 }));
  // (the ticks are bare, as Huw's: no readouts round the orb; latency and sync times are in Controls › Under the hood)
  // hash marks at 2.2 R on the diagonals: step in order with the voice
  parts.push(layer("hash", 88, svg(88, hashPaths().map((d, k) => `<path class="jv-orb__hash" data-k="${k}" d="${d}"/>`).join("")), { cls: "jv-orb__outerL jv-orb__tilt", k: -2, delay: 240 }));
  // the day dial's slot at 2.5 R: a square whose inscribed circle is the dial's ring. Shown only with the `dial`
  // attribute (HUD v3 §14: the home screen has nothing around the orb; Today may still put the dial here)
  parts.push(`<div class="jv-orb__L jv-orb__dial jv-orb__outerL" style="inset:${inset(DIAL_R)}" data-orb-slot="dial"></div>`);
  // motes at 2.75–2.95 R, twinkling in two groups
  parts.push(`<div class="jv-orb__L jv-orb__L--motes jv-orb__outerL" style="inset:${inset(109)}">${MOTES.map((pts, i) =>
    `<div class="jv-orb__twinkle jv-orb__twinkle--${i}">${svg(109, `<path class="jv-orb__motes" d="${dotsPath(pts)}"/>`)}</div>`).join("")}</div>`);
  return parts.join("");
}

/** The strip's orb (Laptop A): one still SVG, state by colour and shape only (the strip adds the word). */
export function stripMarkup() {
  return `<svg class="jv-orb__svg jv-orb__strip" viewBox="-50 -50 100 100" aria-hidden="true" focusable="false">
    <circle class="jv-orb__strip-core" r="30"/><circle class="jv-orb__strip-ring" r="40" pathLength="100"/>
    <path class="jv-orb__glyph jv-orb__glyph--muted" transform="scale(1.25)" d="${GLYPHS.muted}"/>
    <path class="jv-orb__glyph jv-orb__glyph--offline" transform="scale(1.25)" d="${GLYPHS.offline}"/></svg>`;
}

/** Which wake beat to play, for a caller that knows when he last woke Jarvis: the full tilt-snap on the first
 *  wake of the day or after ≥ 4 h away, otherwise the 250 ms tighten. */
export function wakeKind(lastWake, now = new Date()) {
  if (!lastWake) return "full";
  const last = new Date(lastWake);
  if (Number.isNaN(last.getTime())) return "full";
  return last.toDateString() !== now.toDateString() || now - last >= 4 * 3600_000 ? "full" : "tighten";
}
