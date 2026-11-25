# Review: HUD v2 through a film-fidelity lens

**Verdict:** the look (§2–§3) and resume points (§9) are faithful, and the Rail is the Mark II's bottom gauge strip rebuilt. It still feels like an app for two reasons: **the voice and the HUD run on separate tracks**, and there are **no arrivals, endings, protocols or status readouts**, which are JARVIS's most recognisable habits. It also overdoes the wake beat and the wit. *(film)* = scene recalled and paraphrased; I couldn't reach a transcript to check it.

---

## MUST

**M1. The voice drives the HUD (§2a, §8).**
Spec: cue tags gain `[[focus:<rail-slot|window-id|dial-item>]]`. Using the TTS character-alignment timestamps, the hub snaps corner brackets onto the element on the frame its word is spoken and lifts its line to `--cyan-hi` (250 ms), releasing 600 ms after the sentence ends. Every spoken item that's on screen gets a focus. If alignment is missing, fire at the start of the sentence.
Why: the HUD *is* the character, and information arrives by voice and visuals together (Favreau, befores & afters). A fading caption reads as a voice assistant bolted onto a dashboard.
Latency: none; it uses the same SSE stream, and ElevenLabs streams alignment with the audio.

**M2. Arrivals, mornings, endings (new §8.1).** This is the biggest gap.
- *Walk-in* (Laptop B unlock or input after ≥ 30 min idle, or the first wake in ≥ 2 h; no camera): leave standby, then at most **one greeting plus the one thing that changed**, spoken only if he's alone and outside quiet hours, otherwise visual only. "Evening. Lab four's draft is where you left it, at Results. Nothing new on Canvas." If nothing changed: "Evening." or silence.
- *First wake of the day*, at most 3 facts with numbers first, and only when he wakes Jarvis or an alarm he set fires: "Morning, De Wet. Minus fourteen, minus twenty-two with the wind. CHEM at 8:30, Thorvaldson 159. Nothing due today."
- *Wind-down* ("that's it for tonight", or the last block ends): "PPS 7 to question nine, lab draft through Results. Tomorrow starts with GE 122 at 9:30. Both are saved where you left them." Then fade to standby with the done arcs showing on the dial.
Why: S1 (ready, one line); *(film)* the 2008 time/temperature/tide wake-up readout; *(film)* *Iron Man 2*'s "welcome home" plus one remark; peak-end (code of conduct #16).
Rules: reads only; no "missed you", no streaks (C40).
Latency: the "since you left" diff is pre-computed every 5 min, and lines come from the phrase cache (~75 ms to first audio).

**M3. Ration the wake beat; never gate input (§3, §6).**
The full 1.2 s tilt-snap plays only on the first wake of a session (hub launch, or standby ≥ 20 min). Later wakes get a 250 ms "tighten" (the dotted ring goes 1.9 → 1.8 R and back). The energy ring shows Listening **from frame 1**.
This also fixes §3 vs §6 (1.2 s vs ≤ 300 ms on open): open = the ≤ 300 ms assemble, with the tilt alongside, never blocking.
Why: Huw's 3D moments "are rare, which gives them a cinematic payoff". *(film)* the full HUD boot plays once, at the first suit-up.
Latency: removes up to 1.2 s of perceived lag on every "hey Jarvis".

**M4. Rarer wit (§8 "Humour").**
Replace "one dry aside per exchange" with **at most one per session (~1 in 15 lines); never in alerts, approvals, errors or readouts; never when he's behind, stressed or not alone.** Only two forms: understatement aimed at the situation ("The syllabus calls this lab 'short'. It's open, with last year's data beside it.") or polite literal agreement.
Why: in S4/S5 the aside is one beat among plain readouts; Clark et al. found humour valued only as novelty.
Latency: none.

**M5. Register: short, complete, slightly formal (§8, §9 examples).**
- Offers are complete sentences: "Question seven is where you stopped. Shall I take you there?" Fragments ("Seven?", "Thermo deck, card 18.") only for pure readouts.
- "No visible pattern" varies **content**, never **register**.
- At most one address term per exchange, only in greetings, alerts and read-backs. That gives the JARVIS cadence with "De Wet" or "sir".
- No filler, no exclamation marks, no "Sure!" or "Got it!", no emoji in captions.
- Jobs over ~1 s get an instant two-word acknowledgement ("Checking Canvas.").
- "Shall I" in at most 1 in 5 offers, so it never tips into imitation.
Why: research: "courteous, brief, slightly formal" *(film: "Shall I render…?")*; mixed registers make him drift.
Latency: acknowledgements come from the phrase cache (~75 ms), so slow jobs feel faster.

**M6. A critical alert is spoken once, then lives on screen (§5.6).**
One spoken line per critical item. Speak again only when it crosses a new threshold ("leave now"), never on a timer.
Why: *(film)* JARVIS keeps warning about low power until Tony snaps at him to just leave it on the screen (TV Tropes, "Critical Annoyance"). This is "flag once, then defer".
Latency: none.

---

## SHOULD

**S1. Named protocols (new §8.2, Controls).**
Bundles he names himself (Study, Lab, Exam, Wind-down, Game), never the films' names. He says the name; Jarvis echoes it as a question ("Study protocol?"); yes → layout, focus, phone quiet, timer, lecture pack beside the work. Bundles hold only local, undoable actions by default. If one includes a write, the read-back names it: "Study protocol. That also moves your 9 pm block to 10. Go ahead?" The yes covers only what was read back, so every write still waits for his yes.
Why: S10, House Party and Clean Slate confirmed by echo.
Latency: T0, ~0.1 s.

