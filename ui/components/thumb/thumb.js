// <jv-thumb>: a picture of a thing with its big label (HUD v2 §5: picture + label was ~30% faster than text;
// a picture alone wasn't).   .thumb = { src, kind, alt } (contracts common $defs.thumb)
//   label     the big label laid over the bottom of the picture ("PPS 7 · Q7")
//   fallback  course | person | room | monogram: what to draw when there is no picture (or it fails to load)
//   text      the fallback's words: a course code ("GE 122"), a person's name ("Sam Taylor"), a room ("ENGR 1A10")
//   ratio     wide (16:9) | page (4:3, the top of a page) | square; by default from the thumb's kind
//   size      small: a 48 px square, no label overlay (the label is said elsewhere, e.g. beside it)
// The box has a fixed aspect ratio, so nothing moves when the picture arrives; images load lazily and decode
// off the main thread. Rooms show as a big room code, which beats a photo; people as initials.
import { css, html, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const RATIO_OF = { page: "page", slide: "wide", video: "wide", design: "wide", course: "square", person: "square", monogram: "square", icon: "square" };

/** "Sam Taylor" → "ST", "high valyrian" → "HV", "Jarvis" → "JA". */
export function initials(name) {
  const words = String(name || "").trim().split(/[\s\-_.]+/).filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/** "GE 122" → ["GE", "122"], "CHEM 142" → ["CHEM", "142"], "ENGR 1A10" → ["ENGR", "1B71"], "Jarvis" → ["JA", ""]. */
export function monogram(code) {
  const m = String(code || "").trim().match(/^([A-Za-z]{2,5})\s*-?\s*(\d[0-9A-Za-z]*)$/);
  return m ? [m[1].toUpperCase(), m[2].toUpperCase()] : [initials(code), ""];
}

class Thumb extends Jv {
  static props = ["thumb"];
  static attrs = ["label", "fallback", "text", "ratio", "size"];

  update() { if (this.thumb !== this._for) { this._for = this.thumb; this._failed = false; } super.update(); }

  render() {
    const t = this.thumb, a = (n) => this.getAttribute(n);
    const label = a("label") || "", small = a("size") === "small";
    const fallback = a("fallback") || (t?.kind === "person" ? "person" : t?.kind === "course" || t?.kind === "monogram" ? "course" : "monogram");
    const ratio = a("ratio") || RATIO_OF[t?.kind] || (fallback === "room" ? "wide" : "square");
    const text = a("text") || label || t?.alt || "";
    const alt = t?.alt || (fallback === "person" ? text : label || text);
    const picture = t?.src && !this._failed;
    let body;
    if (picture) {
      body = html`<img class="jv-thumb__img" src="${t.src}" alt="${alt}" loading="lazy" decoding="async" width="320" height="${ratio === "wide" ? 180 : ratio === "page" ? 240 : 320}" draggable="false">`;
    } else if (fallback === "room") {
      const [building, room] = monogram(text);
      body = html`<span class="jv-thumb__mono jv-thumb__mono--room" role="img" aria-label="Room ${text}"><span class="jv-thumb__code">${building}</span>${room ? html`<span class="jv-thumb__num">${room}</span>` : ""}</span>`;
    } else if (fallback === "person") {
      body = html`<span class="jv-thumb__mono jv-thumb__mono--person" role="img" aria-label="${alt || text}"><span class="jv-thumb__initials">${initials(text)}</span></span>`;
    } else {
      const [letters, num] = monogram(text);
      body = html`<span class="jv-thumb__mono jv-thumb__mono--course" role="img" aria-label="${alt || text}"><span class="jv-thumb__code">${letters}</span>${num ? html`<span class="jv-thumb__num">${num}</span>` : ""}</span>`;
    }
    return html`<figure class="jv-thumb jv-thumb--${ratio}${small ? " jv-thumb--small" : ""}${picture ? "" : " jv-thumb--fallback"}" data-kind="${t?.kind || fallback}">
      ${body}${label && !small ? html`<figcaption class="jv-thumb__label">${label}</figcaption>` : ""}
    </figure>`;
  }

  rendered() {
    const img = this.$(".jv-thumb__img");
    if (img) img.addEventListener("error", () => { this._failed = true; this._render(); }, { once: true });
  }
}
Thumb.define("jv-thumb");

// ---- scenes: pictures (made-up demo thumbnails, never his files) and every fallback ---------------------
const thumb = (src, kind, alt) => ({ src: `/api/thumb/${src}.webp`, kind, alt });
const make = (props, attrs) => () => el("jv-thumb", props, attrs);
registerGallery("thumb", [
  { label: "Page (the question's page)", build: make({ thumb: thumb("file-pps7-p3", "page", "PPS 7, page 3: question 7, a beam with two supports") }, { label: "PPS 7 · Q7" }) },
  { label: "Slide deck", build: make({ thumb: thumb("slides-ge122-l21", "slide", "GE 122 lecture 21 title slide: Frames") }, { label: "GE 122 · L21" }) },
  { label: "Lecture video", build: make({ thumb: thumb("video-ge122-l21", "video", "GE 122 lecture 21 video, 12 minutes in") }, { label: "L21 video · 12:40" }) },
  { label: "Course picture", build: make({ thumb: thumb("course-chem-142", "course", "CHEM 142 course picture") }, { label: "CHEM 142" }) },
  { label: "Plotter design", build: make({ thumb: thumb("design-cedar", "design", "Plotter design: a cedar branch line drawing") }, { label: "Cedar branch" }) },
  { label: "Course monogram (no picture)", build: make({}, { fallback: "course", text: "GE 122", label: "Statics" }) },
  { label: "Person (initials)", build: make({}, { fallback: "person", text: "Sam Taylor", label: "Sam" }) },
  { label: "Room code", build: make({}, { fallback: "room", text: "ENGR 1A10", label: "Next class" }) },
  { label: "Picture that fails to load", build: make({ thumb: { src: "data:image/webp;base64,AAAA", kind: "page", alt: "PPS 6, page 1" } }, { fallback: "course", text: "GE 122", label: "PPS 6" }) },
  { label: "Small (beside a label)", build: () => {
    const box = el("div", { className: "jv-thumb-demo" });
    box.append(el("jv-thumb", { thumb: thumb("file-pps7-p3", "page", "PPS 7, page 3") }, { size: "small" }),
      el("jv-thumb", {}, { size: "small", fallback: "course", text: "MATH 133" }),
      el("jv-thumb", {}, { size: "small", fallback: "person", text: "Riley Morgan" }),
      el("jv-thumb", {}, { size: "small", fallback: "room", text: "ENGR 1A10" }));
    return box;
  } },
], { about: "A picture with a big label; course monograms, initials and room codes when there's no picture. Demo pictures are made up.", columns: "260px" });
