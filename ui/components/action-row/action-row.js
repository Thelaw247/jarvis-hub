// <jv-action-row>: one receipt in the Activity log: what · why · sources · result · Undo with its window.
//   .action = action contract   .now = Date     Held-back remarks (kind "held") show why Jarvis stayed quiet.
// After the undo window the row stays and the button goes (HUB_TRUST §1.5); the button says how long is left
// ("Undo · until 9:12 am tomorrow") and goes by itself when the window closes.
// Attribute `quiet`: an answer that did nothing (he said no), shown as a calm row with no undo.
// The row itself can take focus (tabindex -1), so Activity can land focus on a receipt after Yes or Undo.
// Night HUD (N5b): the time in mono tabular figures, the kind as a kicker, and the receipt's state as a glance
// mark: Done (cyan-hi disc), Undone and Held back (dashed ring); a "no" is a quiet row with no mark.
import { asDate, clockTime, css, html, icon, Jv, shortDate, whenWords } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
/** "until 9:12 pm", "until 9:12 am tomorrow", "until Wed 9:12 am", "until Nov 30": how long Undo still works. */
export function untilWords(until, now) {
  const u = asDate(until), n = asDate(now);
  const day = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(u) - day(n)) / 864e5);
  if (days <= 0) return `until ${clockTime(u)}`;
  if (days === 1) return `until ${clockTime(u)} tomorrow`;
  if (days < 7) return `until ${DAYS[u.getDay()]} ${clockTime(u)}`;
  return `until ${shortDate(u)}`;
}

const CATEGORY = { calendar: ["calendar", "Calendar"], files: ["file", "Files"], messages: ["mail", "Messages"], memory: ["spark", "Memory"], tree: ["leaf", "Life Map"], skills: ["gauge", "Skills"] };

class ActionRow extends Jv {
  static props = ["action", "now"];
  static attrs = ["quiet"];
  teardown() { clearTimeout(this._expire); }
  render() {
    const a = this.action;
    if (!a) return html``;
    const now = asDate(this.now || store.now());
    const [glyph, word] = CATEGORY[a.category] || CATEGORY.skills;
    const held = a.kind === "held";
    const quiet = this.hasAttribute("quiet");
    const canUndo = !quiet && a.undo && !a.undone && asDate(a.undo.until) > now;
    clearTimeout(this._expire);
    if (canUndo && store.state.mode !== "scene") {  // the button goes by itself when the window closes
      const left = asDate(a.undo.until) - now;
      if (left < 2 ** 31 - 1) this._expire = setTimeout(() => this.update(), left + 50);
    }
    this._sources = a.sources || [];
    const tag = held ? "Held back" : quiet ? "You said no" : "";
    return html`<article class="jv-action-row ${a.undone ? "jv-action-row--undone" : ""} ${held ? "jv-action-row--held" : ""} ${quiet ? "jv-action-row--quiet" : ""}" tabindex="-1" aria-labelledby="what-${a.id}">
      <p class="jv-action-row__when"><time datetime="${a.ts}">${whenWords(a.ts, now)}</time><span class="jv-action-row__cat">${icon(glyph)}${word}</span>
        ${quiet ? "" : a.undone ? html`<jv-glance state="parked" label="Undone"></jv-glance>` : held ? html`<jv-glance state="parked" label="Held"></jv-glance>` : html`<jv-glance state="done" label="Done"></jv-glance>`}</p>
      <div class="jv-action-row__main">
        <h3 class="jv-action-row__what" id="what-${a.id}">${tag ? html`<span class="jv-action-row__tag">${tag}</span> ` : ""}${a.what}${a.undone ? html`<span class="jv-sr"> (undone)</span>` : ""}</h3>
        <p class="jv-action-row__why"><span class="jv-label">Why</span> ${a.why}</p>
        ${a.result ? html`<p class="jv-action-row__result">${a.result}</p>` : ""}
        ${this._sources.length ? html`<p class="jv-action-row__sources">${this._sources.map(() => html`<jv-source-chip></jv-source-chip>`)}</p>` : ""}
      </div>
      <div class="jv-action-row__undo">
        ${a.undone ? html`<span class="jv-action-row__state">${icon("undo")}Undone</span>`
          : canUndo ? html`<button type="button" class="jv-btn jv-btn--small" data-act="undo" data-target="${a.id}" data-key="undo">${icon("undo")}Undo · ${untilWords(a.undo.until, now)}<span class="jv-sr">: ${a.what}</span></button>`
          : quiet ? html`<span class="jv-muted jv-action-row__state">Nothing was done</span>`
          : a.undo ? html`<span class="jv-muted jv-action-row__state">Undo window has passed</span>`
          : held ? "" : html`<span class="jv-muted jv-action-row__state">Nothing to undo</span>`}
      </div>
    </article>`;
  }
  rendered() { this.querySelectorAll("jv-source-chip").forEach((chip, i) => { chip.source = this._sources[i]; }); }
}
ActionRow.define("jv-action-row");

const row = (id, change) => (s) => { const a = s.actions.find((x) => x.id === id); change?.(a); return el("jv-action-row", { action: a, now: s.now }); };
registerGallery("action-row", [
  { label: "Done, can be undone", wide: true, build: row("a-sync") },
  { label: "Undone", wide: true, build: row("a-moved", (a) => { a.undone = true; }) },
  { label: "Undo window has passed", wide: true, build: row("a-quiz", (a) => { a.undo.until = "2026-11-16T10:00:00"; }) },
  { label: "Held back (and why)", wide: true, build: row("a-held") },
  { label: "Nothing to undo", wide: true, build: row("a-old") },
  { label: "You said no (quiet)", wide: true, build: (s) => el("jv-action-row", { action: { id: "declined-ap-week", ts: s.now, kind: "done", what: "Book this week's study plan", why: "You said no. Nothing was changed.", category: "calendar" }, now: s.now }, { quiet: "" }) },
], { about: "What · why · sources · result · Undo with its window." });
