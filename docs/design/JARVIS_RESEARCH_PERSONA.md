# Jarvis research: personality, and hearing a quiet voice

Written 2026-11-17 after his first spoken tests on Laptop B: "his personality feels too much like Claude and not
enough like Jarvis", "words still get cut off and I don't like having to talk too loud".

## Part 1. How the film JARVIS talks

**Who he is.** The MCU AI is named after Edwin Jarvis, the Stark family's butler, and is built on the "gentleman's
gentleman" archetype: an English butler's composure, discretion and loyalty, in software. Character write-ups agree
on the same traits: dry British wit, unwavering loyalty, calm and measured delivery, and sarcasm reserved for his
employer's recklessness. Commentators describe him as the straight man to Tony's eccentricity, and as his voice of
reason. Paul Bettany's delivery is steady and never rushed; the emotion comes through inflection and timing, not
through emotional words.

**How he talks** (from the films, as I know them; the line-by-line transcript count is still to do, see below):

| Pattern | What JARVIS does | What v0 (Claude) did instead |
|---|---|---|
| When he speaks | When spoken to, or when there's a status or a risk to report. No small talk. | Chatty, asked how he could help |
| Length | Mostly one sentence; acknowledgements of a few words | Two to three sentences with pleasantries |
| Address | "Sir" in most lines, once | "De Wet", warm and familiar |
| Content | Status first: numbers, times, states | Feelings and offers first |
| Suggestions | Polite questions: "Shall I…", "Would you like me to…" | Open questions ("What can I do for you?") |
| Concern | States it once with the fact behind it, then complies | Hedged, or none |
| Wit | Deadpan understatement in reply to banter or a rash idea; never a set-up joke | Friendly enthusiasm |
| Greeting | A status line (time, weather, what matters) | "How can I help you today?" |
| Vocabulary | Formal and precise: "Indeed", "As you wish", "I believe", "Might I suggest" | Casual assistant phrases |

**Why v0 sounded like Claude.** The placeholder persona was five lines. With no character to stand on, Haiku fell
back to its assistant register: warmth words, offers of help ("What can I do for you?"), a question at the end of
every reply, and no "sir". Voice-agent prompting guides say the same thing about every model: vague style goals don't
stick, listing the exact phrases to avoid works better than "be casual", and a few worked examples move behaviour
more than a page of rules. Anthropic's guide on keeping Claude in character recommends a detailed role in the system
prompt plus the common scenarios with their expected responses.

**What changed (v0.9.0, `jarvis/voice/persona.py`).** A full persona built on the table above:
- How he talks, as rules: speaks when spoken to; one sentence of 5–15 words; "sir" in most replies; status first;
  suggestions as "Shall I…"; concern once, then comply; deadpan wit only in reply; greetings as a status line.
- A "never say" list of the exact chatbot phrases (and no exclamation marks, lists or markdown).
- Twelve short example exchanges. Every one is original, written for De Wet's life (lab reports, eigenvalues, the
  drop deadline). Nothing is quoted from the films.
- His code of conduct still binds: humour never at his expense or when he's stressed; no remarks on sleep, gaming or
  habits; he has the final word; writes are only proposed.
- A "Now" block with the real date and time on every turn, because v0 said "Good afternoon" at 8:34 am.
- A test keeps the examples short, "sir"-heavy and free of chatbot phrases.

**Latency effect:** none to small. The persona is ~1,250 tokens at the front of every request, marked for prompt
caching. If it's under Haiku's minimum cacheable length it's simply read each turn, which costs a few tens of
milliseconds of prefill. The Now block is tiny and isn't cached.

**Still to do.** He asked for every JARVIS–Tony exchange to be analysed. The transcript pages need his OK to open,
which nobody was there to give. With it, the plan is: count every JARVIS line across the five films (words per line,
share with "sir", share initiated vs replying, type: status, answer, acknowledgement, warning, offer, wit) and tune
the rules above to the measured numbers. The analysis stores statistics and patterns only, never the lines.

## Part 2. Why quiet speech got cut off

**What the mic test showed.** His speech came in at about −36 to −47 dBFS, quiet for a laptop mic, with digital
silence (−90 dB) between words, the signature of Windows noise suppression (Voice Clarity / audio enhancements)
gating the mic. Raising the input volume brought speech to about −23 dB.

**The cause.** Pipecat's VAD counts a 32 ms chunk as speech only if Silero's confidence passes its threshold *and*
the volume passes `min_volume`. Pipecat's defaults are confidence 0.7 and volume 0.6. Set those too high and soft
trailing speech reads as silence: an early endpoint, the "fragmentation" failure. That is the cut-off he heard.

**Measured on the real models** (Silero + Nemotron, sandbox, the model's own test recording at three levels):

| Voice level | Pipecat defaults (0.7 / 0.6) | v0.8.1 (0.6 / 0.3) | v0.9.0 (boost + 0.5 / 0.15) |
|---|---|---|---|
| −30 dB (normal) | 91% of speech heard | 91% | 94% |
| −47 dB (his first test) | 76% | 88% | 93% |
| −56 dB (talking softly) | **0%** | 83% | 91% |

The speech recogniser itself transcribed every level word for word; it was only the voice detector that dropped
words. So v0.9.0 adds:
- **Mic boost** (`MicBoost`): automatic gain that follows his voice over about a second and lifts it towards
  −22 dB, up to 8× (18 dB). It never pumps within a word, digital silence stays silent, and loud audio is clipped,
  never wrapped.
- VAD at confidence 0.5 and volume 0.15. The Silero model still decides what is a voice.
- STT pre-roll from 400 to 600 ms, so a soft first word is kept.
- Echo mute after Jarvis speaks from 350 to 250 ms, so a quick reply isn't lost.
- `Mic test.bat` now shows the boost and his typical speech level.

**He should still** turn off Windows' Voice Clarity / audio enhancements for this mic (Settings › System › Sound ›
the mic). They gate the signal before Jarvis ever sees it.

**Latency effect:** none. The boost is a multiply per 20 ms frame (microseconds), and the pre-roll is audio from
before the turn started.

## Sources
- Wikipedia, "J.A.R.V.I.S." (Edwin Jarvis and H.O.M.E.R. origins; Paul Bettany)
- Character write-ups: shapes.inc character pages; Josh Worth, "Personality Profiles of Pop-Culture Computers";
  articles on Bettany's performance
- Anthropic docs: "Keep Claude in character"; prompt library on few-shot examples
- AssemblyAI voice-agent prompting guide; LiveKit, "Prompting voice agents to sound more realistic"; Vapi prompt
  reference
- Pipecat docs, "Speech input" (VADParams defaults and warnings); Freya latency notes on the VAD state machine
- Windows Voice Clarity / audio enhancement guides (Microsoft Q&A, Rode, GeekRewind)
