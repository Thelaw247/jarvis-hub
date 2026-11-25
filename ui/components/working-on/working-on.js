// <jv-working-on>: what Jarvis is working on in the background ("Syncing Canvas · 60%"). Real progress only:
// a segmented scan bar (2 elements) lit up to the reported share, with a cyan chunk sweeping across while it
// runs; plain words when the job can't report a number. Finished jobs show the done glance, failed ones the
// "needs you" glance with what to do. Reduced motion and the strip: words only.   .jobs = [job]
import { css, html, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import { glance } from "../glance/glance.js";

css(import.meta.url);

class WorkingOn extends Jv {
  static props = ["jobs"];
  render() {
    const jobs = (this.jobs || []).slice(0, 3);
    if (!jobs.length) return html``;
    return html`<ul class="jv-working-on" aria-label="Jarvis is working on">
      ${jobs.map((j) => {
        const pct = typeof j.progress === "number" ? Math.round(j.progress * 100) : null;
        const running = j.state === "running";
        return html`<li class="jv-working-on__chip jv-working-on__chip--${j.state}" title="${j.detail || j.label}">
          ${j.state === "done" ? glance("done", { size: "rail", bare: true }) : j.state === "failed" ? glance("soon", { size: "rail", bare: true, word: "Needs you" }) : ""}
          <span class="jv-working-on__label">${j.label}${j.state === "failed" ? " didn't finish" : j.state === "done" ? " · done" : pct == null ? " · working" : ""}</span>
          ${running ? html`<span class="jv-working-on__bar" ${pct != null ? html`role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="${j.label}"` : html`aria-hidden="true"`} style="--p:${pct ?? 0}%"><span class="jv-working-on__chunk"></span></span>` : ""}
          ${pct != null && running ? html`<span class="jv-working-on__pct">${pct}%</span>` : ""}
          ${j.detail && j.state !== "done" ? html`<span class="jv-sr">: ${j.detail}</span>` : ""}
        </li>`;
      })}
    </ul>`;
  }
}
WorkingOn.define("jv-working-on");

const chips = (jobs) => el("jv-working-on", { jobs });
registerGallery("working-on", [
  { label: "With real progress", build: () => chips([{ id: "j1", label: "Planning your week", state: "running", progress: 0.6, detail: "Finding free time in your calendar" }]) },
  { label: "Progress unknown", build: () => chips([{ id: "j2", label: "Syncing Canvas", state: "running", progress: null }]) },
  { label: "Two jobs", build: () => chips([{ id: "j1", label: "Syncing Canvas", state: "running", progress: 0.3 }, { id: "j2", label: "Building study pack", state: "running", progress: 0.85 }]) },
  { label: "Finished", build: () => chips([{ id: "j4", label: "Study pack for lecture 21", state: "done", progress: 1 }]) },
  { label: "Didn't finish", build: () => chips([{ id: "j3", label: "Gmail sync", state: "failed", detail: "Sign in again from Controls" }]) },
], { about: "Background jobs with real progress: a segmented scan bar while Jarvis works. Words only under reduced motion. Empty when nothing is running." });
