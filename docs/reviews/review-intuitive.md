# HUD v2 review: intuitive or mechanical?

Lens: someone who was there, or a machine running rules? Checked against both research notes, PSYCHOLOGY M, VOICE, MEMORY §7–8, HUB_TRUST. 2026-11-14.

**Verdict:** §8–9's rules are right. The mechanical feel will leak from four uncovered places:
1. The cached phrase library and time-of-day greetings (VOICE §4, HUB_TRUST §5.7).
2. Things that happen *every* time: the wake beat, the debrief, the resume offer, the end-of-session recap.
3. There's no decline grammar (ignore / not now / no / stop).
4. "Prepare first" (§9.3) can visibly move his windows before he says yes.

## 1. Scenarios

**1. First sit-down, 8:40 am.** Wake beat plays, day dial shows two class arcs. Current docs give him a time-of-day greeting, and Now leads with "You were on: PPS 7 · Q7 → resume". *Feels:* by Thursday "Good morning" is a jingle, and opening on last night's unfinished work is a quiet guilt trip. *Fix:* mornings lead with today; the thread waits on the Rail. Speak only if something changed overnight ("CHEM's moved to Thorv 271."). Silence is a valid morning.

**2. Ten minutes before lecture.** He's on Q9 and hears one line: "GE 122 in ten, same room." Resume point saves silently (right). *Flag:* if it fires at exactly T−12 every day, he'll feel the timer. Fire at the nearest breakpoint inside a window. Show the slide preview instead of saying it.

**3. Back from class.** P1 demo: "Welcome back. GE 122 just ended; PPS 7 is next… Pull it up?", plus F2.9's "How was math?". *Feels:* robotic by day three. A debrief after every class is a survey, edging toward C14. *Fix:* lead with the one thing that changed, or say nothing. Debrief only after events with an outcome (quiz, lab, midterm).

**4. Practice set from two days ago.** Tap → opens at Q7 behind "1–6 done · looked at 5b's solution", nothing spoken. *Feels:* the best moment in the design. *Flags:* "looked at 5b's solution" on a big HUD reads as judgment and is visible to visitors; dwell time ("40 min on Q6") would feel like surveillance.

**5. New Canvas assignment.** Syncs while he's mid-PPS; §9.5 has no timing rule, so speaking now is presumptuous. *Fix:* put a "1 new" notch on the Homework slot. At the next coarse breakpoint, and only if it's due within 72 h: "Assignment 5's out, due Friday — about two hours, going by your last few. Want it up with Lecture 18 beside it?"

**6. Lab report draft.** "Open lab 4"; Word cold-starts (2–4 s, est.). *Risk:* a spoken "Done" before Word is visible. *Fix:* show the card with the Results heading at once, then stay quiet until Word lands on the heading.

**7. Approval: booking a study block.** "Thursday 7 to 9 for PPS 8? It's clear." An amber ring empties over 10 s, and with reduced motion he sees a countdown number. *Feels:* like a quiz timer. Nothing says what happens at zero, and a cached "Booked." confirms the obvious. *Fix:* see M5. The yes is confirmed by the arc drawing onto the day dial.

**8. Rushed.** Four minutes left, "quick, what's due?" → two items in one breath, no offer, no aside. §8 says "read the moment" but defines no signal for it (S1).

**9. Friend interrupts.** Jarvis asks "Thursday at 7?". Roommate walks in and says "yeah sure" to him. *Real risk:* the open answer window takes "yeah" and books it. Private widgets also stay up. F1.6 (others present) is P3, so v0.3 needs a fallback (M5). On "sorry, what?", a shorter version, not a replay.

**10. Long evening.** "Settled in → fuller recap" (§8) risks a monologue; cap at two sentences. The break line, "That's three hours straight…", is fine once per evening at a breakpoint. It's mechanical if it fires at 3:00:00. The session end (M16) becomes a sign-off jingle if it's always spoken.

