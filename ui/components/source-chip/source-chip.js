// <jv-source-chip> shows where a claim came from: icon + word, never colour alone (HUB_TRUST §3).
//   .source = { kind, label, unexpected?, snippet?, ref? }   (contracts/common: source)
// With a snippet it opens to show the evidence itself, so checking is cheap.
// <jv-confidence level="likely|guess|sure"> shows confidence in words. Sure is hidden unless show-sure.
import { css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const KIND_ICON = { you: "you", canvas: "canvas", syllabus: "book", calendar: "calendar", paws: "calendar", crowdmark: "book", gmail: "mail", file: "file", jarvis: "spark", web: "globe", guess: "help" };

class SourceChip extends Jv {
  static props = ["source"];
  render() {
    const s = this.source;
    if (!s) return "";
    const inner = html`${icon(KIND_ICON[s.kind] || "file")}<span class="jv-source-chip__label">${s.label}</span>
      ${s.unexpected ? html`<span class="jv-source-chip__flag" title="You might not expect this source here">${icon("alert")}<span class="jv-sr">, a source you might not expect</span></span>` : ""}`;
    const cls = `jv-source-chip__chip${s.unexpected ? " jv-source-chip__chip--unexpected" : ""}${s.kind === "guess" ? " jv-source-chip__chip--guess" : ""}`;
    if (!s.snippet) return html`<span class="${cls}"><span class="jv-sr">Source: </span>${inner}</span>`;
    return html`<details class="jv-source-chip__details">
      <summary class="${cls}" data-key="chip"><span class="jv-sr">Source: </span>${inner}<span class="jv-sr">. Show the evidence</span></summary>
      <blockquote class="jv-source-chip__evidence">“${s.snippet}”<footer class="jv-muted">${s.label}${s.ref ? ` · ${s.ref}` : ""}</footer></blockquote>
    </details>`;
  }
}
SourceChip.define("jv-source-chip");

const WORDS = { sure: "Sure", likely: "Likely", guess: "Guess" };
class Confidence extends Jv {
  static attrs = ["level", "show-sure"];
  render() {
    const level = this.getAttribute("level");
    if (!WORDS[level] || (level === "sure" && !this.hasAttribute("show-sure"))) return "";
    return html`<span class="jv-confidence jv-confidence--${level}">${icon(level === "sure" ? "check" : level === "likely" ? "leaf" : "help")}<span class="jv-sr">Confidence: </span>${WORDS[level]}</span>`;
  }
}
Confidence.define("jv-confidence");

const chip = (source) => el("jv-source-chip", { source });
registerGallery("source-chip", [
  { label: "You said it", build: () => chip({ kind: "you", label: "You · Nov 13" }) },
  { label: "Official sources", build: () => { const r = el("div", { className: "jv-chip-row" }); [["canvas", "Canvas"], ["paws", "PAWS"], ["calendar", "Calendar"], ["file", "PPS 7.pdf"], ["jarvis", "Jarvis"], ["web", "usask.ca"]].forEach(([kind, label]) => r.append(chip({ kind, label }))); return r; } },
  { label: "With evidence (opens)", build: () => chip({ kind: "syllabus", label: "Syllabus GE 122 p.2", snippet: "Late submissions: 10% per day to a maximum of three days." }) },
  { label: "Unexpected source", build: () => chip({ kind: "gmail", label: "Gmail", unexpected: true, snippet: "Tutorial section T05 will meet in 2C02 from Nov 18." }) },
  { label: "Guess", build: () => chip({ kind: "guess", label: "Guess" }) },
  { label: "Confidence words", build: () => { const r = el("div", { className: "jv-chip-row" }); ["sure", "likely", "guess"].forEach((level) => r.append(el("jv-confidence", {}, { level, "show-sure": true }))); return r; } },
], { about: "Every claim carries one. Icon and word, never colour alone." });
