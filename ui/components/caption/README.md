# jv-caption (C16; HUD v3 §14 decision 7)

Jarvis's spoken line above the icon row, **only while he says it**: it shows while the orb is speaking and goes
the moment he stops (the hub keeps the last 10 under the Jarvis icon, `rail.slots.jarvis.said`). His own words
("You") show while Jarvis hears and thinks about them. A line that comes while the orb isn't speaking (quiet
hours: shown, not said) stays for its `ttl_ms`; nothing ever stays past it. Night: no box, a cyan "JARVIS" tick and
the line with its source chip; Daylight keeps the slim strip. `.caption`; the shell's copy follows the store's orb
itself; `sticky` keeps a gallery copy up. Screen readers get the line from `core/a11y.js` (aria-hidden here).
`captionLive()` is the rule, exported for tests.

Scene: `?scene=component:caption` (add `&state=<name>` for one state, `&theme=day` for Daylight).
