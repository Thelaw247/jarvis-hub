// The rules for web windows (REACH §5.1), as plain functions so they are easy to test: which addresses may be
// shown at all (http and https only), how a page is sandboxed, whether to try a frame or show the card at once,
// and what the window's kicker says. No DOM here.

/** How long a page may take to load before the window shows its card instead (a hung address, no network). */
export const LOAD_TIMEOUT_MS = 12_000;
/** A tabs window holds at most this many pages (contracts/web.schema.json pages.maxItems). */
export const MAX_PAGES = 6;

/** Sites known to refuse being shown inside another page (X-Frame-Options or CSP frame-ancestors). Only a hint,
 *  used in a plain browser: there the window shows its card at once instead of the browser's broken-frame page.
 *  On the desktop app WebView2 lets the hub's own pages frame them (jarvis_hub/webframes.py), so the hint is
 *  ignored there. Matched on the host and every subdomain of it. Their /embed/ pages are made to be framed. */
export const REFUSES_FRAMING = Object.freeze([
  "google.com", "youtube.com", "github.com", "instructure.com", "canvas.usask.ca", "paws.usask.ca",
  "office.com", "live.com", "sharepoint.com", "microsoft.com", "x.com", "twitter.com", "facebook.com",
  "instagram.com", "linkedin.com", "reddit.com", "stackoverflow.com", "chatgpt.com", "claude.ai", "amazon.com",
]);

/** Sites that sign people in. They refuse to do it inside another app's window (on 2026-11-19 Google answered 403
 *  in a hub window), so these always show the card, on the desktop app too: one click opens his own browser.
 *  The core marks them frame: "no" as well (jarvis/tools/show_page/handler.py SIGN_IN_HOSTS). */
export const NEVER_FRAME = Object.freeze([
  "accounts.google.com", "login.microsoftonline.com", "login.live.com", "composio.dev", "appleid.apple.com",
  "auth.openai.com",
]);

/** The sandbox every framed page gets: its own scripts, its own cookies (signed-in pages), and forms (a search
 *  box), but never top navigation (it can't take the hub away), never pop-ups, never the hub's bridge. */
export const SANDBOX = "allow-scripts allow-same-origin allow-forms";
/** A page from the hub's own address (the demo pages) loses same-origin: it gets an opaque origin and can't
 *  reach into the hub, its store or its bridge. */
export const SANDBOX_HUB_ORIGIN = "allow-scripts allow-forms";

/** The address as a clean http(s) URL string, or null: no javascript:, data:, file:, blob: or about: pages, and
 *  no user name or password inside the address. */
export function safeUrl(raw) {
  if (typeof raw !== "string" || !raw.trim()) return null;
  let url;
  try { url = new URL(raw.trim()); } catch { return null; }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  if (url.username || url.password || !url.hostname) return null;
  return url.href;
}

/** "google.com" for https://www.google.com/search?q=…: the host without a leading www. */
export function siteOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
}

const ownsHost = (host, site) => host === site || host.endsWith(`.${site}`);

/** Is this address on the list of sites that refuse framing (and not one of their embed pages)? */
export function refusesFraming(url, list = REFUSES_FRAMING) {
  let u;
  try { u = new URL(url); } catch { return false; }
  if (/^\/embed(\/|$)/.test(u.pathname) || /^\/maps\/embed/.test(u.pathname)) return false;
  return list.some((site) => ownsHost(u.hostname, site));
}

/** Pages Jarvis wrote himself (make_window, v0.23.0) arrive as http://jarvis.made/<id>: not a real site. */
export const MADE_HOST = "jarvis.made";
export const isMade = (url) => { try { return new URL(url).hostname === MADE_HOST; } catch { return false; } };
/** Where a page is really loaded from: a made page comes from the hub's own /api/made/<id> (in the hub's theme);
 *  everything else from its own address. Being the hub's address, a made page gets SANDBOX_HUB_ORIGIN: an opaque
 *  origin that cannot reach into the hub. */
export function frameSrc(url, hubOrigin, theme = "night") {
  if (!isMade(url) || !hubOrigin) return url;
  const id = new URL(url).pathname.replace(/^\//, "");
  return /^[a-f0-9]{12}$/.test(id) ? `${hubOrigin}/api/made/${id}?theme=${theme === "day" ? "day" : "night"}` : url;
}

/** The sandbox for a page: same-origin is dropped for the hub's own address. */
export function sandboxFor(url, hubOrigin) {
  let origin = "";
  try { origin = new URL(url).origin; } catch { /* not a URL: safeUrl already refused it */ }
  return hubOrigin && origin === hubOrigin ? SANDBOX_HUB_ORIGIN : SANDBOX;
}

/** "frame" (try to show the live page) or "card" (show the card at once). `desktop`: the hub runs in the
 *  desktop app, where WebView2 frames pages that refuse it (jarvis_hub/webframes.py). */
export function frameMode(page, { desktop = false } = {}) {
  if (!page || page.frame === "no") return "card";
  if (refusesFraming(page.url, NEVER_FRAME)) return "card";
  return !desktop && refusesFraming(page.url) ? "card" : "frame";
}

/** The pages of a web window (contracts/web.schema.json), cleaned: only http(s) addresses, at most MAX_PAGES,
 *  each with an id, a title and its site. → { pages, active } where active is the shown page's index. */
export function pagesOf(win) {
  const list = Array.isArray(win?.data?.pages) ? win.data.pages : [];
  const pages = [];
  for (const [i, p] of list.entries()) {
    const url = safeUrl(p?.url);
    if (!url || pages.length >= MAX_PAGES) continue;
    const site = String(p.site || siteOf(url));
    pages.push({ id: String(p.id || `page-${i + 1}`), url, title: String(p.title || site), site, frame: p.frame === "no" ? "no" : "auto" });
  }
  const active = Math.max(0, pages.findIndex((p) => p.id === win?.data?.active));
  return { pages, active: pages.length ? active : -1 };
}

const pad = (n) => String(n).padStart(2, "0");

/** The kicker row for a web window (HUD v2 §14.2): `WEB // site` on the left; a tabs window puts the shown
 *  page's place on the right ("02 / 03"). `active` overrides the shown page (the window's own tab state). */
export function webKicker(win, _s, active) {
  const { pages, active: first } = pagesOf(win);
  const at = Number.isInteger(active) && pages[active] ? active : first;
  const page = pages[at];
  if (page && isMade(page.url)) return { heading: "Jarvis", status: page.title, index: "" };   // his own window, not a site
  return { heading: "Web", status: page ? page.site : "", index: pages.length > 1 ? `${pad(at + 1)} / ${pad(pages.length)}` : "" };
}

/** The supporting line under a card's title: the address without its scheme, at most ~90 characters. */
export function addressLine(url, max = 90) {
  const text = String(url || "").replace(/^https?:\/\//, "").replace(/\/$/, "");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
