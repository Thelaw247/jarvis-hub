// Static scenes: ?scene=<name>&theme=day|evening&size=full|laptop|strip|phone|ambient[&state=<s>]
// load the contract fixture, change it for the state being shown, and draw it with no server events,
// so every state of every view and component can be opened, checked and screenshotted.
import { html, slug } from "./dom.js";

const scenes = new Map();

export const params = new URLSearchParams(location.search);
export const sceneName = params.get("scene");

export const scenes_ = scenes;
/** Register a scene. def: { path?, size?, patch?(state), render?(stage, state), about? } */
export function registerScene(name, def) { scenes.set(name, def); }

/** Register a component gallery: `component:<name>` shows every state side by side; &state=<slug> shows one.
 *  items: [{ label, build(state) → Element | string, wide? }] */
export function registerGallery(name, items, { about = "", columns } = {}) {
  registerScene(`component:${name}`, {
    about, gallery: items.map((i) => slug(i.label)),
    render(stage, state) {
      const only = params.get("state");
      const wrap = document.createElement("div");
      wrap.className = "jv-gallery jv-grid";
      if (columns) wrap.style.setProperty("--gallery-min", columns);
      wrap.innerHTML = String(html`<h1 class="jv-gallery__title">${name}</h1>${about ? html`<p class="jv-muted jv-gallery__about">${about}</p>` : ""}`);
      const grid = document.createElement("div");
      grid.className = "jv-gallery__grid";
      for (const item of items) {
        if (only && slug(item.label) !== only) continue;
        const cell = document.createElement("section");
        cell.className = "jv-gallery__cell" + (item.wide ? " jv-gallery__cell--wide" : "");
        cell.dataset.state = slug(item.label);
        const label = document.createElement("h2");
        label.className = "jv-label";
        label.textContent = item.label;
        const body = document.createElement("div");
        body.className = "jv-gallery__body";
        const built = item.build(structuredClone(state));
        if (typeof built === "string" || built?.s !== undefined) body.innerHTML = String(built); else body.append(built);
        cell.append(label, body);
        grid.append(cell);
      }
      wrap.append(grid);
      stage.replaceChildren(wrap);
    },
  });
}

/** Make an element with properties (for galleries and views). */
export function el(tag, props = {}, attrs = {}) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
  Object.assign(node, props);
  return node;
}

export const getScene = (name) => scenes.get(name);
export const sceneNames = () => [...scenes.keys()].sort();
