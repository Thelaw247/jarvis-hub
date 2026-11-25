# jv-rail (N4; HUD v3 §14 decision 2: Huw's icon row)

The Rail, drawn as Huw's icon row: six fixed slots at the bottom centre of every screen (the hub, the ambient
screen and the Stage) that track **things, not windows**: Your yes · Today · Homework · Messages · Jarvis · Parked.
Each slot is a tiny monochrome line icon (16 px in a 40 × 28 button; with the dots the row is 48 px, the shell's --rail-h) between thin dividers, with a small count
badge. When the slot's worst thing wants him, its glance shape leads the badge in the glance colour: amber hollow
square (your yes), amber diamond (soon), red triangle (critical). Shape + colour + the slot's label, never colour
alone. A short static cyan notch under the icon means "new since you looked" (never a badge count). After the
slots: a search glyph (the command bar, like Ctrl+K) and, on the calm home while windows are up, a Stage glyph with
the count. Under the row: `<jv-page-dots>` for the five views (`components/tabs`).

- **Data:** `.rail`, `.marks`, `.focus`, `.presence`, `.ambient`, `.now`, `.stage`. The shell's `<jv-rail id="rail">`
  reads the store and the router itself; a copy with the `static` attribute (galleries) is given them. The server
  builds the Rail (`jarvis_hub/rail.py`); this component only draws it (it recomputes count and worst only when
  tier-2 things are hidden). `.stage` is set by the Now view (`null` hides the glyph).
- **Open:** click, Enter or Space on a slot, or **Alt+1…6** from anywhere (Alt is left alone by `core/keys.js`).
  Cards fan out 40 ms apart above the row. A card with a docked window sends `recall` and fires `jv-rail-recall`
  `{ id, ref, rect }` on `document` so the Now view grows the window out of the slot; a card without one opens
  where the thing lives (Activity, Today, its branch). Esc closes and gives focus back. ← → Home End move along
  the row, slots then tools (one Tab stop); the dots come next.
- **Tools:** search fires `jv-act` `search` (the shell opens the command bar); Stage fires `jv-rail-stage`. Opening a slot fires `jv-rail-open` `{ slot }` (the home's return offer takes it as his answer). A PDF work thread with no docked window opens in the reader (`/read/<thread>`), at his spot.
- **Marks:** a slot's notch shows while any of its things is marked. `seen` is sent on keyboard focus of a card,
  an 800 ms hover on it (not on ambient), opening it, or "Mark all seen". Focus the Rail puts there on opening
  doesn't count. One polite screen-reader line a minute at most for new marks.
- **Focus cue:** `state.focus` naming a slot (`homework`, `rail:homework`) or a thing on it snaps cyan-hi corner
  brackets onto the icon (250 ms) until `until`.
- **Empty slots:** on the hub and the Stage all six always show, an empty one with no badge (its label still says
  "0 things"). **Ambient:** only filled slots, nothing moves; an empty slot and the tools keep their place unseen
  (`data-vacant`, `visibility: hidden`), so the row never re-centres. Tier-2 things hide when others are present
  and on ambient.
- **Phone:** a 44 px row above the tab bar, the six slots sharing the width; no tools or dots (the tab bar is the
  phone's way between views). `views/phone` shows the words instead of the icons when the row has room.

Gallery: `?scene=component:rail` (empty, filled, since you looked, Jarvis names Homework, critical, ambient, Stage
glyph, others present, Homework open, Jarvis open, glance codes). Page scenes live in `views/now/now.js`.
