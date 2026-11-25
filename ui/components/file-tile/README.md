# jv-file-tile (C19, Night pass N5a)

A file as a **picture with its big label**, plus its kind (icon + words), name, path and "Open it". `.file`, `compact`.

- With `file.thumb` (the page rendered at filing time, a deck's own thumbnail): `jv-thumb` with the name and page
  laid over it.
- Without one: the first preview lines on the light reading sheet (`.jv-paper`), drawn from text the hub already
  has, so it shows with the event (≤ 100 ms). A folder shows its icon on a dark sheet.
- "Open it" emits `jv-act` `open` with the file id.

Scene: `?scene=component:file-tile` (add `&state=<name>` for one state, `&theme=day` for Daylight).

In a glass `media` window on the Stage (HUD v3) the picture fills the panel edge to edge and the name, kind and path step back (the kicker and the picture's label say them); "Open it" stays a real button but the panel itself is what he clicks (`jv-window[opens]`).