**11. Ignores an offer.** "Seven, where you were?" He just scrolls to Q3. His scroll *is* the answer: the card lifts with no comment. *Gap:* "ignored" is logged but has no behaviour.

**12. "Not now."** Nothing, or an earcon; never "I'll remind you later" without a real time. *Gap:* nothing says how long "not now" lasts.

**13. Game mode.** PTT only, strip hidden, resume point saved: right. When the game closes, Jarvis must not pounce with "Back to PPS 7?". That's a verdict on gaming (C14/C40); resume cue stays visual.

**14. Jarvis's mistake.** Opened the solutions; he says "no, the questions". Swap, no words. Bigger slips: the §8 line, once, at a breakpoint, never again. If he corrects a document's resume point twice, offers for that document drop to page level (Horvitz).

## 2. After a week: what he'd predict word for word

| Jingle | Source | Fix |
|---|---|---|
| "One moment." on every tool call | VOICE §3 | pool + silence (the orb's Thinking state *is* the ack); skip if done in < ~700 ms |
| "On it / Done / Booked / Sent / Pulling it up" | F2.11, BUILD_PLAN P1 | visual receipt; pools where speech is needed |
| "Good morning" / "Welcome back" | HUB_TRUST §5.7, P1 demo | drop standalone greetings |
| "How was math?" after every class | F2.9 | outcome events only |
| A spoken offer on every reopen | §9 | mostly card-only (M2) |
| The offer's *shape* "{N}, {where}?" | §8 template slots | vary structure: statement, question, one word, silence |
| 1.2 s wake beat on every "hey Jarvis" | §3 | first wake of the day only (M6) |
| Break nudge at exactly 3 h | §8 sample | breakpoint inside a 2.5–3.5 h window |
| "Understood. Carrying on." | §8 sample | pool |
| End-of-session recap | M16 | visual by default |

**How to vary without becoming unpredictable.** There are three layers:
1. **Never varies:** what Jarvis *does*, where things appear, the shape/colour/word codes, the answer grammar, the layout, and safety lines. "Leave now for the exam" should be the same words every time, and that's a feature. *Vary the words, never the screen.*
2. **Varies by context** (deterministic, so "Why?" can explain it): whether Jarvis speaks at all (silence, card, one word or a sentence), how long it talks, and what the line leads with. Lead with what changed first, then time away, then his own last words. A line that leads with what's actually new rarely repeats.
3. **Varies by rotation** (surface only): a pool per line type, with no repeat within the last 5 uses of that type, and no greeting or acknowledgement repeated within the same day. Rotation never decides *whether* Jarvis speaks.

## 3. Declines (missing from §8–9)

- **He answers by acting** (scrolls, opens something else): a redirect; resume point follows him, silently.
- **Ignored** (the window ends with no word): card shrinks to its Rail slot, not spoken again this session. Two ignores in a row for the same offer type and context make that offer card-only until he next accepts one by voice.
- **"Not now"**: earcon at most. Stays on the Rail, unspoken until context changes (he leaves and returns, new day, or state changes: due tomorrow → said once, with that reason).
- **"No" / "from the top"**: do what he said.
- **"Stop offering that"**: off for that type; one receipt with undo in the "Jarvis learned" feed.
- **Decay:** raised thresholds drift back over ~2 weeks of acceptances (MEMORY §8 only has the raise).
- **Never** refer to a past decline ("you said not now earlier"), and never show declines as misses.

## 4. Ranked changes

### MUST
- **M1 · §8 + VOICE §4. Phrase pools.** "Every cached line type has 5–8 variants rendered once, plus *silent* as a variant. The picker excludes the last 5 used for that type. No standalone greetings." *Latency:* none; still < 30 ms from disk. One-time ElevenLabs credits.
- **M2 · §8, new "When it speaks" rule.** "Speak an offer only when (a) he asked by voice, (b) he's been away ≥ 1 day from that thread, or (c) something about it changed. Otherwise show a card. A tap never triggers speech." *Latency:* less speech, so it's faster.
- **M3 · §9.3.** "Preparation is invisible until yes. Whatever he asked for may open behind the card. His Laptop A windows never move, and nothing he didn't ask for opens, until he accepts." *Latency:* none. Pre-load off-screen; restoring on yes takes ~50–200 ms (SetWindowPlacement).
- **M4 · new §8a Declines.** As in section 3. *Latency:* none.
- **M5 · §3 "Waiting for your yes".**
  - "The ring means 'listening for your answer', not a deadline. Reduced motion shows *Listening*, never a countdown number."
  - "When the window ends, the card moves silently to *Your yes* on the Rail. It's asked aloud again only if its state changes."
  - "Any speech outside the answer grammar closes the window. After that, ask-tier yeses need push-to-talk or a fresh wake."
  - *Latency:* none. This stops a friend's "yeah" from approving.
- **M6 · §3 Wake.** "The full wake beat plays only on the first wake of the day or after ≥ 4 h away. Every other wake shows Listening within 100 ms." *Latency:* perceived feedback drops from 1.2 s to ≤ 100 ms and meets the repo rule.
- **M7 · §5.4 + §8.** "Never remark on his sleep, gaming, time away or time per question. Dwell data only picks resume points. 'Solutions viewed' appears only under *Why?* or in review, never on the ambient screen or when others are present." *Latency:* none.

### SHOULD
- **S1 · MEMORY §7.1, now card. Add `moment`.** One of: rushed (≤ 15 min to a fixed event, or he said "quick"), between (≤ 10 min since arrival), settled (≥ 60 min free and a session started), heads-down, others present, game. Max spoken sentences for non-critical items: 0–1 / 1 / 2 / 0 / 0 / 0. *Latency:* < 1 ms, templated.
- **S2 · §8. Pre-phrase in T2.** When the now card rebuilds, Haiku writes 2–3 candidate lines per *Ready to offer* item, with recent lines in its prompt. Arrival pre-renders the top line's audio. §8 templates become the fallback. *Latency:* 150–250 ms TTFB becomes < 30 ms playback. Background Haiku cost only.
- **S3 · §5.4.** Resume cue leads Now after short breaks; mornings lead with today. Replace "→ resume" (system-speak) with a thumbnail plus "PPS 7 · Q7 · Tue".
- **S4 · F2.9.** Debrief only after outcome events, at most once a day, never when rushed.
- **S5 · triggers.** Leave-now and break lines fire at the nearest breakpoint in a window; critical "leave now" still fires at the hard time, fixed wording.
- **S6 · §9.5.** Canvas items: Rail notch at once; spoken only at a coarse breakpoint if due ≤ 72 h, with an estimate from his past, never "you're behind".
- **S7 · game mode.** After a game, no proactive speech except critical items.
- **S8 · mistakes.** As scenario 14.
- **S9 · M16.** Session ends visual by default; speak only when a whole item finished or tomorrow changed.

### NICE
- **N1.** Humour budget of about 2 asides a day, never the same target in a week. Drop lines that comment on his hours ("Bold choice, studying thermo at midnight").
- **N2.** Docking (700 ms) and wake (1.2 s) break §6's ≤ 300 ms. Either name them as exceptions or shorten them. Skip the dock slide if content arrives within 60 s of the last one.
- **N3.** 2–3 soft earcons as the non-verbal "got it".
- **N4.** Under the hood: a "repeat rate", the share of spoken lines identical to one used in the last 7 days. Target < 10%, safety lines excluded.

## 5. Doc fixes spotted
- §8 cites "JARVIS_PSYCHOLOGY.md Part N". Neither copy has it; both end at Part M.
- §8 says "Flash ~75 ms to first audio". VOICE §5 budgets 150–250 ms warm TTFB.
- RUNTIME §9 makes planner blocks *auto*, but HUB_TRUST §2 says every write asks. Scenario 7 depends on which one wins.
- The §4 glance table uses `--hud`, which the §2 palette doesn't define (`--cyan`?).
