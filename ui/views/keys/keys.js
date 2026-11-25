// Controls › Keys (K2; JARVIS_CORE_BUILD_MAP §3; contracts/keys.schema.json). One row per service: its status as
// a glance code (shape + colour + word), the last 4 characters only, when it was added and last checked.
// Rotation with no downtime: Add next key → Check → Make live → Remove old (the old key is kept 15 minutes in
// case the new one fails; the countdown is in words). After the swap, a link to the provider's console reminds
// him to revoke the old key there (Jarvis can't).
//
// Secrets: the field is a password input (no autocomplete, spellcheck off) that is never re-rendered: the same
// node is moved back in after each render, so its value never passes through a template, the store, events,
// localStorage or an attribute. On Check its value is read once, the field is cleared at once, and the value goes
// only into the request body (keys-api.js). Nothing sent is ever shown back.
//
// No core (the hub's demo backend answers): "Jarvis core isn't connected yet", example rows with fake last-4s,
// and nothing is accepted. On the phone the page is view-only. Scenes preview each row state locally: no
// network writes, nothing kept (the typed value is dropped unread except for "is it empty").
import { css, html, localIso, shortDate } from "../../core/dom.js";
import { router } from "../../core/router.js";
import { registerScene, sceneName } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { glance } from "../../components/glance/glance.js";
import { keptWords, laptops, loadKeys, sendKey } from "./keys-api.js";
import "./voice-setting.js";

css(import.meta.url);

/** status → [glance code, word] (contracts/keys.schema.json $defs/status; HUD v2 §5). */
export const STATUS = {
  live: ["done", "Live"],
  next_waiting: ["yes", "Next waiting"],
  checking: ["progress", "Checking"],
  failed_check: ["critical", "Failed check"],
  missing: ["soon", "Missing"],
  expiring: ["soon", "Expiring"],
  fell_back: ["yes", "Fell back"],  // also raises a "Your yes" flag on the Rail (keysYesFlag)
};
/** The "Your yes" Rail item a fell-back row raises (contracts/rail.schema.json $defs/item), or null. Mirrors
 *  jarvis_hub/demo/keys.py yes_flag. The Rail is the hub's: the scenes put it there; live, the hub or core does. */
export function keysYesFlag(row, at) {
  if (row?.status !== "fell_back") return null;
  return { ref: `keys:${row.id}`, slot: "yes", kind: "notice", title: `${short(row.label)} key fell back`, at, state: "yes",
           detail: "The new key was refused once live · Controls › Keys" };
}
const REASON = {
  rejected: "The service refused it.", forbidden: "The service says it isn't allowed.", bad_shape: "It doesn't look like this service's key.",
  rate_limited: "The service was busy. Try the check again in a minute.", unreachable: "The service didn't answer.",
  provider_error: "The service had a problem.", refresh_failed: "Google refused the sign-in.", too_long: "It's too long to store.",
  refused_after_swap: "It passed the check but was refused once live.",
};
// Scenes: the demo backend's simulated state for each (jarvis_hub/demo/keys.py SCENES). `preview` draws it as a
// connected core would, with every write answered locally; `keys` itself is the honest not-connected page.
const SCENES = {
  keys: { state: "not_connected", preview: false, about: "No core: \"Jarvis core isn't connected yet\", example rows, accepts nothing" },
  "keys-live": { state: "live", about: "Every key live" },
  "keys-next-waiting": { state: "next_waiting", about: "A checked next key waits to be made live" },
  "keys-checking": { state: "checking", about: "The next key is being checked" },
  "keys-failed-check": { state: "failed_check", about: "The next key failed its check; the live key keeps working" },
  "keys-fell-back": { state: "fell_back", about: "The new key was refused once live: Jarvis went back to the old one" },
  "keys-old-kept": { state: "old_kept", about: "Just made live: the old key is kept 15 minutes, with the revoke link" },
  "keys-missing": { state: "missing", about: "Two services have no key yet" },
  "keys-expiring": { state: "expiring", about: "Google OAuth (added from the list) runs out soon" },
  "keys-phone": { state: "live", size: "phone", about: "The phone: view-only" },
};
const PREVIEW_LAST4 = "EX10";  // the scene preview's made-up last 4 for a "sent" key; never taken from the field
const POLL_MS = 1500;

