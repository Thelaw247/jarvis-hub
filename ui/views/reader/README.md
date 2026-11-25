# Reader (N6)

A work thread's PDF inside the hub, on the light reading sheet (`.jv-paper`) in a HUD window. Route
`/read/<thread id>` (registered by `reader.js`). It opens straight away at the thread's resume point (page + y)
**behind** `<jv-resume-card>`; a fresh PDF (no resume point) opens at the top with no card; a weak spot (resume
without `y`) opens at the page and the card offers the page.

- **Answers:** Enter or "Carry on at Q7" → `resume_accept`, the card lifts and brackets lock onto the heading
  (250 ms), hold, fade. "From the top" / "Another question" jump there. Scrolling, the wheel, a key or Esc is
  the answer too: the card lifts silently and the spot follows him.
- **The voice:** when `state.focus` names this thread (its id, its file, or a window showing the file) and the
  spot is `confirmed`, the card lifts and the brackets lock onto the question, once per cue. "Open it" on a
  file with a PDF thread comes here (`core/main.js`).
- **Tracking:** PDF.js `pagechanging` / `updateviewarea` → page, y (PDF points from the top of the page), the
  question he's on (the first heading in the top 60% of the sheet, else the one running through the top edge),
  the questions in that part, and seconds per question (paused when hidden or after 10 idle minutes). What's
  under the card isn't in view, and a heading near the top owns the empty working space above it (the question
  running through the top edge counts only when no heading sits near the top).
- **His choice stands:** "Carry on at Q8", a pick under "Another question" or a yes by voice goes into the
  session as `chosen` (+ `since`, the questions after it). While he stays on it, the save is `confirmed` at that
  question; a saved question he never moved off is kept. Only moving on re-decides (`jarvis_hub/threads.py`).
- **The card** comes up once: answered (or Esc, or a scroll) it stays away for this open, and a reopen within
  5 minutes of leaving (or of the spot being saved) opens at the spot with no card. If the card held focus when
  it lifts, focus goes to the sheet (`#rd-scroll`). It only makes room above the heading when it really covers
  the top of the page (`covered()`).
- **Leaving** (route change, Close, page hide): `resume_save` with `{ label, page, y?, session }`. The label is a
  mirror of `jarvis_hub/threads.py`'s rules; the server re-decides from `session` once `threads.on_act` is wired.
  A glance (< 15 s, nothing moved) sends nothing.
- **Speed:** PDF.js loads in idle time after boot (not on the strip or phone), one worker, the last two
  documents stay open, and the question index comes pre-built from `/api/file/<id>.qindex.json`. Measured in
  `tests/e2e/test_reader.py`: cold ≈ 200–400 ms, warm ≈ 20–50 ms to Q7 (target ≤ 400 ms).
- The reader's canvas is the HUD's one canvas: never on the ambient screen or the strip.

Scenes: `reader-fresh`, `reader-resume`, `reader-weak`, `reader-accepted` (both themes; full, laptop, phone).
The demo PDF ("PPS 7") is drawn by `jarvis_hub/threads.py`, never one of his files.
