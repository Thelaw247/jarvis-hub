# jv-mini-chart (C10)

A small bar or line chart in token colours: one series, values labelled directly on top, a short label under every bar or point (12 px mono in Night: MON … FRI; `shortLabel()` turns "Monday" into "Mon"), an optional labelled target line, and the numbers behind it as a real table ("Show the numbers"). `.data`, `.target`, `heading`, `type`, `unit`, `tone`.

Drawn in HTML, so it fits the height it is given (a window on the Stage): the plot takes the room left over (48 px at least), the bars scale to it and each is at least 2 px tall; no bar is ever cut off. `chartModel(data, { type, target })` is the pure geometry.

Scene: `?scene=component:mini-chart` (add `&state=<name>` for one state, `&theme=evening` for Evening). Details are in the comment at the top of `mini-chart.js`.

On the Stage's glass board (HUD v3, `jv-window[opens]`) the caption and "Show the numbers" are small mono, like Huw's chart panels.
