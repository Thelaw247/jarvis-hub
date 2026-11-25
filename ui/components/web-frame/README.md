# jv-web-frame, jv-web-full (R1, hub v0.5.0: REACH §5.1)

A **web window**: a live web page inside the glass frame on the Stage, or a **tabs window** that groups up to six
pages with a small tab row (Huw's). Both are the window type `web`; `window.data` follows
`contracts/web.schema.json`: `{ pages: [{ id, url, title, site?, frame? }], active? }`. One page is a web window;
two or more get the tab row.

- **The page** is an `<iframe>`, 16:10 in its window, edge to edge under the kicker (the board's `media` role).
  It sits under the same static dark tint as a page picture (`--media-tint`, v0.4.1) so a white page is never
  the brightest thing on screen (HUD v2 §14.2). It fades in once loaded (opacity, 200 ms; none when nothing may move).
- **Sandbox:** `allow-scripts allow-same-origin allow-forms`, nothing else: no top navigation (a page can't take
  the hub away), no pop-ups, no permissions (`allow=""`), `referrerpolicy="no-referrer"`. A page from the hub's
  own address (the demo pages) loses `allow-same-origin`, so it gets an opaque origin and can't reach the hub,
  its store or its bridge. Only `http:` and `https:` addresses are ever shown (`web-policy.js safeUrl`): no
  `javascript:`, `data:`, `file:`, `blob:`, `about:`, and no user name or password in the address.
- **The card** (§14.2 anatomy) replaces a page that can't be framed: the window's kicker `WEB // site`, the
  page's title as the one hero (condensed caps, ≤ 2 lines), its address as the one supporting line. It shows
  when the page says `frame: "no"`, when its site is on the "refuses framing" hint list in a plain browser
  (`REFUSES_FRAMING`: Google, GitHub, Canvas…; their `/embed/` pages excepted), on a load error, or when it
  hasn't loaded after 12 s. Activating it opens the page in his **default browser** (`openInBrowser`: in the
  desktop app a new window from the hub goes to the default browser; in a browser, a new tab with no opener).
- **Activating the panel** (on the Stage the whole panel is its "Open it": window.css hides the opener button
  but keeps it for the keyboard and screen readers) opens the page **full size on the Stage**: `<jv-web-full>`,
  a dialog with the kicker, the page's place (`02 / 03`), the tabs, **Open in browser** and **Close**. Esc or
  the scrim closes it and focus goes back to the window; Tab stays inside; the hub's shortcuts don't fire while
  it is open. One at a time.
- **Tabs:** a real tablist (`role=tab`, one Tab stop, ← → Home End move, selection follows focus). A page's frame
  is made the first time its tab is shown and then kept, so switching back is instant. The window's kicker
  follows the tab (`WEB // site`, `02 / 03`), and a redraw keeps the tab he chose.
- **Pin and close** are the window's own (jv-window): shown only on hover or keyboard focus.
- **On the desktop** (`jarvis_hub/webframes.py`): WebView2 lets the hub's own pages frame sites that send
  `X-Frame-Options` / CSP `frame-ancestors` (`AdditionalAllowedFrameAncestors`, set to the hub's origin only, for
  first-level frames of the hub's pages only). The page knows it is there by `window.chrome.webview` and then
  tries the live frame for every site; `?web=browser` forces the plain-browser rules in a scene.
- **Signed-in pages** use the desktop app's own browser profile, `%LOCALAPPDATA%\JarvisHub\webprofile`
  (`webframes.start_options`): he signs in once inside a web window and stays signed in, separate from his
  everyday Chrome or Edge. Nothing about his accounts is in the code; deleting the folder signs him out of all.

## The window kind
`web-frame.js` registers the kind with `core/window-kinds.js`: content = `<jv-web-frame>`, kicker =
`webKicker`, role `media`, width 600 (L tier), default size `2x2`. The board and the content switch only use it
once the hook below is in (the overseer's; it touches `ui/core/windows.js` and `ui/views/now/widgets.js`).

### Hook for the overseer (after v0.4.1 lands)
- `ui/components/index.js`: `import "./web-frame/web-frame.js";  // R1: web windows`
- `ui/views/now/widgets.js`: import `windowKind` from `../../core/window-kinds.js`; first line of
  `windowContent`: `const kind = windowKind(win.type); if (kind) return kind.content(win, s, now);`; in
  `windowKicker`, after `out` is made: `const kind = windowKind(win.type); if (kind) return { ...out, ...kind.kicker?.(win, s, thread) };`
- `ui/core/windows.js`: import `windowKind` from `./window-kinds.js`; fall back to it in `sizeOf`
  (`… || windowKind(w.type)?.size || "1x1"`), `roleOf` (`… || windowKind(win.type)?.role || "text"`) and
  `panelWidth` (`PANEL_WIDTH[win.type] || windowKind(win.type)?.width || 340`).
- `contracts/window.schema.json`: add `"web"` to `type`'s enum (its `data` is `web.schema.json`). It docks under
  **Jarvis** (the default slot) as a notice until a Rail kind for it exists.

## Scenes
`?scene=component:web-frame` (a live page, a tabs window, the card, pin and close as on hover, the opener off the
board), and, once the hook is in, `stage-web` (a search page, a tabs window, a countdown), `stage-web-card`
(add `&web=browser`: the card beside a live page) and `stage-web-full` (opened full size). The demo pages are
served by the hub at `/demo/web/search.html` and `/demo/web/article.html` (no internet needed).
