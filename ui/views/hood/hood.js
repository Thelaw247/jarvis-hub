// Under the hood (V06), off the main navigation (Controls › Under the hood): latency per stage, connectors,
// spend, voice credits, the "Know De Wet" score trend, placement accuracy, backups, the weekly self-report.
// Night HUD (N5b): an instrument panel. Each latency stage is a readout (p50 big in mono, tabular figures) over a
// gauge (p50 fill, p95 tick, target line); connections show sync ages in mono with their health as shape + colour
// + word. Green is allowed here and only here: it means a system is healthy.
import { css, html, icon, Jv } from "../../core/dom.js";
import { registerScene } from "../../core/scenes.js";
import { store } from "../../core/store.js";

css(import.meta.url);

const STATUS = { ok: ["check", "Working"], stale: ["alert", "Out of date"], error: ["alert", "Needs attention"], off: ["close", "Off"] };
/** "Hear (speech to text)" → ["Hear", "Speech to text"] */
const stageWords = (stage) => { const m = /^(\S+)\s*\((.*)\)\s*$/.exec(stage || ""); return m ? [m[1], m[2][0].toUpperCase() + m[2].slice(1)] : [stage, ""]; };
/** A latency gauge's scale and marks as fractions of its width (tested). */
export function gauge(l) {
  const max = Math.max((l.target_ms || 0) * 1.25, l.p95_ms * 1.1, l.p50_ms * 1.2, 1);
  return { p50: l.p50_ms / max, p95: l.p95_ms / max, target: l.target_ms ? l.target_ms / max : null, over: !!l.target_ms && l.p95_ms > l.target_ms };
}
const share = (v) => `${Math.round(v * 1000) / 10}%`;

