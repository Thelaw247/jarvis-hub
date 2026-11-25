# ui/vendor

Third-party code, vendored so the hub has no build step and never loads anything from the network.

| File | What | Licence |
|---|---|---|
| `d3-lifemap.js` | One ES module with only what the Life Map uses: `hierarchy`, `cluster`, `tree` (d3-hierarchy 3), `zoom`, `zoomIdentity` (d3-zoom 3) and `select` (d3-selection 3), plus the d3 modules those need (transition, interpolate, drag, dispatch, ease, timer, color). | ISC, © Mike Bostock (`LICENSE-d3.txt`; every bundled d3 module uses the same licence) |
| `pdfjs/` | PDF.js 6.5.438 (`pdf.min.mjs`, `pdf.worker.min.mjs`, `web/pdf_viewer.{mjs,css}`, cmaps, standard fonts, wasm, ICC profiles): the hub's reader (`views/reader`), fully offline. About 6.4 MB. | Apache-2.0, © Mozilla (`pdfjs/LICENSE`) |

`d3-lifemap.js` is rebuilt with:
```
npm install d3-hierarchy d3-zoom d3-selection esbuild
# entry.js:
#   export { hierarchy, cluster, tree } from "d3-hierarchy";
#   export { zoom, zoomIdentity } from "d3-zoom";
#   export { select } from "d3-selection";
npx esbuild entry.js --bundle --format=esm --minify --outfile=ui/vendor/d3-lifemap.js
```
Nothing here is edited by hand, and `tools/hexlint.py` skips this folder.
