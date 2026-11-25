// The Keys page's only door to the keys API (contracts/keys.schema.json, K1). Kept apart from bridge.js on
// purpose: a pasted key must never pass through bridge.act, /api/act, the store, events or the activity log.
//   GET    /api/keys                     the rows (never a key; at most its last 4 characters)
//   POST   /api/keys/{id}/next           { secret }  → row   (stored as next and checked; never live by itself)
//   POST   /api/keys/{id}/promote                    → row   (next becomes live; the old one kept 15 minutes)
//   DELETE /api/keys/{id}/previous                   → row
//   DELETE /api/keys/{id}               { confirm }  → row   (confirm must equal the id)
// An answer with the header `X-Jarvis-Keys: example` comes from the hub's demo backend (jarvis_hub/demo/keys.py),
// not from jarvis-core: the page then says the core isn't connected and accepts nothing.

//
// Two laptops (v0.24.0). The hub's answers say where the keys are kept (`X-Jarvis-Kept`: "here" or the other
// laptop's name) and, on a laptop that runs its own Jarvis, name the other one (`X-Jarvis-Other-Name`). With his
// tick box on, a change goes out with `X-Jarvis-Also-Other: 1` and the hub repeats it there; `X-Jarvis-Other`
// (saved | refused | unreachable) says how that went. The voice field shares this state.

const BASE = "/api/keys";
export const EXAMPLE_HEADER = "X-Jarvis-Keys";

/** kept: "here" | a laptop's name | "" (not known yet). other: the second Jarvis ("" when there is none). */
export const laptops = { kept: "", other: "", also: true };
export function readWhere(response) {
  laptops.kept = response.headers.get("X-Jarvis-Kept") || laptops.kept;
  laptops.other = response.headers.get("X-Jarvis-Other-Name") || "";
}
export const alsoHeaders = () => (laptops.other && laptops.also ? { "X-Jarvis-Also-Other": "1" } : {});
export const keptWords = () => (laptops.kept && laptops.kept !== "here" ? laptops.kept : "this laptop");
/** How the other laptop took the change, as one short sentence for the toast ("" when nothing went there). */
export function otherWords(response) {
  const how = response.headers.get("X-Jarvis-Other"), name = laptops.other || "the other laptop";
  if (how === "saved") return ` Same on ${name}.`;
  if (how === "refused") return ` ${name} didn't take it: finish it in the hub on that laptop.`;
  return how === "unreachable" ? ` ${name} isn't answering, so it kept what it had.` : "";
}

const ROUTES = {
  add_next: (id) => ["POST", `${BASE}/${encodeURIComponent(id)}/next`],
  promote: (id) => ["POST", `${BASE}/${encodeURIComponent(id)}/promote`],
  remove_previous: (id) => ["DELETE", `${BASE}/${encodeURIComponent(id)}/previous`],
  remove: (id) => ["DELETE", `${BASE}/${encodeURIComponent(id)}`],
};

/** Read the rows. → { doc, connected, example }. doc is null when nothing answered (then: not connected). T1. */
export async function loadKeys({ scene = null, now = null } = {}) {
  const query = scene ? `?scene=${encodeURIComponent(scene)}${now ? `&now=${encodeURIComponent(now)}` : ""}` : "";
  try {
    const response = await fetch(BASE + query, { cache: "no-store", headers: { Accept: "application/json" } });
    readWhere(response);
    if (!response.ok) return { doc: null, connected: false, example: false, status: response.status };
    const doc = await response.json();
    const example = response.headers.get(EXAMPLE_HEADER) === "example";
    return { doc, connected: !example, example };
  } catch {
    return { doc: null, connected: false, example: false, status: 0 };
  }
}

/** Send one change. `body` is built here from the caller's value and dropped when this returns.
 *  → { ok: true, row } or { ok: false, error, message, row? }. Never throws. T1. */
export async function sendKey(action, id, body = null) {
  const route = ROUTES[action];
  if (!route) return { ok: false, error: "bad_request", message: "That isn't something the Keys page can do." };
  const [method, url] = route(id);
  try {
    const response = await fetch(url, {
      method, cache: "no-store", credentials: "same-origin",
      headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}), ...(action === "remove" ? {} : alsoHeaders()) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const answer = await response.json().catch(() => ({}));
    const example = response.headers.get(EXAMPLE_HEADER) === "example";
    if (!response.ok || example || answer.error) {
      return { ok: false, error: answer.error || (example ? "not_connected" : "bad_request"), row: answer.row,
               message: answer.message || "That didn't go through. Nothing was changed." };
    }
    return { ok: true, row: answer, also: otherWords(response) };
  } catch {
    return { ok: false, error: "unreachable", message: "Jarvis core isn't answering. Nothing was changed." };
  }
}
