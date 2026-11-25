// The one registry of window kinds that bring their own content (hub v0.5.0: web, map, agent_task). The window
// manager (core/windows.js), the content switch (views/now/widgets.js) and the Stage canvas know the built-in
// kinds by name; a new kind registers here instead of growing those switches. Each of them asks
// `windowKind(type)` and falls back to its own rules when nothing is registered, so a kind that isn't loaded
// changes nothing. This file imports nothing, so core/windows.js can read it.
//
//   registerWindowKind("web", {
//     content(win, s, now) → Element      the window's body (required): one hero, at most one line (HUD v2 §14.2)
//     kicker(win, s, thread, now) → { heading?, status?, index?, meta? }   overrides for the kicker row and footer
//     role: "media" | "chart" | "number" | "title"   what it leads with on the Stage's board (windows.js roleOf)
//     tier: "S" | "M" | "L"               its width tier (windows.js tierOf); or `width` in px at 1920
//     size: "2x2"                          its default grid size on the hub (windows.js sizeOf)
//   })
const KINDS = new Map();
const ROLES = new Set(["media", "chart", "number", "title"]);
const TIERS = new Set(["S", "M", "L"]);
const tierFor = (width) => (width <= 300 ? "S" : width <= 440 ? "M" : "L");

/** Register (or replace) a window kind. → the stored spec */
export function registerWindowKind(type, spec) {
  if (!type || typeof spec?.content !== "function") throw new TypeError(`Window kind "${type}" needs a content() function.`);
  const role = ROLES.has(spec.role) ? spec.role : "title";  // ("text", the name before v0.4.1, is a title)
  const tier = TIERS.has(spec.tier) ? spec.tier : spec.width ? tierFor(spec.width) : role === "media" ? "L" : "M";
  const kind = Object.freeze({ ...spec, type, role, tier });
  KINDS.set(type, kind);
  return kind;
}

/** The registered kind for a window type, or null (the built-in rules apply). */
export const windowKind = (type) => KINDS.get(type) || null;

/** Every registered type (for tests and the gallery). */
export const windowKinds = () => [...KINDS.keys()];