**S2. Mechanical assembly, not app transitions (§2a, §6).**
- Each window assembles in ≤ 300 ms: brackets snap to the corners (80 ms) → the frame draws between them (120 ms) → the kicker resolves left to right (100 ms) → a "lock" (brackets 1 → 1.5 px for 80 ms).
- Easing `cubic-bezier(.2,.9,.1,1)`: a hard stop, no springs (springs read as a phone OS).
- Fix the conflict: windows Jarvis pushes assemble **in place**; windows he recalls **grow from their Rail slot**.
- Opening a Rail slot fans its cards out in an arc, 40 ms apart. TIDY moves windows with a 40 ms chained lag.
Why: the keyhole widget "turned, unlocked, fanned out", "a mechanical visual in a digital form", damped to lag (Seki).
Latency: content is interactive at 0 ms, and animation is an overlay only.

**S3. Status readout (§8, T0).**
"Status" or "how are we doing?" gives 3 items in a fixed order (time-critical → progress → systems), each focused on the HUD as it's spoken (M1). "Two due this week, the nearest Thursday at noon. You're four questions into PPS 7. Canvas synced six minutes ago."
Why: S6 and S11; Bettany's lines existed to explain state.
Latency: data already in memory, ~75 ms to first audio.

**S4. A minimal sound layer (new §6.1).**
Three original earcons, nothing sampled from the films:
- **Wake**: a two-note glass rise, 250 ms, with the full wake beat only.
- **Accepted**: a soft tick ≤ 100 ms after a recognised command.
- **Critical**: one low tone, alongside M6.

Rules:
- ~18 dB under the voice, ducked while Jarvis speaks.
- Silent for routine pushes and in quiet hours.
- Laptop B only by default. **Never on Laptop A in game mode.**
- Setting: Off / Minimal (wake + accepted, the default) / Full.
Why: the films' HUD is never silent, but the mix aimed for power "without being overbearing" (Boyes). No source on the HUD's own sounds; this is a proposal.
Latency: preloaded WebAudio buffers play in < 10 ms; the tick is a perceived-speed win for push-to-talk.

**S5. Colour roles closer to Stark tech (§2, §3 dial, §4).**
- Done = a full `--cyan-hi` ring plus "DONE", not green. Done dial arcs are filled `--cyan-hi`, upcoming arcs are outlined `--line-dim`, and missed ones stay dim. Green only in Under the hood.
- Amber means only "needs you", so "ACTIVE" moves to `--cyan`.
- Fix: §4's `--hud` is undefined, so use `--cyan`.
Why: green "reads as old tech" (pushing-pixels); Territory gave green to Banner, not Stark.
Latency: none.

**S6. Condensed type for hero numbers and titles (§7).**
Lexend reads as an edtech app; Huw uses "bold condensed caps". Zero-cost: hero numbers in JetBrains Mono 500 (tabular), titles Lexend 600 tracked .08em. Better: one self-hosted OFL condensed face (e.g. Barlow Condensed 600, ~20 KB subset) for titles and numbers only.
Latency: none at runtime.

**S7. Real instrument micro-data (§3, §7).**
Up to 4 tiny mono readouts at the orb's cardinal ticks, all real and non-personal ("TURN 412 MS", "CANVAS 6 MIN", "MIC −32 dB"), at the grid's brightness tier.
Why: Hansen's micro-text matched the story; film density without fake text.
Latency: updates ≤ 1 fps.

**S8. The approval ring shouldn't feel like a bomb timer (§3, §4).**
A steady amber ring plus "AWAITING YES", with only the dim dotted ring draining over the mic window; reduced motion shows a word, not a ticking number. When the window ends, the item goes to the Rail and is asked aloud **once more at most**, at the next breakpoint.
Why: the films never rush Tony with a countdown.
Latency: none.

**S9. The Rail as a gauge cluster (§5).**
Each slot is a mini 270° arc gauge (today's share done) + count + worst-state glyph. "Since you looked" is a static cyan notch, never a red badge count (an app and FOMO pattern, C40).
Why: the Mark II's persistent bottom strip of instruments (scifiinterfaces breakdown).
Latency: ≤ 1 fps.

**S10. Fix the dial and mote collision (§3).**
The day dial (2.4–2.6 R) sits inside the motes (2.2–2.7 R). Move the motes to 2.75–2.95 R, or hide them while the dial shows.
Latency: none.

---

## NICE

- **N1 (§9):** the Q7 highlight becomes a reticle lock: brackets snap around the heading in 250 ms, then fade over 1 s.
- **N2 (§6):** depth without parallax: unfocused windows at 0.98 scale, `--line-dim`, 75% opacity.
- **N3 (§3):** hash marks step in order with amplitude instead of re-randomising; in the films glitch means damage.
- **N4 (§2a):** a static 1 px top-edge sheen on windows (`--cyan-hi` at 8%) for the films' glassiness.
- **N5 (§3):** the 3D emphasis separation happens at most once per utterance.
- **N6 (§10):** demo story: arrival → status → "Study protocol?" → Q7 reticle lock → wind-down.

All NICE items: zero latency cost.

---

## Standing-rule guards
- Others present → visual only, tier-1 data; wit only when he's alone.
- Flag once → M6, S8. Writes wait for his yes → S1 read-backs.
- No emotional probing → "read the moment" changes word count only; never names a feeling.
- Own voice → "sir" opt-in; "Shall I" ≤ 1 in 5.
- Laptop A → static strip, no sounds in game mode. Latency → nothing gates input.
