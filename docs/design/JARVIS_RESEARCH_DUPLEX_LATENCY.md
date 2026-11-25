# Jarvis research: talking over him, cutting latency, thinking fillers

Written 2026-11-17 from his request: "keep Jarvis listening while he's talking, like ChatGPT goes quiet when you
talk over it; make the audio processing faster, cut the latency by a lot; use filler words while he's thinking so he
doesn't go quiet. Research how to do this properly before you do it."

## 1. Talking over Jarvis (full duplex, barge-in)

**Why he couldn't.** With laptop speakers the mic hears Jarvis. Without echo cancellation, his own voice trips the
voice detector and he interrupts himself on every answer, which is why v0.8–v0.10 muted the mic while he spoke
(half-duplex). Every voice-agent guide says the same: without echo cancellation or headphones, the agent hears itself
and cuts its own answers short.

**How it's done properly.** Acoustic echo cancellation (AEC) with the *exact* audio the speaker played as the
reference ("far-end" / "render" signal): an adaptive filter learns the speaker-to-mic path and subtracts it. The
reference must be the clean played audio, time-aligned; a bad reference is the usual cause of echo that won't go
away. WebRTC's AEC3 (the canceller in Chrome) is the standard, and it estimates the delay itself.
`pywebrtc-audio` 0.2.0 ships it as a Python package with Windows x64 wheels for Python 3.10–3.14.

**Measured in the sandbox** (AEC3 through `EchoCanceller`, a real speech recording played back as a simulated laptop
echo, 40–50 ms delay plus a room tail):
- Echo alone: **45–57 dB removed**, whether the reference arrives on time or 200 ms early (client buffering).
- Cost: **0.25 ms per 20 ms frame** (~1% of one core); fine for Laptop A's ≤ 3% CPU budget (C37).
- While he and Jarvis talk at once, AEC3's suppressor also removes much of *his* voice (with a loud echo, all of
  it). That's normal double-talk behaviour, and it shapes the design: the cancelled mic is used to **notice** he's
  talking; his words after Jarvis stops come through clean.

**Not every sound is an interruption.** The production guides (Pipecat, LiveKit, Deepgram, AssemblyAI, Hamming)
agree on the failure modes: false barge-ins from "mm-hmm", "yeah", coughs and leftover echo. The fixes are a minimum
number of real words before interrupting (Pipecat's MinWordsInterruptionStrategy, e.g. 3), ignoring backchannel
words (LiveKit's filler-word ignore list; AssemblyAI's backchannel set), and checking the words.

**What v0.11.0 does (ChatGPT-like):**
1. **Client:** the mic goes through AEC3 with what the speaker actually played (after ducking) as the reference,
   then the mic boost. The mic stays open while Jarvis talks. If the canceller isn't installed, it falls back to
   half-duplex.
2. **Core, "confirm" mode:** his first speech frame while Jarvis is speaking **ducks Jarvis to 30% at once** (he
   hears that he was heard). Jarvis **stops** when it's clearly him and clearly meant: either 2 real words in the
   live transcript, or 600 ms of continuous speech. "Real" means not a listener noise (mm-hmm, yeah, right, okay…)
   and not one of the words Jarvis is saying right now (echo the canceller missed). If he goes quiet first, Jarvis
   returns to full volume and carries on, and that bit of sound is never treated as a question.
3. No speculative Claude call starts while he's talking over Jarvis (it would be wasted).

Latency effect: the stop takes the time to hear two words (typically 300–600 ms after he starts), not the 20 ms of a
bare voice detector. That's the price of not being interrupted by "mm-hmm". The duck is instant. On headphones,
`--barge-in` keeps the old immediate stop.

**Bug found on Laptop B the same morning (v0.10.2: "he hears me but says nothing").** The latency log showed 20
of 26 turns with an empty transcript and the real questions never reaching a first token. A noise (a fan, a click)
right after a question started a new "turn"; any new turn interrupted the pending answer before it was spoken
(immediate barge-in also covered "thinking"), so the answer was dropped. v0.11.0 applies the confirm rule while
Jarvis is thinking too: a sound with no words never cancels an answer (the noise turn is dropped and the orb returns
to what it was showing); two real words mean a new question, which replaces the old one.

## 2. Where the time goes, and what cuts it

**His real numbers** (Laptop B, `voice-latency.jsonl`, measured from the moment his speech ended + 200 ms VAD):
- STT final: **~250–700 ms** (median ~450). The biggest piece we control.
- Claude's first token: **~400–1,100 ms after that** (faster when speculation hits: ~880 ms total vs ~1,400–1,800).
- TTS first byte: **~250–450 ms after the first token**.
- First sound: **~1.2–2.2 s** in total.

**Findings**
- *Smaller STT chunks aren't free on a CPU.* Nemotron streaming also comes as 160 ms and 80 ms exports (sherpa-onnx,
  int8). In the sandbox (2 cores) the 160 ms model ran at 1.1× real time and the 80 ms at 2.0× (slower than real
  time), with a *slower* final (325 / 615 ms vs 183–204 ms for 560 ms), because the work per second of audio grows
  as the chunks shrink. Laptop B's i7-12700H has far more cores, so this needs a benchmark there before switching
  (`Benchmark speech.bat`, next step). Accuracy was the same on the test recordings.
