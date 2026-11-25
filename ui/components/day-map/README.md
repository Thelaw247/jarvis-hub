# jv-day-map (R2): the map window

The hero of the `map` window (REACH §5.2): today's places on the USask campus with the route between them, close to
Huw's map look. Dark land, faint roads, an ice route, the pin it leads with brighter and the only one labelled, and
one supporting line under it ("Next: CHEM 142 lab 4 · Thorvaldson 173 · 1:30 pm"). No buttons, no motion.

- **Data:** `window.data` of a `map` window (`contracts/map.schema.json`): `places` (lat/long), `stops` (the day's
  items with a place, in time order), `start` (where the route starts: his residence) and optional `focus` (what he
  asked about). Built by `jarvis_hub/demo/places.py` from the day and `jarvis_hub/demo/places.json`.
- **Leads with** `focus`, else the next stop by the clock. The line's first word says how it stands: Next, Now,
  Earlier, Later; when the day's stops are done it says so.
- **Schematic first:** every draw starts from bundled shapes (`campus.js`: the four buildings, the Bowl, two roads,
  all approximate) labelled "Schematic · approximate". Never presented as an accurate map. First draw ≈ 1–2 ms.
- **Tiles:** CARTO's basemap without labels (`dark_nolabels` at night, `light_nolabels` by day), credited
  "© OpenStreetMap contributors © CARTO" in the map's corner while shown. Asked for only against the live hub,
  online and not under automation (tests and screenshots always see the schematic); `tiles="on|off"` or
  `?tiles=on|off` forces it. Shown all at once when every tile has loaded; a failed tile keeps the schematic and stops
  asking for 5 minutes. One zoom level, ≤ ~24 tiles a draw, the same URL for the same tile (the browser's cache
  answers), no panning or prefetching. CARTO's free basemaps are for non-commercial use within their fair-use
  limits, which a personal hub stays far inside. Pulled into the HUD palette by a static colour blend.
- **Window kind:** registers `map` with `core/window-kinds.js` (content, kicker `MAP // TODAY` with `3 / 4`, role
  media, width 600, size 2x2). A pure view: closing it just closes.

Scenes: `?scene=component:day-map` (five states), `?scene=stage-map`, `?scene=stage-map-asked` (add `&theme=day`).
Live demo: type or say "show me where my lab is" (also "where's my next class", "show me the map").
