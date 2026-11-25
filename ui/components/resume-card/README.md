# jv-resume-card (N6)

"Here's where you stopped" over a reopened work thread: the page thumbnail, a kicker with the in-progress glance
shape ("PPS 7 · Q7 · Tue"), one short line ("1–6 done.") and the answers: **Carry on at Q7**, **From the top**,
**Another question**, **Why?**. A weak spot offers the page instead ("You stopped on page 3."). It never offers
two answers that mean the same: at the start of the document (page 1, or the first question) there is no
**From the top**. Props: `.thread`, `.questions`, `.now`,
`.changed` (a mark's `what`), `.private` (others present or ambient: "solutions viewed" never shows).
Emits `jv-resume` `{ choice: accept | top | pick | ignore, label?, page?, y? }` and lifts itself.

It never speaks. Its words follow the character rules (HUD v2 §9.2, §9.4): the line leads with what changed,
then (after a day away) a short review of what's done; the wording rotates through a pool and never repeats one
of the last five lines it showed. No system-speak, no remarks on time away.

Scene: `?scene=component:resume-card` (add `&state=<name>` for one state, `&theme=day` for Daylight).
