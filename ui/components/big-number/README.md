# jv-big-number (C09, Night pass N5a)

The one big thing a window leads with: a hero number in the condensed face (Barlow Condensed, tabular figures,
~3× the title). A due countdown (`.due`, `.now`) such as "2 d 4 h" with progress and source, or a stat (`label`,
`value`, `unit`, `sub`). Screen readers hear the countdown in full ("2 days 4 hours left").

- Within 72 hours the label is the **soon** glance code (diamond in brackets + "Due soon") and the number turns
  warn; past due it is the **critical** code ("Now") with a quiet "Past due" (no blame). Never colour alone.
- Progress is a segmented bar of real progress (~30 blocks, one element) plus the progress glance "50% done".
- The caption above a plain number is sentence case, not small caps.

Scene: `?scene=component:big-number` (add `&state=<name>` for one state, `&theme=day` for Daylight).

On the Stage's glass board (HUD v3, `jv-window[opens]`) the words around the number are 13/19; the number stays big.
