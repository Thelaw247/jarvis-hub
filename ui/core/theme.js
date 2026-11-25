// Theme and motion (B02, HUD v2 §1). Reads Controls › Look and sets the attributes the tokens and base styles use:
//   data-theme = night | day        (Night is the default everywhere, ambient included)
//   data-motion = full | reduced | off   and   data-still when nothing may move
//   data-plants = off when plants are turned off
// Choices in Controls: "night" (default) · "day" (Daylight, for bright rooms) · "sunset" (Daylight by day,
// Night from Saskatoon's real sunset to sunrise, worked out on the device: standard sunrise equation, within a
// couple of minutes; no network and no location lookup). Retired choices still load: a stored "evening" is
// Night, and "system" follows Windows (dark → Night, light → Daylight). ?theme=night|day forces one
// (?theme=evening is read as night).
import { params, registerGallery } from "./scenes.js";
import { store } from "./store.js";

const root = document.documentElement;
const dark = matchMedia("(prefers-color-scheme: dark)");
const calm = matchMedia("(prefers-reduced-motion: reduce)");

const RAD = Math.PI / 180;
export const SASKATOON = { lat: 52.1332, lon: -106.67 };

// Sunrise and sunset (Date objects) for the solar day nearest `now`. Polar days/nights return { polar }.
export function sunTimes(now, { lat, lon } = SASKATOON) {
  const jd = now.getTime() / 86400000 + 2440587.5;
  const jStar = Math.round(jd - 2451545 + lon / 360) - lon / 360;
  const M = (357.5291 + 0.98560028 * jStar) % 360;
  const C = 1.9148 * Math.sin(M * RAD) + 0.02 * Math.sin(2 * M * RAD) + 0.0003 * Math.sin(3 * M * RAD);
  const L = (M + C + 180 + 102.9372) % 360;
  const transit = 2451545 + jStar + 0.0053 * Math.sin(M * RAD) - 0.0069 * Math.sin(2 * L * RAD);
  const sinD = Math.sin(L * RAD) * Math.sin(23.4397 * RAD), cosD = Math.cos(Math.asin(sinD));
  const cosW = (Math.sin(-0.833 * RAD) - Math.sin(lat * RAD) * sinD) / (Math.cos(lat * RAD) * cosD);
  if (cosW > 1) return { polar: "night" };
  if (cosW < -1) return { polar: "day" };
  const half = Math.acos(cosW) / RAD / 360, toDate = (j) => new Date((j - 2440587.5) * 86400000);
  return { rise: toDate(transit - half), set: toDate(transit + half) };
}
export function afterSunset(now, place = SASKATOON) {
  const t = sunTimes(now, place);
  if (t.polar) return t.polar === "night";
  return now < t.rise || now > t.set;
}

export const THEMES = ["night", "day"];
export const THEME_CHOICES = [["night", "Night"], ["day", "Daylight"], ["sunset", "Sunset"]];

/** The choice Controls should show as selected, with retired values mapped onto today's three. */
export function themeChoice(choice, prefersDark) {
  if (choice === "day" || choice === "sunset") return choice;
  if (choice === "system") return prefersDark ? "night" : "day";
  return "night";  // "night", the retired "evening", or nothing chosen yet
}
/** data-theme for a choice at a moment: "night" or "day". */
export function themeFor(choice, now, prefersDark) {
  const c = themeChoice(choice, prefersDark);
  if (c === "sunset") return afterSunset(now) ? "night" : "day";
  return c;
}

/** A ?theme= value forced in the address (scenes, screenshots): day stays day, everything else is night. */
export function forcedTheme(value) {
  return value === "day" ? "day" : "night";
}

export function isStill(motion, size, prefersReduced) {
  return size === "strip" || motion === "reduced" || motion === "off" || (motion !== "full" && prefersReduced);
}

export function applyLook() {
  const c = store.state.settings || {};
  const forced = params.get("theme"), forcedMotion = params.get("motion");
  root.dataset.theme = forced ? forcedTheme(forced) : themeFor(c.theme, store.now(), dark.matches);
  // "full" in Controls respects Windows' reduced-motion setting; "always" (v0.12.3) keeps full motion anyway, the
  // same as ?motion=full (for a laptop with Windows animations turned off)
  const chosen = forcedMotion || c.motion || "full";
  const motion = chosen === "always" ? "full" : chosen;
  const explicit = forcedMotion || chosen === "always";
  if (explicit || motion !== "full") root.dataset.motion = motion; else delete root.dataset.motion;
  root.toggleAttribute("data-still", isStill(explicit || motion !== "full" ? motion : "", root.dataset.size, calm.matches));
  if (c.plants === false) root.dataset.plants = "off"; else delete root.dataset.plants;
}

export function startTheme({ live = true } = {}) {
  applyLook();
  store.subscribe((_s, keys) => { if (keys.has("settings")) applyLook(); });
  dark.addEventListener("change", applyLook);
  calm.addEventListener("change", applyLook);
  if (live) setInterval(() => { if (!document.hidden) applyLook(); }, 60_000);  // catches sunset within a minute
}

// The base HUD classes (ui/base.css) side by side, in whichever theme is forced: ?scene=component:hud-base
registerGallery("hud-base", [
  { label: "Window", build: () => `<div class="jv-frame"><div class="jv-kicker-row"><span class="jv-kicker">GE 122 // DUE</span><span class="jv-kicker">01 / 03</span></div>
      <p class="jv-hero">2 d 4 h</p><p class="jv-display">PPS 7 · Problem-solving set</p><span class="jv-meta">Syllabus p.3</span></div>` },
  { label: "Window Jarvis means", build: () => `<div class="jv-frame jv-frame--on"><div class="jv-kicker-row"><span class="jv-kicker">PPS 7 // Q7 OF 12</span><span class="jv-kicker">00:04</span></div>
      <p class="jv-display">Question seven</p><p class="jv-muted">Where you stopped on Tuesday.</p><span class="jv-meta">Added 2 min ago</span></div>` },
  { label: "Window set aside", build: () => `<div class="jv-frame jv-frame--dim"><div class="jv-kicker-row"><span class="jv-kicker">Messages // New</span></div>
      <p class="jv-display">2 messages</p><span class="jv-meta jv-meta--end">Gmail</span></div>` },
  { label: "Pills", build: () => `<div style="display:flex;flex-wrap:wrap;gap:8px"><button class="jv-pill">Tidy</button><button class="jv-pill">Clear view</button>
      <button class="jv-pill" aria-pressed="true">Now</button><button class="jv-pill">Today</button><button class="jv-pill jv-show-focus">Focused</button></div>` },
  { label: "States", build: () => `<div class="jv-frame"><p style="color:var(--cyan)">Jarvis means this</p><p style="color:var(--cyan-hi)">Done</p>
      <p style="color:var(--warn)">Soon · your yes</p><p style="color:var(--crit)">Now · overdue</p><p style="color:var(--ok)">Systems fine</p>
      <p style="color:var(--text-2)">Secondary text</p><p class="jv-kicker">Kicker // text-3</p></div>` },
  { label: "Reading sheet", build: () => `<div class="jv-frame"><div class="jv-paper" style="padding:16px"><p class="jv-read">Q7. Find the reactions at A and B.</p>
      <p style="color:var(--cyan)">Jarvis means this</p><p style="color:var(--warn)">Soon</p><p style="color:var(--ok)">Done</p><p style="color:var(--crit)">Overdue</p><p class="jv-muted">Page 3 of 12</p></div></div>` },
], { about: "Night HUD base classes: frame, kicker, metadata outside the frame, hero and title type, pills, focus ring, state colours and the light reading sheet." });
