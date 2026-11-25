// <jv-file-tile>: a file as a picture with its big label, plus "Open it".   .file = file (contracts/now_card $defs.file)
// With a `thumb` (the page rendered when the file was filed, or a deck's own thumbnail) it shows that picture
// with the file's name laid over it (HUD v2 §5: picture + big label). Without one, the page is drawn from the
// file's preview lines on the light reading sheet: no image to load, so it appears with the event (≤ 100 ms).
// The kind of file is shown by its icon and words, never by colour. "Open it" emits jv-act { action: "open", target: file id }.
import { css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";
import "../thumb/thumb.js";

css(import.meta.url);

const KIND = { pdf: ["file", "PDF"], slides: ["class", "Slides"], doc: ["file", "Document"], sheet: ["list", "Sheet"], code: ["file", "Code"], folder: ["folder", "Folder"], image: ["file", "Image"] };

class FileTile extends Jv {
  static props = ["file"];
  static attrs = ["compact"];
  render() {
    const f = this.file;
    if (!f) return html``;
    const [glyph, word] = KIND[f.kind] || KIND.doc;
    const lines = (f.preview || []).slice(0, 5);
    const compact = this.hasAttribute("compact");
    const picture = compact ? "" : f.thumb ? html`<jv-thumb class="jv-file-tile__thumb" label="${f.page ? `${f.name.replace(/\.[a-z0-9]+$/i, "")} · ${f.page.replace(/ of \d+$/, "")}` : f.name}"${f.thumb.kind === "page" ? html` ratio="page"` : ""}></jv-thumb>`
      : html`<div class="jv-file-tile__page${lines.length ? " jv-paper" : ""}" aria-hidden="true">
        ${lines.length ? lines.map((l, i) => html`<p class="${i === 0 ? "jv-file-tile__line jv-file-tile__line--title" : "jv-file-tile__line"}">${l}</p>`) : html`<span class="jv-file-tile__glyph">${icon(glyph)}</span>`}
      </div>`;
    return html`<figure class="jv-file-tile${compact ? " jv-file-tile--compact" : ""}">
      ${picture}
      <figcaption class="jv-file-tile__meta">
        <p class="jv-file-tile__info">${icon(glyph)}<span>${word}${f.page ? ` · ${f.page}` : ""}</span></p>
        <p class="jv-file-tile__name" title="${f.name}">${f.name}</p>
        ${f.path ? html`<p class="jv-telemetry jv-file-tile__path" title="${f.path}">${f.path}</p>` : ""}
        <button type="button" class="jv-btn jv-btn--small" data-act="open" data-target="${f.id}" data-key="open">Open it<span class="jv-sr">: ${f.name}</span></button>
      </figcaption>
    </figure>`;
  }
  rendered() { const t = this.$("jv-thumb"); if (t) t.thumb = this.file?.thumb; }
}
FileTile.define("jv-file-tile");

const tile = (id, attrs, change) => (s) => { const file = s.files.find((f) => f.id === id); change?.(file); return el("jv-file-tile", { file }, attrs); };
registerGallery("file-tile", [
  { label: "PDF page (its picture)", build: tile("file-pps7", {}, (f) => { f.page = "Page 3 of 3"; f.thumb = { src: "/api/thumb/file-pps7-p3.webp", kind: "page", alt: "PPS 7, page 3: question 7, a beam with a point load and a uniform load" }; }) },
  { label: "PDF page (drawn from its text)", build: tile("file-pps7") },
  { label: "Folder (no preview)", build: tile("file-l21") },
  { label: "Compact (in a list)", build: tile("file-lab4", { compact: true }) },
], { about: "The file's own picture with its name over it, or its first lines on a light page, plus “Open it”." });
