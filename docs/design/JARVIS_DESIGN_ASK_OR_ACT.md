# Jarvis design: ask or act

Written 2026-11-16 from De Wet's problem statement. **The problem:** Jarvis must not ask what it already knows
(that feels like a machine and wastes his time), and must not act on what it doesn't know (booking "golden week"
wrong, deleting his events, moving a block past its deadline). The fix has to keep the intuition: he should feel
understood, not interviewed.

His scenario is a test, not a script: *"Put golden week in my calendar."* Jarvis doesn't know what golden week is.
It asks one natural question; he says it's a fitness plan with Charlie; Jarvis asks if they've planned it out; yes;
Jarvis asks for the sessions; it books them, deletes nothing, and never moves anything past a deadline.

## 1. The idea: Jarvis fills a plan, and only asks for the holes that matter

Every write Jarvis can propose has a **plan shape**: a short list of slots it must fill before it can act. For a
calendar booking: *what it is · when (dates, times) · how often · who · where · how firm · what it must not clash
with or pass (deadlines)*. A deletion or move adds *which exact events* and *why*.

Before proposing, Jarvis fills every slot **from what it already knows** (the now card, memory, the Life Tree,
the calendar, homework.json), and each slot gets the confidence memory already uses:

| Slot is… | What Jarvis does |
|---|---|
| **Sure** (his word, or the calendar itself) | uses it, never asks |
| **Likely** (his habits, an earlier similar event) | uses it and **says the assumption inside the read-back**, so one "yes" covers it and he corrects only if wrong: *"…at 7 am like your gym slots"* |
| **Unknown or a guess, and it matters** | asks, see §2 |
| **Unknown and it doesn't matter** | picks the sensible default and says nothing |

This is plain code over memory (a readiness check, `ready(plan)`), run before the model writes a reply. It
costs no extra model call: ~5 ms, using reads the turn already made.

## 2. When a hole is worth a question

A question has a cost (his attention, the feeling of being interviewed). Acting wrong has a cost too (a wrong
booking, a lost event). Jarvis asks only when the second is bigger:

**ask if (how likely it's wrong) × (how bad if wrong) > (cost of asking)**

- **How bad if wrong** comes from the action, in code: adding a private block is cheap to undo; anything that
  touches *his own* events, other people, or a deadline is expensive; deleting is the most expensive.
- **Cost of asking** goes up with each question already asked in this task and when he's busy (focus, class,
  game mode), so Jarvis asks fewer questions at bad times and waits for a breakpoint (code of conduct rule 3).

When it does ask:
- **One question at a time, the one that fills the most slots.** "What is golden week?" fills *what*, often
  *who*, *how often* and *how firm*; "what time on Tuesday?" fills one.
- **Casual and closed, with its best guess offered.** Not "Please specify the event type." Instead:
  *"Golden week, is that the fitness thing with Charlie?"* or, if it has no guess, *"What's golden week?"*
- **At most three questions per task.** After that, Jarvis drafts with its assumptions visible and asks for one
  yes on the whole draft. **Draft before interrogating:** once it has the gist, it proposes the whole booking
  and lets him correct it, rather than asking about each field.
- **Never the same question twice.** Every answer is saved to memory (as his word: Sure), so next time "golden week"
  is known: what it is, that it's with Charlie, which sessions.

## 3. Lines code holds, whatever the model thinks

These are rules in the executor, not prompts, so no wording can get around them (C12, C41).

1. **Nothing of his is deleted without a named yes.** Events he made (or anyone else made) are never deleted by
   Jarvis or by a skill. A proposed deletion lists each event by name and time, and only his yes to that exact
   list runs it. Jarvis may tidy only events *it* created (calendar-sync already tells them apart), and even that
   waits for his yes. Deleted events go to the undo bin (24 h).
2. **No move past a deadline.** Before any move, code checks every block that serves a deadline (homework,
   study-plan sessions, lab preps) against `homework.json` and the syllabi. If a move would land at or after the
   due time, it isn't proposed. Jarvis says so and offers the nearest slot before it: *"Wednesday is after PPS 7's
   8 pm deadline. Tuesday at 4 instead?"* Moving his own events is shown first ("moves 1 block you made") and needs
   its own yes.
3. **No clash without saying so.** A booking that overlaps class, a lab, an exam or an event he made is named in
   the read-back.
4. **Unknown things aren't invented.** If a slot that matters is still unknown after the question budget, Jarvis
   drafts with a clear blank ("I don't have Thursday's time yet") instead of guessing.

## 4. His scenario, through this design

1. *"Put golden week in my calendar."* Memory has no "golden week". The plan's *what* is unknown and it decides
   everything else, so it's worth one question: *"Golden week, what's that?"*
2. *"It's like a fitness plan, with Charlie."* Saved: golden week = a fitness plan, with Charlie (his word). Now
   *how firm* and *the sessions* are unknown, and they matter, because booking made-up sessions is wrong.
   One question fills both: *"Have you two already planned the sessions, or should I sketch a week?"*
3. *"Yes, we have."* → *"Great, what are they?"* He lists them. Jarvis already knows his classes, so it says
   nothing about times that fit and names only the one that clashes: *"Thursday at 10 clashes with Lecture 22.
   Book it anyway or move it?"*
4. Read-back and one yes: *"Golden week with Charlie: 6 sessions, Monday to Saturday. Nothing deleted, nothing of
   yours moved. Book it?"* The read-back is generated by code from the actual plan.
5. Next time: *"Book golden week again"* needs no questions. It's Sure.

## 5. His skills run on their own, inside these lines

The USask skills (week-planner, homework-finder, calendar-sync, study-plan, laundry-timing…) run as background jobs
by themselves (RUNTIME §4). Their reads are free; their writes come out as one proposed plan per run, checked by
§3's rules (no deletes of his events, nothing past a deadline, clashes named), and wait for his yes like
everything else. When a skill hits a real unknown (its `AskUserQuestion`), Jarvis asks it at the next breakpoint
using §2's rules: one casual question, its best guess offered.

## 6. How we'll know it works

- **Ask rate:** questions per task, aiming for ≤ 1 on familiar tasks and ≤ 3 on new ones; zero questions whose
  answer was already Sure in memory (logged and reviewed).
- **Wrong-act rate:** proposals he rejects or corrects because of a wrong assumption.
- **Hard-line tests:** a test for every §3 rule (deleting his event without a named yes fails; a move past a
  deadline is never proposed), plus his golden-week scenario as an end-to-end test.
- Latency effect: none on normal turns. The readiness check is code over data the turn already has (~5 ms); a
  question replaces a turn, it doesn't add one.
