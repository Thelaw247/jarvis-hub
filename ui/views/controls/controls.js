// Controls (V05): small groups, each with at most four rows (tested).
// Interruptions · Voice and sound · Approvals · Look · Screens · Data and privacy. Under the hood and the demo controls are linked at the bottom.
// Every control is a real button with its state in words (On / Off), never colour alone.
// Deep links: #/controls/<setting> (the command bar uses them) scrolls to that row and focuses its control.
// Radio groups get one Tab stop and arrow keys from core/dom.js (rove + radioKey).
// Night HUD (N5b): each group is a square window led by a kicker; the theme segment is Night · Daylight · Sunset
// (theme.js's THEME_CHOICES, the chosen one from themeChoice(), so a stored "evening" or "system" shows as what
// it now means).
import { css, html, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";
import { THEME_CHOICES, themeChoice } from "../../core/theme.js";

css(import.meta.url);

const seg = (name, value, options, label) => html`<span class="jv-seg" role="radiogroup" aria-label="${label}">
  ${options.map(([v, label]) => html`<button type="button" role="radio" aria-checked="${value === v}" data-act="set" data-target="${name}" data-args='${JSON.stringify({ value: v })}' data-key="${name}-${v}">${label}</button>`)}</span>`;
const sw = (name, on, label) => html`<button type="button" class="jv-switch" role="switch" aria-checked="${!!on}" aria-label="${label}" data-act="set" data-target="${name}" data-args='${JSON.stringify({ value: !on })}' data-key="${name}">${on ? "On" : "Off"}</button>`;
const row = (id, title, sub, control) => html`<div class="jv-row" data-setting="${id}"><p class="jv-row__text"><b>${title}</b><span>${sub}</span></p>${control}</div>`;
const SHOWN_SOURCES = 4;  // the rest sit behind "More" (≤ 4 items per panel)

/** The settings the command bar can jump to: id (the #/controls/<id> path) → the row's title. */
export const SETTINGS = [
  ["interruption", "Interruption dial", "how chatty quiet balanced"], ["quiet_hours", "Quiet hours", ""], ["focus", "Focus mode", ""],
  ["game_mode", "Game mode", ""], ["approvals", "Approvals and standing permissions", "revoke"],
  ["theme", "Theme: Night, Daylight or Sunset", "look dark light hud evening"], ["motion", "Motion", "reduced animation"],
  ["plants", "Plants", "day plant leaves growth"], ["ambient", "Ambient screen", "idle clock orb"], ["stage", "Where Jarvis shows things", "stage window hub screen monitor windows"],
  ["voice_here", "Voice on this laptop", "talk here mic microphone speakers which laptop"], ["muted", "Microphone", "mute unmute mic listening"],
  ["earcons", "Sounds", "earcons chime tick wake tone audio"], ["address", "How Jarvis addresses you", "sir name formal"],
  ["sources", "Data sources", "canvas paws gmail calendar connectors"], ["tiers", "Privacy tiers", "private branches"],
  ["memory_paused", "Pause memory", "stop learning"], ["off_record", "Off the record", ""],
];
const TITLES = Object.fromEntries(SETTINGS.map(([id, label]) => [id, label]));
const STATUS = { ok: "Up to date", stale: "Out of date", error: "Needs attention", off: "Off" };

/** "22:30" (how the setting is stored) as he reads it: "10:30 pm". */
const clock = (hm) => { const [h, m] = String(hm).split(":").map(Number); return Number.isFinite(h) && Number.isFinite(m) ? `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}` : String(hm); };

/** This laptop's voice as its own hub runs it (contracts/voice_host.schema.json): where Jarvis is listening. */
const VOICE_HERE = {
  live: () => ["Jarvis is listening and speaking through this laptop.", html`<span class="jv-controls__never">Here</span>`],
  waiting: (v) => [`${v.device ? laptop(v.device) : "Another laptop"} has the voice. Talk here moves it to this one.`,
    html`<button type="button" class="jv-btn jv-btn--small" data-voice="take" data-key="voice-take">Talk here</button>`],
  starting: () => ["Starting the voice on this laptop.", html`<span class="jv-controls__never">Starting</span>`],
  down: (v) => [v.message || "The voice isn't connected. It tries again by itself.", html`<span class="jv-controls__never">Not connected</span>`],
  off: (v) => [v.message || "The voice isn't running on this laptop.", html`<span class="jv-controls__never">Off</span>`],
};
const laptop = (name) => String(name).replace(/^laptop-([a-z])$/i, (_m, x) => `Laptop ${x.toUpperCase()}`);
const VOICE_POLL_MS = 3000;

class ControlsView extends Jv {
  static props = ["params", "route"];
  setup() {
    this.stop = store.subscribe((_s, keys) => { if (keys.has("settings") || keys.has("demo")) this.update(); });
    this.moreOpen = false;
    this.addEventListener("toggle", (e) => { if (e.target.matches?.(".jv-controls__more")) this.moreOpen = e.target.open; }, true);
    // v0.15.0: the hub runs this laptop's voice itself; this row says where Jarvis is listening and moves it here
    this.voice = null;
    this.addEventListener("click", (e) => { if (e.target.closest?.('[data-voice="take"]')) this.takeVoice(); });
    this.readVoice();
    this.voiceTimer = setInterval(() => this.readVoice(), VOICE_POLL_MS);
  }
  teardown() { this.stop?.(); this.found = null; clearInterval(this.voiceTimer); }

  async readVoice() {
    let next = null;
    try {
      const r = await fetch("/api/voicehost", { cache: "no-store", headers: { Accept: "application/json" } });
      if (r.ok) next = await r.json();
    } catch { /* the hub itself is closing */ }
    if (JSON.stringify(next) !== JSON.stringify(this.voice)) { this.voice = next; this.update(); }
  }
  async takeVoice() {
    this.voice = { state: "starting", device: "", message: "" };   // feedback at once (<= 100 ms)
    this.update();
    try { await fetch("/api/voicehost/take", { method: "POST" }); } catch { /* shown by the next read */ }
    setTimeout(() => this.readVoice(), 600);
  }

  /** After a deep link (#/controls/<id>): bring the row into view and focus its control, once per link. */
  rendered() {
    const id = this.params?.[0];
    if (!id) { this.found = null; return; }
    if (id === this.found) return;
    this.found = id;
    if (!this.querySelector(`[data-setting="${CSS.escape(id)}"]`)) return;
    // two frames: after the router has set the view's scroll position for the new path
    requestAnimationFrame(() => requestAnimationFrame(() => {
      // looked up now, not before the wait: the view may have redrawn in between (the voice row's first read)
      const target = this.querySelector(`[data-setting="${CSS.escape(id)}"]`);
      if (!target) return;
      const control = target.querySelector('button:not([tabindex="-1"]), a[href], summary') || target;
      if (!control.matches("button, a, summary")) control.tabIndex = -1;
      control.focus({ preventScroll: true });
      target.scrollIntoView({ block: "center" });
    }));
  }
  render() {
    const s = store.state, c = s.settings, q = c.quiet_hours || { on: false, from: "22:30", to: "07:30" };
    const perms = c.standing_permissions || [], sources = c.sources || [];
    const tiers = (c.tiers || []).map((t) => s.branches.find((b) => b.id === t.branch_id)?.name).filter(Boolean);
    const shown = sources.slice(0, SHOWN_SOURCES), rest = sources.slice(SHOWN_SOURCES);
    const source = (x) => html`<li><span>${x.name} <span class="jv-muted">· ${STATUS[x.status] || STATUS.ok}${x.last_sync ? ` · ${x.last_sync}` : ""}</span></span>
      <button type="button" class="jv-switch" role="switch" aria-checked="${!!x.on}" aria-label="${x.name}" data-act="set" data-target="source:${x.id}" data-args='${JSON.stringify({ value: !x.on })}' data-key="src-${x.id}">${x.on ? "On" : "Off"}</button></li>`;
    const here = TITLES[this.params?.[0]];
    return html`<div class="jv-view">
      <header class="jv-view__head"><nav class="jv-crumbs" aria-label="Breadcrumb">${here
        ? html`<a href="#/controls" data-nav="/controls" data-key="crumb">Controls</a><span aria-hidden="true">›</span><span aria-current="page">${here}</span>`
        : html`<span aria-current="page">Controls</span>`}</nav>
        <h1>Controls</h1><p class="jv-view__sub">How much Jarvis interrupts, what it may do, how it looks, what it can see.</p></header>
      <div class="jv-controls__grid">
        <section class="jv-sheet" aria-labelledby="c-int"><h2 id="c-int" class="jv-view__kicker"><span class="jv-kicker">Interruptions</span></h2>
          ${row("interruption", "How chatty", "Quiet speaks only when asked. Chatty offers more.", seg("interruption", c.interruption, [["quiet", "Quiet"], ["balanced", "Balanced"], ["chatty", "Chatty"]], "How chatty"))}
          ${row("quiet_hours", "Quiet hours", `No remarks between ${clock(q.from)} and ${clock(q.to)}.`, html`<button type="button" class="jv-switch" role="switch" aria-checked="${!!q.on}" aria-label="Quiet hours" data-act="set" data-target="quiet_hours" data-args='${JSON.stringify({ value: { ...q, on: !q.on } })}' data-key="quiet">${q.on ? "On" : "Off"}</button>`)}
          ${row("focus", "Focus", "Hold everything except what you ask for.", sw("focus", c.focus, "Focus mode"))}
          ${row("game_mode", "Game mode", "Auto turns it on when a game is running. The strip hides.", seg("game_mode", c.game_mode || "auto", [["auto", "Auto"], ["on", "On"], ["off", "Off"]], "Game mode"))}
        </section>
        <section class="jv-sheet" aria-labelledby="c-voice"><h2 id="c-voice" class="jv-view__kicker"><span class="jv-kicker">Voice // Sound</span></h2>
          ${(() => { const v = this.voice || { state: "starting" }; const [text, control] = (VOICE_HERE[v.state] || VOICE_HERE.off)(v); return row("voice_here", "Voice on this laptop", text, control); })()}
          ${row("muted", "Microphone", c.muted ? "Off: Jarvis hears nothing until you turn it back on here." : "On. Turn it off and Jarvis hears nothing until you turn it back on here.", html`<button type="button" class="jv-switch" role="switch" aria-checked="${!c.muted}" aria-label="Microphone" data-act="set" data-target="muted" data-args='${JSON.stringify({ value: !c.muted })}' data-key="muted">${c.muted ? "Off" : "On"}</button>`)}
          ${row("earcons", "Sounds", "Minimal: a soft rise on the first wake and a tick when Jarvis has heard you. Full adds one low tone for something critical. Never in quiet hours or game mode.", seg("earcons", c.earcons || "minimal", [["off", "Off"], ["minimal", "Minimal"], ["full", "Full"]], "Sounds"))}
          ${row("address", "How Jarvis addresses you", "At most once in an exchange, and only in greetings, alerts and read-backs.", seg("address", c.address || "name", [["name", "By name"], ["sir", "Sir"], ["none", "Not at all"]], "How Jarvis addresses you"))}
        </section>
        <section class="jv-sheet" aria-labelledby="c-app"><h2 id="c-app" class="jv-view__kicker"><span class="jv-kicker">Approvals</span></h2>
          ${row("approvals-how", "Reading is automatic. Every change waits for your yes.", "Jarvis reads the change back out loud first. You can also answer in Activity.", html`<a class="jv-btn jv-btn--small" href="#/activity" data-nav="/activity" data-key="go-activity">Open Activity</a>`)}
          <div class="jv-row" data-setting="approvals"><div class="jv-row__text"><b>Standing permissions</b><span>${perms.length ? "Things you've said Jarvis may do without asking each time." : "None. Jarvis asks every time."}</span>
            ${perms.length ? html`<ul class="jv-controls__list">${perms.slice(0, 4).map((p) => html`<li><span>${p.text} <span class="jv-muted">· since ${p.granted}</span></span>
              <button type="button" class="jv-btn jv-btn--small" data-act="revoke" data-target="${p.id}" data-key="revoke-${p.id}">Revoke<span class="jv-sr">: ${p.text}</span></button></li>`)}</ul>` : ""}</div></div>
          ${row("never", "Never", (c.never || ["Submitting assignments", "Payments"]).join(" · "), html`<span class="jv-controls__never">Always off</span>`)}
        </section>
        <section class="jv-sheet" aria-labelledby="c-look"><h2 id="c-look" class="jv-view__kicker"><span class="jv-kicker">Look</span></h2>
          ${row("theme", "Theme", "Night is the HUD. Daylight is for bright rooms. Sunset switches at Saskatoon's real sunset and sunrise.", seg("theme", themeChoice(c.theme, matchMedia("(prefers-color-scheme: dark)").matches), THEME_CHOICES, "Theme"))}
          ${row("motion", "Motion", "Full follows Windows: if its animations are off, the hub goes still too. Always keeps the orb and windows moving anyway. Reduced keeps state changes and drops the rest.", seg("motion", c.motion, [["full", "Full"], ["always", "Always"], ["reduced", "Reduced"], ["off", "Off"]], "Motion"))}
          ${row("plants", "Plants", "Daylight: the day plant and the Life Map's leaves. Night: a quiet line-art growth mark.", sw("plants", c.plants !== false, "Plants"))}
        </section>
        <section class="jv-sheet" aria-labelledby="c-screens"><h2 id="c-screens" class="jv-view__kicker"><span class="jv-kicker">Screens</span></h2>
          ${row("ambient", "Ambient screen", "Return to the orb and clock after two idle minutes.", sw("ambient", c.ambient !== false, "Ambient screen"))}
          ${row("stage", "Where Jarvis shows things", c.stage === "window" ? "Stage window: what Jarvis pulls up goes to a second, full-screen window. Takes effect the next time the hub opens." : "On the hub: one window. What Jarvis pulls up shows here; drag one off the edge to give it a window of its own.", seg("stage", c.stage === "window" ? "window" : "hub", [["hub", "On the hub"], ["window", "Stage window"]], "Where Jarvis shows things"))}
        </section>
        <section class="jv-sheet" aria-labelledby="c-data"><h2 id="c-data" class="jv-view__kicker"><span class="jv-kicker">Data // Privacy</span></h2>
          <div class="jv-row" data-setting="sources"><div class="jv-row__text"><b>Data sources</b><span>What Jarvis can read. Turning one off stops new reads at once.</span>
            <ul class="jv-controls__list">${shown.map(source)}</ul>
            ${rest.length ? html`<details class="jv-controls__more" ${this.moreOpen ? "open" : ""}><summary class="jv-btn jv-btn--small" data-key="more-sources">${rest.length} more<span class="jv-sr"> data sources</span></summary>
              <ul class="jv-controls__list">${rest.map(source)}</ul></details>` : ""}</div></div>
          ${row("tiers", "Private branches", tiers.length ? `${tiers.join(" · ")}: never shown on the ambient screen or in pushed windows.` : "No private branches.", html`<a class="jv-btn jv-btn--small" href="#/life" data-nav="/life" data-key="go-life">Open Life</a>`)}
          ${row("memory_paused", "Pause memory", "Jarvis stops learning new things until you turn this off.", sw("memory_paused", c.memory_paused, "Pause memory"))}
          ${row("off_record", "Off the record", "Nothing from this session is kept.", sw("off_record", c.off_record, "Off the record"))}
        </section>
      </div>
      <footer class="jv-controls__foot">
        <a class="jv-btn" href="#/controls/reach" data-nav="/controls/reach" data-key="reach">What Jarvis can do</a>
        <a class="jv-btn" href="#/controls/hood" data-nav="/controls/hood" data-key="hood">Under the hood</a>
        <a class="jv-btn" href="#/controls/keys" data-nav="/controls/keys" data-key="api-keys">Keys</a>
        <button type="button" class="jv-btn" data-act="shortcuts" data-key="keys">Keyboard shortcuts</button>
        ${s.mode === "demo" ? html`<span class="jv-controls__demo" id="demo"><span><b>Demo mode.</b> A scripted day, not your real data.</span>
          <button type="button" class="jv-btn jv-btn--small" data-act="demo" data-target="restart" data-key="demo-restart">Play the demo day again</button></span>` : ""}
      </footer></div>`;
  }
}
ControlsView.define("jv-view-controls");

registerScene("controls", { path: "/controls", about: "The five control groups" });
registerScene("controls-quiet", { path: "/controls", about: "Quiet, focus on, memory paused, no standing permissions", patch: (s) => { Object.assign(s.settings, { interruption: "quiet", focus: true, memory_paused: true, standing_permissions: [], theme: "sunset", motion: "reduced" }); } });
registerScene("controls-stage-hub", { path: "/controls/stage", about: "Where Jarvis shows things set to On the hub (the old behaviour)", patch: (s) => { s.settings.stage = "hub"; } });
registerScene("controls-live", { path: "/controls", about: "Controls with the theme left to the settings" });
registerScene("controls-voice", { path: "/controls/voice_here", about: "Voice on this laptop (the hub runs it): where Jarvis is listening, Talk here, the microphone switch" });