- *Claude Haiku 5.5:* the minimum cacheable prompt is reported as 512 tokens, so the ~1,250-token persona should be
  served from Anthropic's prompt cache. v0.11.0 logs `cache_read` per turn to prove it (the first thing to check if
  the first token stays slow).
- *ElevenLabs Flash v2.5* is ~75–100 ms of model time; the rest is network and waiting for the first text chunk. The
  WebSocket is already warm (re-opened when he starts talking).
- *Speculation* (starting Claude on a stable partial before the turn is confirmed) is the biggest single win already
  in place; it saves ~0.5 s when it hits.

**Plan, in order of payoff**
1. Benchmark 560 / 160 / 80 ms STT on Laptop B (`Benchmark speech.bat`); switch if 160 ms runs under ~0.5× real
   time there. Expected: −150 to −300 ms on every turn.
2. Confirm prompt caching from the `cache_read` field; if it's 0, fix the cache breakpoint. Expected: −100 to −300 ms.
3. Tune speculation (fire after 80 ms of a stable partial instead of 120 ms). Expected: more hits.
4. Later: the T0 router answers simple things (time, timers, stop) with no LLM at all, and phrase-cached replies play
   in ~1 ms.

## 3. Thinking fillers

**What the research says.** Fillers mask latency: people read "hmm" or "one moment" as someone thinking, not as a
broken system. But they backfire when they don't fit ("On it!" before a weather question sounds wrong) or come too
often; keep them short and neutral. Fillers fit best where a person would pause, such as a lookup.

**What v0.11.0 does:**
- If Claude's first word hasn't arrived **800 ms** after he finished, Jarvis says one short filler: "Mm.",
  "One moment." or "Let me see.", rotating, in his own voice.
- The fillers are rendered once per voice into the phrase cache and play from disk in ~1 ms; a filler is never
  synthesised live (that would add latency).
- At most one per answer, and none within 20 s of the last, so they stay rare (one source cites GPT Realtime at a
  ~16% filler rate).
- It's skipped if he's already speaking, the answer failed, or the turn moved on. The latency log notes which turns
  had one.

Latency effect: none on the answer. Perceived silence after 800 ms drops to ~0, because the filler plays from the
local cache.

## Sources
- AssemblyAI voice agent docs (echo without AEC causes self-interruption; backchannel list)
- Fora Soft, "Echo cancellation (AEC)" (the reference must be the clean far-end audio); GetStream, "What is echo
  cancellation"
- pywebrtc-audio on PyPI and Strands Labs docs (AEC3, Windows wheels, 3.10–3.14)
- protoVoice audio handling guide (echo guard vs reference AEC for laptop speakers)
- Pipecat interruption strategies (MinWordsInterruptionStrategy); LiveKit agents issue #4450 (ignore filler words);
  Deepgram, "Backchannels vs interruptions"; Hamming interruption runbook
- NVIDIA Nemotron Speech FAQ and Together AI model card (80–1,120 ms chunk sizes); sherpa-onnx asr-models release
- Haiku 5.5 guide (512-token minimum cache); Anthropic "Reducing latency"
- ElevenLabs latency optimization docs (Flash ~75 ms; auto_mode; chunk schedule)
- dev.to "5 tricks to hide voice agent latency"; PolyAI voice polish; LiveKit "thinking sounds" thread; Parloa