const word = (kind) => (kind === "password" ? "password" : kind === "client_json" ? "client file" : "key");
const short = (label) => String(label || "").replace(/\s*\(.*\)\s*$/, "");  // "Claude (Anthropic API)" → "Claude"
/** "just now", "12 s ago", "4 min ago", "3 h ago", "yesterday", "5 days ago". */
export function ago(iso, now) {
  if (!iso) return "";
  const s = Math.max(0, Math.round((now - new Date(iso)) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  const d = Math.floor(s / 86400);
  return d === 1 ? "yesterday" : `${d} days ago`;
}
/** The fallback countdown in words: "14 more minutes", "1 more minute", "under a minute". */
export function minutesLeft(until, now) {
  const m = Math.ceil((new Date(until) - now) / 60000);
  return m <= 0 ? "under a minute" : m === 1 ? "1 more minute" : `${m} more minutes`;
}
/** The last 4 of a slot, or null. A password (restic) never shows any of itself, whatever a backend sends. */
export const last4Of = (row, slot) => (row?.kind === "password" || row?.id === "restic" ? null : slot?.last4 || null);
const masked = (last4) => (last4 ? html`<span class="jv-keys__mask"><span aria-hidden="true">····</span><span class="jv-sr">ending in </span>${last4}</span>` : "");

class KeysView extends HTMLElement {
  connectedCallback() {
    if (this._wired) return;
    this._wired = true;
    this.doc = null; this.connected = false; this.example = false; this.loaded = false;
    this.scene = SCENES[sceneName] && sceneName?.startsWith("keys") ? { preview: true, ...SCENES[sceneName] } : null;
    this.openFor = null;      // the row id (or an addable id) whose secret field is open
    this.confirming = null;   // the row id whose Remove waits for "Remove it" / "Keep it"
    this.notes = {};          // row id → one plain line after a change (never key material)
    this.busy = null;         // the row id a request is out for
    this.focusKey = null;     // data-key to focus after the next render
    this.addChoice = "";
    this.addEventListener("click", (e) => this.onClick(e));
    this.addEventListener("keydown", (e) => this.onKey(e));
    this.addEventListener("change", (e) => { if (e.target.matches?.("[data-k=choose]")) { this.addChoice = e.target.value; this.draw(); } });
    this.stopEvents = store.onEvent((event) => { if (event.type === "keys.updated" && event.data?.row) this.putRow(event.data.row); });
    this.sizeWatch = new MutationObserver(() => this.draw());  // phone ⇄ laptop: view-only follows the size
    this.sizeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-size"] });
    this.tick = setInterval(() => { if (this.doc?.rows?.some((r) => r.previous || r.used)) this.draw(); }, 30_000);  // words, not motion
    this.draw();
    this.load();
  }
  disconnectedCallback() {
    this.stopEvents?.(); this.sizeWatch?.disconnect();
    clearInterval(this.tick); clearTimeout(this.poll);
    this.dropField();
    this._wired = false;
  }

  get now() { return store.now(); }
  get viewOnly() { return document.documentElement.dataset.size === "phone" || (this.connected && this.doc?.can_write === false) || (this.scene?.size === "phone"); }
  get writable() { return (this.connected || (this.scene && this.scene.preview)) && !this.viewOnly; }

  async load() {
    const got = await loadKeys(this.scene ? { scene: this.scene.state, now: localIso(this.now) } : {});
    Object.assign(this, { doc: got.doc, connected: got.connected, example: got.example || !!this.scene, loaded: true });
    this.draw();
    this.schedulePoll();
  }
  /** While a key is being checked and a real core is connected, ask again every 1.5 s (keys.updated usually beats it). */
  schedulePoll() {
    clearTimeout(this.poll);
    if (this.connected && this.doc?.rows?.some((r) => r.status === "checking")) this.poll = setTimeout(() => this.load(), POLL_MS);
  }
  putRow(row) {
    if (!this.doc || !row?.id) return;
    const rows = this.doc.rows.some((r) => r.id === row.id) ? this.doc.rows.map((r) => (r.id === row.id ? row : r)) : [...this.doc.rows, row];
    this.doc = { ...this.doc, rows, addable: (this.doc.addable || []).filter((a) => a.id !== row.id) };
    this.draw();
    this.schedulePoll();
  }

  // ---- the secret field: one node, made here, never written into a template ------------------------------
  field(id) {
    if (!this.input || this.input.dataset.for !== id) {
      this.dropField();
      const input = document.createElement("input");
      Object.assign(input, { type: "password", autocomplete: "off", spellcheck: false, className: "jv-keys__secret", id: "keys-secret" });
      for (const [k, v] of Object.entries({ autocapitalize: "off", autocorrect: "off", "data-key": "secret", "data-for": id,
        "aria-describedby": "keys-field-hint", "data-lpignore": "true", "data-1p-ignore": "", "data-bwignore": "", "data-form-type": "other" })) input.setAttribute(k, v);
      this.input = input;
    }
    return this.input;
  }
  dropField() { if (this.input) { this.input.value = ""; this.input.remove(); this.input = null; } }
  takeSecret() {  // read once, clear at once
    const input = this.input;
    const value = input ? input.value : "";
    if (input) input.value = "";
    return value;
  }

  // ---- actions -------------------------------------------------------------------------------------------
  onKey(e) {
    if (e.target !== this.input) return;
    if (e.key === "Enter") { e.preventDefault(); this.check(this.input.dataset.for); }
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.cancel(); }
  }
  onClick(e) {
    const b = e.target.closest?.("[data-k]");
    if (!b || b.disabled || b.tagName === "SELECT") return;
    const id = b.dataset.id, k = b.dataset.k;
    if (!this.writable && k !== "nav") return;
    if (k === "nav") { e.preventDefault(); router.go(b.dataset.path); return; }
    if (k === "also") { laptops.also = b.checked; return; }  // his choice; kept across redraws, never sent by itself
    if (k === "add") { this.openFor = id; this.confirming = null; this.focusKey = "secret"; this.draw(); }
    else if (k === "add-service") { if (this.addChoice) { this.openFor = this.addChoice; this.focusKey = "secret"; this.draw(); } }
    else if (k === "check") this.check(id);
    else if (k === "cancel") this.cancel();
    else if (k === "promote") this.change("promote", id);
    else if (k === "remove-old") this.change("remove_previous", id);
    else if (k === "remove") { this.confirming = id; this.openFor = null; this.dropField(); this.focusKey = `keep-${id}`; this.draw(); }
    else if (k === "keep") { this.confirming = null; this.focusKey = `remove-${id}`; this.draw(); }
    else if (k === "remove-yes") this.change("remove", id, { confirm: id });
  }
  cancel() {
    const id = this.openFor;
    this.openFor = null; this.dropField();
    this.focusKey = id && this.doc?.rows?.some((r) => r.id === id) ? `add-${id}` : "choose";
    this.draw();
  }
  async check(id) {
    if (!id || !this.writable) return;
    const label = this.labelOf(id);
    if (!this.input?.value) { this.say(`Paste the new ${label} key first.`); return; }
    let secret = this.takeSecret();
    this.openFor = null; this.dropField();
    this.notes[id] = "Sent once to Jarvis core. The field is cleared; the key is never shown again.";
    this.focusKey = `name-${id}`;
    this.busy = id; this.draw();
    let result;
    if (this.connected) result = await sendKey("add_next", id, { secret });
    else { secret = ""; result = this.preview("add_next", id); }
    secret = "";
    this.done(id, result, `${label}: checking the new key.`);
  }
  async change(action, id, body = null) {
    if (!this.writable) return;
    this.busy = id; this.draw();
    const result = this.connected ? await sendKey(action, id, body) : this.preview(action, id);
    const label = this.labelOf(id);
    if (result.ok) {
      if (action === "promote") this.notes[id] = "The new key is live. The old one stays 15 minutes in case it fails.";
      if (action === "remove_previous") this.notes[id] = "revoke";
      if (action === "remove") { this.notes[id] = ""; this.confirming = null; }
      this.focusKey = action === "promote" ? `remove-old-${id}` : `name-${id}`;
    }
    this.done(id, result, { promote: `${label} key is live.`, remove_previous: `Old ${label} key removed from ${keptWords()}.`, remove: `${label} key removed.` }[action]);
  }
  done(id, result, okWords) {
    this.busy = null;
    if (result.ok) { this.putRow(result.row); this.say(okWords + (result.also || "")); }
    else {
      if (result.row) this.putRow(result.row);
      if (result.error === "not_connected") this.connected = false;
      this.notes[id] = result.message;
      this.say(result.message, "error");
      this.draw();
    }
  }
  /** Scene preview: what a connected core would answer, worked out here. Nothing is sent, nothing is kept. */
  preview(action, id) {
    const now = this.now, iso = (ms = 0) => localIso(new Date(now.getTime() + ms));
    const row = structuredClone(this.doc.rows.find((r) => r.id === id) || { ...this.doc.addable.find((a) => a.id === id), status: "missing", live: null, next: null, previous: null, used: null });
    delete row.detail;
    if (action === "add_next") {
      Object.assign(row, { status: "checking", next: { last4: row.kind === "password" ? null : PREVIEW_LAST4, added: iso(), checked: null, check: "checking" } });
      setTimeout(() => {
        const r = structuredClone(this.doc?.rows.find((x) => x.id === id));
        if (r?.status !== "checking") return;
        Object.assign(r.next, { checked: iso(1200), check: r.kind === "password" ? "shape_only" : "ok" });
        if (r.live) Object.assign(r, { status: "next_waiting", detail: "A new key passed its check. Make it live when you're ready." });
        else Object.assign(r, { status: "live", live: r.next, next: null, used: null });
        this.putRow(r);
      }, 1200);
    } else if (action === "promote") {
      if (!row.next) return { ok: false, error: "no_next", message: "There's no checked next key to make live." };
      Object.assign(row, { status: "live", previous: row.live ? { ...row.live, until: iso(15 * 60_000) } : null, live: { ...row.next, check: "ok" }, next: null, used: iso() });
    } else if (action === "remove_previous") row.previous = null;
    else if (action === "remove") Object.assign(row, { status: "missing", live: null, next: null, previous: null, used: null });
    return { ok: true, row };
  }
  say(text, kind = "info") {
    if (!text) return;
    store.apply({ v: 2, type: "toast", ts: localIso(this.now), data: { id: `t-keys-${Date.now()}`, kind, text, ttl_ms: 5000 } });
  }
  labelOf(id) { return short((this.doc?.rows || []).concat(this.doc?.addable || []).find((r) => r.id === id)?.label || id); }

  // ---- drawing -----------------------------------------------------------------------------------------
  draw() {
    const had = this.contains(document.activeElement) ? document.activeElement.getAttribute("data-key") : null;
    this.innerHTML = String(this.render());
    const slot = this.querySelector("[data-secret-slot]");
    if (slot && this.input) slot.replaceWith(this.input);
    this.voice ||= document.createElement("jv-voice-setting");  // made once; keeps what he typed across redraws
    this.querySelector("[data-voice-slot]")?.replaceWith(this.voice);
    const asked = this.focusKey, want = asked || had;
    this.focusKey = null;
    if (want) this.querySelector(`[data-key="${CSS.escape(want)}"]`)?.focus({ preventScroll: !asked });
  }
  render() {
    const doc = this.doc, now = this.now, writable = this.writable, rows = doc?.rows || [];
    const crumb = html`<nav class="jv-crumbs" aria-label="Breadcrumb"><a href="#/controls" data-k="nav" data-path="/controls" data-key="crumb">Controls</a><span aria-hidden="true">›</span><span aria-current="page">Keys</span></nav>`;
    const head = html`<header class="jv-view__head">${crumb}<h1>Keys</h1><p class="jv-view__sub">The keys Jarvis uses for Claude, the voice and your apps. Write-only: a key is never shown again, only its last 4 characters.</p></header>`;
    const notConnected = this.loaded && !this.connected && !(this.scene?.preview);
    const banner = notConnected ? html`<section class="jv-keys__banner" role="status" aria-labelledby="keys-nc"><p class="jv-keys__banner-kicker jv-kicker">CORE // OFFLINE</p>
        <h2 id="keys-nc" class="jv-keys__banner-title">Jarvis core isn't connected yet</h2>
        <p>Keys go in here once Jarvis core is running. Until then this page accepts nothing, and the hub never keeps a key itself.${doc ? " The rows below are examples with made-up endings." : ""}</p></section>`
      : this.viewOnly && this.loaded ? html`<p class="jv-keys__viewonly" role="status">View-only here. Change keys from the hub on Laptop A or B.</p>` : "";
    const marker = this.example ? html`<span class="jv-kicker jv-kicker--end">${this.scene?.preview ? "Scene preview · examples" : "Examples · not your keys"}</span>` : html`<span class="jv-kicker jv-kicker--end">Write-only</span>`;
    const list = !this.loaded ? html`<p class="jv-muted">Reading the keys…</p>`
      : !doc ? "" : html`<ul class="jv-keys__list" role="list">${rows.map((r) => this.row(r, now, writable))}${this.adder(writable)}</ul>`;
    return html`<div class="jv-view jv-keys">${head}${banner}${this.where(writable)}
      ${doc || !this.loaded ? html`<section class="jv-sheet jv-keys__sheet" aria-labelledby="keys-list"><h2 id="keys-list" class="jv-view__kicker"><span class="jv-kicker">Keys // Services</span>${marker}</h2>${list}</section>` : ""}
      ${this.viewOnly ? "" : html`<section class="jv-sheet jv-keys__sheet" aria-labelledby="keys-voice"><h2 id="keys-voice" class="jv-view__kicker"><span class="jv-kicker">Voice // ElevenLabs</span><span class="jv-kicker jv-kicker--end">Not a secret</span></h2><span data-voice-slot></span></section>`}
      <p class="jv-sr" id="keys-field-hint">Paste the key. It is sent once to Jarvis core on ${keptWords()} and never shown again.</p>
      <p class="jv-keys__foot">Stored only in Windows Credential Manager on ${keptWords()}. Every change lands in Activity, without the key.</p></div>`;
  }
  /** Which laptop these keys are on, and (when this laptop runs its own Jarvis) the tick box that sends a new key
   *  or voice ID to the other laptop's Jarvis too. Nothing here when there's one Jarvis and it's on this laptop. */
  where(writable) {
    if (!this.connected || !this.loaded) return "";
    const other = laptops.other, kept = laptops.kept;
    if (other && writable) return html`<section class="jv-sheet jv-keys__sheet jv-keys__both" aria-labelledby="keys-both">
        <h2 id="keys-both" class="jv-view__kicker"><span class="jv-kicker">Laptops // Two</span></h2>
        <label class="jv-keys__also"><input type="checkbox" data-k="also" data-key="also-other" aria-describedby="keys-both-hint" ${laptops.also ? "checked" : ""}> Also update ${other}</label>
        <p class="jv-keys__hint" id="keys-both-hint">This laptop runs its own Jarvis and so does ${other}. Ticked, a new key or voice ID you put in here goes to both, so they stay the same. Removing a service is done on each laptop by itself.</p></section>`;
    if (kept && kept !== "here") return html`<p class="jv-keys__where" role="note">Kept on ${kept}, the Jarvis this laptop is using. One change here covers both laptops.</p>`;
    return "";
  }
  row(r, now, writable) {
    const [code, said] = STATUS[r.status] || STATUS.missing;
    const label = short(r.label), w = word(r.kind), busy = this.busy === r.id, id = r.id;
    const live = r.live, next = r.next, prev = r.previous;
    const meta = live ? html`${masked(last4Of(r, live))}${last4Of(r, live) ? html`<span aria-hidden="true"> · </span>` : ""}<span>Added ${shortDate(live.added)}</span><span aria-hidden="true"> · </span><span>Checked ${live.checked ? ago(live.checked, now) : "never"}</span>${r.used ? html`<span aria-hidden="true"> · </span><span>Used ${ago(r.used, now)}</span>` : ""}`
      : html`<span>No ${w} yet.</span>`;
    const nextLine = next ? html`<p class="jv-keys__line">Next ${w} ${masked(last4Of(r, next))}: ${next.check === "checking" ? "being checked…" : next.check === "failed" ? `failed its check. ${REASON[next.reason] || ""}` : next.check === "shape_only" ? "looks right (no online check for this one)." : "passed its check, ready to make live."}</p>` : "";
    const prevLine = prev ? html`<p class="jv-keys__line">Old ${w} ${masked(last4Of(r, prev))} kept for ${minutesLeft(prev.until, now)} in case the new one fails, then removed by itself.${r.console_url ? html` ${this.revoke(r)}` : ""}</p>` : "";
    const note = this.notes[id] === "revoke" ? (r.console_url ? html`<p class="jv-keys__line">Old ${w} removed from ${keptWords()}. ${this.revoke(r)}</p>` : "")
      : this.notes[id] ? html`<p class="jv-keys__line jv-keys__note">${this.notes[id]}</p>` : "";
    const detail = r.detail ? html`<p class="jv-keys__line">${r.detail}</p>` : "";
    const btn = (k, text, cls = "", extra = "") => html`<button type="button" class="jv-btn jv-btn--small ${cls}" data-k="${k}" data-id="${id}" data-key="${k}-${id}" ${busy ? "disabled" : ""}>${text}<span class="jv-sr"> · ${label}${extra}</span></button>`;
    let actions = "";
    if (writable && this.confirming === id) {
      actions = html`<span class="jv-keys__confirm" role="group" aria-label="Remove the ${label} ${w}?"><span class="jv-keys__ask">Remove it? Jarvis stops using ${label}.</span>${btn("remove-yes", "Remove it")}${btn("keep", "Keep it")}</span>`;
    } else if (writable && this.openFor !== id) {
      actions = html`${r.status === "next_waiting" ? btn("promote", "Make live", "jv-keys__primary") : ""}
        ${prev ? btn("remove-old", "Remove old") : ""}
        ${r.status !== "checking" && r.status !== "next_waiting" && !prev ? btn("add", live ? `Add next ${w}` : `Add ${w}`) : ""}
        ${live || next ? btn("remove", "Remove", "jv-btn--quiet") : ""}`;
    } else if (!writable && this.loaded) {
      actions = html`<span class="jv-keys__locked">${r.status === "next_waiting" ? "Make live from a laptop" : ""}</span>`;
    }
    return html`<li class="jv-keys__row jv-keys__row--${r.status}" data-row="${id}" aria-labelledby="name-${id}">
      <div class="jv-keys__status">${glance(code, { word: said, size: "inline" })}</div>
      <div class="jv-keys__main">
        <h3 class="jv-keys__name" id="name-${id}" tabindex="-1" data-key="name-${id}">${r.label}${this.example ? html` <span class="jv-keys__ex">Example</span>` : ""}</h3>
        <p class="jv-keys__meta">${meta}</p>${detail}${nextLine}${prevLine}${note}
        ${this.openFor === id && writable ? this.form(id, label, w) : ""}
      </div>
      <div class="jv-keys__actions">${actions}</div></li>`;
  }
  revoke(r) {
    return html`<a class="jv-link jv-keys__revoke" href="${r.console_url}" target="_blank" rel="noopener noreferrer" data-key="revoke-${r.id}">Revoke it in ${short(r.label)}'s console<span class="jv-sr"> (opens in your browser)</span></a>`;
  }
  form(id, label, w) {
    this.field(id);
    return html`<div class="jv-keys__form" role="group" aria-label="New ${label} ${w}">
      <label class="jv-keys__label" for="keys-secret">Paste the new ${label} ${w}</label>
      <span data-secret-slot></span>
      <button type="button" class="jv-btn jv-btn--small jv-keys__primary" data-k="check" data-id="${id}" data-key="check-${id}">Check<span class="jv-sr"> the new ${label} ${w}</span></button>
      <button type="button" class="jv-btn jv-btn--small jv-btn--quiet" data-k="cancel" data-id="${id}" data-key="cancel-${id}">Cancel</button>
      <p class="jv-keys__hint">Sent once to Jarvis core and checked. Nothing changes until you make it live.</p></div>`;
  }
  adder(writable) {
    const addable = this.doc?.addable || [];
    if (!addable.length) return "";
    const open = this.openFor && addable.find((a) => a.id === this.openFor);
    const choice = addable.some((a) => a.id === this.addChoice) ? this.addChoice : "";
    return html`<li class="jv-keys__row jv-keys__row--add" data-row="add">
      <div class="jv-keys__status">${glance("parked", { word: "Optional", size: "inline" })}</div>
      <div class="jv-keys__main"><h3 class="jv-keys__name">Add a service</h3>
        <p class="jv-keys__meta">${addable.map((a) => a.label).join(" · ")}</p>
        ${open && writable ? this.form(open.id, short(open.label), word(open.kind)) : ""}</div>
      <div class="jv-keys__actions">${writable && !open ? html`<select class="jv-keys__select" data-k="choose" data-key="choose" aria-label="Service to add">
          <option value="">Choose a service</option>${addable.map((a) => html`<option value="${a.id}" ${a.id === choice ? "selected" : ""}>${a.label}</option>`)}</select>
        <button type="button" class="jv-btn jv-btn--small" data-k="add-service" data-key="add-service" ${choice ? "" : "disabled"}>Add key<span class="jv-sr"> for the chosen service</span></button>` : ""}</div></li>`;
  }
}
if (!customElements.get("jv-view-keys")) customElements.define("jv-view-keys", KeysView);

router.register("/controls/keys", "jv-view-keys", "controls", "Keys");  // the overseer may move this line to views/index.js
for (const [name, def] of Object.entries(SCENES)) {
  registerScene(name, { path: "/controls/keys", about: def.about, ...(def.size ? { size: def.size } : {}),
    // a fell-back key raises its "Your yes" flag on the Rail (the icon row's badge), as the hub will live
    ...(def.state === "fell_back" ? { patch: (s) => {
      const flag = keysYesFlag({ id: "anthropic", label: "Claude (Anthropic API)", status: "fell_back" }, s.now?.slice(0, 19) || localIso(new Date()));
      s.rail.slots.yes.items = [flag, ...s.rail.slots.yes.items.filter((i) => i.ref !== flag.ref)];
    } } : {}) });
}
