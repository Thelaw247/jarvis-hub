// Fallback view: shown for any route whose view isn't built yet, and as the live event log
// (Controls › Under the hood links to it). It proves the plumbing: state loaded, events arriving.
import { html, Jv } from "./dom.js";
import { registerScene } from "./scenes.js";
import { store } from "./store.js";

class Placeholder extends Jv {
  static props = ["params", "route"];
  setup() { this.stop = store.subscribe(() => this.update()); }
  teardown() { this.stop?.(); }
  render() {
    const s = store.state;
    const log = s.ui.log.slice(0, 8);
    return html`<section class="jv-placeholder jv-sheet" aria-labelledby="ph-title">
      <h1 id="ph-title">${this.route?.title || "Hub"}</h1>
      <p class="jv-muted">This view is on its way. The hub is running in ${s.mode} mode and its live events are below.</p>
      <dl class="jv-placeholder__facts">
        <div><dt class="jv-label">Orb</dt><dd>${s.orb.state}</dd></div>
        <div><dt class="jv-label">Windows</dt><dd>${s.windows.length}</dd></div>
        <div><dt class="jv-title">Waiting for you</dt><dd>${s.approvals.filter((a) => a.status === "pending").length}</dd></div>
        <div><dt class="jv-label">Branches</dt><dd>${s.branches.length}</dd></div>
      </dl>
      <h2 class="jv-label">Latest events</h2>
      <ol class="jv-placeholder__log jv-telemetry" aria-live="off">
        ${log.length ? log.map((e) => html`<li>${String(e.ts).slice(11, 19)} · ${e.type}</li>`) : html`<li>Nothing yet.</li>`}
      </ol>
    </section>`;
  }
}
Placeholder.define("jv-view-placeholder");

registerScene("shell", { path: "/debug", about: "The frame and the event log" });
