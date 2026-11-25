# ui/core

The shell's plumbing. Components and views use these and nothing else to reach data.

| File | Job |
|---|---|
| `dom.js` | `html` templates (escaped by default; `true`/`false` in an `aria-*` attribute render as words), the `Jv` base element, `icon()`, radio groups (`rove` roving tabindex, `radioKey` arrows), time words (`countdown`, `clockTime`) |
| `store.js` | The UI state (contract shapes) and `apply(event)`; `watch(keys, fn)` to redraw on change; `now()` hub clock |
| `bridge.js` | `loadState()` and `act(action, target, args)`: hub server in live/demo mode, local answers in scene mode |
| `events.js` | The SSE stream; shows "offline" calmly and reloads state on reconnect |
| `router.js` | Five tabs, hash paths (`#/life/ge-122`), back stack with scroll positions, `refresh()` after a resize |
| `scenes.js` | `?scene=` registry: `registerScene`, `registerGallery` (component state galleries) |
| `main.js` | Boot, the live size (`data-size`: phone < 720 px, laptop ≤ 1280 px, full; `?size=` or a scene's size stays fixed; on the phone the tabs move after the view in the DOM), and keeping the shell regions in step with the store |
| `windows-core.js` | The six-window rule shared by the store and the window manager |
| `windows.js` | Window manager (W01): grid layout, 60 s lifetime, privacy on shared screens, voice/keyboard commands, saved layouts |
| `keys.js` | Keyboard and focus (B01): Ctrl+K, /, 1–5, Esc, ?, L, M, radio-group arrows and the shortcuts sheet |
| `theme.js` | Theme and motion (B02): Daylight / Evening / Windows / sunset, reduced motion (`data-still`), plants on/off |
| `presence.js` | Idle ↔ ambient (B03): 2 idle minutes → ambient screen, wake on key/click/push; runs the window clock; rests when he leaves (`presence.changed { here: false }`) |
| `orbview.js` | What the orb shows, from the store: `standby` when nobody is here, an alert while something on the Rail is critical, and which wake beat to play (`last_wake`). `showOrb(el)` puts it on a `<jv-orb>` |
| `a11y.js` | Screen-reader live regions (B05) for captions, notices, approvals and offline |
| `placeholder.js` | The live event log (`#/debug`) and the fallback for a missing view |

Components emit `jv-act` (`{action, target, args}`) and `jv-nav` (`{path}`); `main.js` forwards them to the
bridge and the router. Put `data-act`/`data-target` or `data-nav` on a button inside a `Jv` element and the
base class emits the event for you.
