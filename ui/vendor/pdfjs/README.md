# ui/vendor/pdfjs

PDF.js **6.5.438** (`pdfjs-dist`, © Mozilla Foundation, Apache-2.0, `LICENSE`), vendored so the hub's reader
works fully offline. Nothing here is edited by hand; `tools/hexlint.py` skips this folder.

| Path | What |
|---|---|
| `pdf.min.mjs`, `pdf.worker.min.mjs` | the library and its worker (from `build/`; flattened, because `build/` is git-ignored) |
| `web/pdf_viewer.mjs`, `web/pdf_viewer.css`, `web/images/` | the viewer component (PDFViewer, EventBus, PDFLinkService) |
| `cmaps/`, `standard_fonts/`, `wasm/`, `iccs/` | given to `getDocument` as `cMapUrl`, `standardFontDataUrl`, `wasmUrl`, `iccUrl` (each folder keeps its own licence files) |

Left out: source maps, the legacy build, the sandbox (no PDF scripting), the off-thread renderer and the types.

Update with:
```
npm pack pdfjs-dist@<version> && tar -xzf pdfjs-dist-<version>.tgz
cp package/build/pdf.min.mjs package/build/pdf.worker.min.mjs ui/vendor/pdfjs/
cp -r package/web/pdf_viewer.mjs package/web/pdf_viewer.css package/web/images ui/vendor/pdfjs/web/
cp -r package/cmaps package/standard_fonts package/wasm package/iccs package/LICENSE ui/vendor/pdfjs/
```
