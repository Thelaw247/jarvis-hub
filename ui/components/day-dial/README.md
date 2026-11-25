# jv-day-dial (N3)

The day dial around the orb (HUD v2 §6.1; review-glance-feasibility SHOULD 1). A 12-hour clock face from an
hour ago to 11 hours ahead, so it reads like a watch with no am/pm overlap.

| Mark | Look |
|---|---|
| Face | 12 ticks (longer at 12, 3, 6, 9), a faint ring |
| Now | a 2 px hand in `--text` |
| Upcoming | 4 px arc, `--line-dim` |
| Next (and under way) | 4 px arc, `--cyan`; only the next item is labelled, 12 px, in short words: "4:00 · GE 122 · ENGR 1A10" or "4:00 · GE 122 review" (course code + kind; the room only if it is a room code; up to two lines, never an ellipsis: `shortTitle()`, `roomCode()`) |
| Done | 4 px arc, `--cyan-hi` (Night adds a static bloom) |
| Moved / missed | dashed 4 px arc, `--text-3` |
| Due | 9 px diamond, `--warn` (`--cyan-hi` once done) |
| Overdue | triangle, `--crit`; one older than the face is pinned at its start so it never drops off |

```html
<jv-orb state="standby"><jv-day-dial slot="dial" live></jv-day-dial></jv-orb>
```
- `.items` = `state.day.dial[]` (ISO start/end, so it crosses midnight); `.now` = Date/ISO, or `live` for the hub clock.
- `private`: others may see the screen: shapes only, no label, no titles in the summary.
- **Static**: no animation or transition, ever. It redraws when its data changes and, with `live`, once at the
  start of each minute (never while the page is hidden). Drawn in pixels for its own size (ResizeObserver).
- In the orb it fills `.dialSlot` (2.5 R); arcs and marks stay inside the motes (2.75 R); the label hangs outside them.
- `role="img"` with a one-line `aria-label` (`.summary`), and `jv-day-dial-summary` fires when it changes. Inside
  `<jv-orb>` (itself `role="img"`) that name isn't read, so the ambient view repeats it in a `.jv-sr` line.
- `dialModel(items, now, { private })` and `clockAngle(t)` are exported (pure; the tests use them).

Scenes: `?scene=component:day-dial` (afternoon, crossing midnight, overdue, all done, moved/missed, empty,
others present) and `?scene=day-dial-orb&state=<afternoon|midnight|overdue|all-done|moved|empty>`.

## The ambient screen (`ui/views/now/ambient.js`, `ambient.css`)
The calm home screen (HUD v2 §4 standby, §6.4, §9.6): the standby orb with the dial, a big JetBrains Mono 300
clock with a small "PM" and the tiny tracked date, **one** line, the your-yes pill, page dots, Jarvis's caption
just above the Rail (the shell draws the Rail). The line: mornings (4 am–noon, no work touched yet today) lead
with today (first class + room, what's due today); within 3 h of touching a work thread, its picture + "PPS 7 ·
Q7 · Today"; otherwise nothing (the dial already labels what's next). Others present: nothing personal (no
line beyond "Something is ready for you when you're on your own.", no dial words, no count). Tier-2 branches
never show. Night has no plant; Daylight keeps a small one. Scenes: `now-ambient` (in now.js),
`now-ambient-morning`, `now-ambient-resume`, `now-ambient-others`, `now-ambient-midnight`, `now-ambient-caption`.