class HoodView extends Jv {
  static props = ["params", "route"];
  setup() { this.stop = store.subscribe((_s, keys) => { if (keys.has("metrics")) this.update(); }); }
  teardown() { this.stop?.(); }
  render() {
    const m = store.state.metrics;
    const crumb = html`<nav class="jv-crumbs" aria-label="Breadcrumb"><a href="#/controls" data-nav="/controls" data-key="crumb">Controls</a><span aria-hidden="true">›</span><span aria-current="page">Under the hood</span></nav>`;
    const sub = "How fast Jarvis is, what it costs, and whether it's getting to know you.";
    const head = html`<header class="jv-view__head">${crumb}<h1>Under the hood</h1><p class="jv-view__sub">${sub}</p></header>`;
    if (!m) return html`<div class="jv-view jv-view--narrow">${head}<jv-notice kind="empty" heading="No measurements yet" text="They appear after Jarvis has been running for a little while."></jv-notice></div>`;
    const spend = m.spend, pct = spend ? Math.round((spend.claude_usd / spend.credit_usd) * 100) : 0;
    const credits = m.credits, left = credits ? Math.round((credits.elevenlabs_left / credits.elevenlabs_total) * 100) : 0;
    const slow = (m.latency || []).filter((l) => l.target_ms && l.p95_ms > l.target_ms);
    // Panel titles here are mostly longer than two words, so all of them are sentence-case headings (.jv-title);
    // small caps stay for the short sub-labels inside (Learned, Got wrong).
    // Panel headings are kickers of one or two words each (no long caps), with a type or status on the right.
    const panel = (id, title, body, end = "") => html`<section class="jv-card jv-hood__panel" aria-labelledby="${id}">
      <h2 id="${id}" class="jv-view__kicker jv-hood__title"><span class="jv-kicker">${title}</span>${end ? html`<span class="jv-kicker jv-kicker--end">${end}</span>` : ""}</h2>${body}</section>`;
    const readout = (l) => {
      const [word, detail] = stageWords(l.stage), g = gauge(l);
      return html`<div class="jv-hood__gauge ${g.over ? "jv-hood__gauge--over" : ""}">
        <p class="jv-kicker">${word}</p>
        <p class="jv-hood__read"><span class="jv-hood__num">${l.p50_ms}</span><span class="jv-hood__unit">ms</span><span class="jv-sr"> typical</span></p>
        ${detail ? html`<p class="jv-hood__stage">${detail}</p>` : ""}
        <div class="jv-hood__bar" aria-hidden="true"><span class="jv-hood__fill" style="width:${share(g.p50)}"></span><span class="jv-hood__p95" style="left:${share(g.p95)}"></span>${g.target != null ? html`<span class="jv-hood__target" style="left:${share(g.target)}"></span>` : ""}</div>
        <p class="jv-hood__sub">slowest 5%: ${l.p95_ms} ms${l.target_ms ? html` · target ${l.target_ms} ms` : ""}${g.over ? html` · <span class="jv-hood__over">over</span>` : ""}</p></div>`;
    };
    return html`<div class="jv-view">
      ${head}
      ${panel("h-speed", "Speed", html`
        <p class="jv-hood__verdict">${slow.length ? html`<span class="jv-hood__warn">${icon("alert")}${slow.length} over target</span>` : html`<span class="jv-hood__ok">${icon("check")}All within target</span>`}</p>
        <div class="jv-hood__tiles jv-hood__gauges">${(m.latency || []).slice(0, 4).map(readout)}</div>`, "p50 ms")}
      ${panel("h-cost", "Cost", html`<div class="jv-hood__tiles">
        <jv-big-number label="Claude spend this month${pct >= 70 ? " · past 70%" : ""}" value="$${(spend?.claude_usd ?? 0).toFixed(2)}" sub="${pct}% of the $${spend?.credit_usd ?? 0} credit. Jarvis warns you at 70%."></jv-big-number>
        <jv-big-number label="Voice credits left" value="${left}" unit="%" sub="${(credits?.elevenlabs_left ?? 0).toLocaleString("en-CA")} of ${(credits?.elevenlabs_total ?? 0).toLocaleString("en-CA")} characters"></jv-big-number>
        <jv-big-number label="Filed on the right branch" value="${Math.round((m.placement_accuracy ?? 0) * 100)}" unit="%" sub="Wrong ones land in Unsorted for you to fix."></jv-big-number>
        <jv-big-number label="Last backup" value="${m.backup?.last || "Not yet"}" sub="Restore test: ${m.backup?.restore_test || "not run yet"}"></jv-big-number>
      </div>`, "Safety")}
      <div class="jv-view__cols">
        ${panel("h-know", "Know you", html`<jv-mini-chart id="eval" heading="“Know De Wet” score by week" type="line" unit="%" tone="growth"></jv-mini-chart>`, "Score trend")}
        ${panel("h-week", "This week", html`<div class="jv-hood__report">
          <div><h3 class="jv-label">Learned</h3><ul>${(m.self_report?.learned || []).slice(0, 3).map((x) => html`<li>${x}</li>`)}</ul></div>
          <div><h3 class="jv-label">Got wrong</h3><ul>${(m.self_report?.got_wrong || []).slice(0, 3).map((x) => html`<li>${x}</li>`)}</ul></div></div>`, "Self-report")}
      </div>
      <section class="jv-sheet" aria-labelledby="h-con"><h2 id="h-con" class="jv-view__kicker"><span class="jv-kicker">Connections</span><span class="jv-kicker jv-kicker--end">Last sync</span></h2>
        ${(m.connectors || []).map((c) => { const [glyph, word] = STATUS[c.status] || STATUS.ok; return html`<div class="jv-row jv-hood__con"><p class="jv-row__text"><b>${c.name}</b>${c.note ? html`<span>${c.note}</span>` : ""}</p>
          <span class="jv-hood__age">${c.last_sync ? html`<span class="jv-sr">Last sync: </span>${c.last_sync}` : "Never"}</span><span class="jv-hood__status jv-hood__status--${c.status}">${icon(glyph)}${word}</span></div>`; })}
        <p class="jv-hood__foot"><a class="jv-link" href="#/debug" data-nav="/debug" data-key="log">Live event log</a></p>
      </section></div>`;
  }
  rendered() { const chart = this.$("#eval"); if (chart) chart.data = (store.state.metrics.eval || []).map((e) => ({ label: e.week, value: e.score })); }
}
HoodView.define("jv-view-hood");

registerScene("hood", { path: "/controls/hood", about: "Speed, cost, score trend, connections" });
registerScene("hood-over", { path: "/controls/hood", about: "One stage over target, spend past 70%", patch: (s) => { s.metrics.latency[1].p95_ms = 1150; s.metrics.spend.claude_usd = 74.1; } });
registerScene("hood-empty", { path: "/controls/hood", about: "Before any measurements", patch: (s) => { s.metrics = null; } });
