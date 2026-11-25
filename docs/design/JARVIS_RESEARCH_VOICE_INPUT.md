# Jarvis research: taking his voice in properly (v0.12.3–v0.12.5)

Written 2026-11-17, after his first real voice sessions on Laptop B. His words:
- "the speech thing, like taking my voice input is still extremely bad";
- "the equalizer barely works";
- "it isn't catching instructions, going in and out of listening very quickly, keeping quiet at the slightest
  noise";
- "use a working system as a baseline".

## 1. What his sessions showed

- **The first session:** of 11 turns, 1 got a full answer (1.54 s to first audio). 6 were "empty" (the detector
  heard sound, speech-to-text found no words), 2 were dropped as noise and 2 were interrupted.
- **One crash:** the speech engine aborted the core mid-answer (fixed in v0.12.3: one user of the engine at a time).
- **Hearing check (v0.12.3), on his laptop:** the mic is not the problem.
  - Room about -50 dBFS, his voice about -20 dBFS: 30 dB apart.
  - 21 of 22 words right with the v0.9 boost and with WebRTC AGC2; 20 of 22 with AGC2 plus noise suppression.
- **So the problem was turn taking,** not hearing: which sounds count as him, and when Jarvis yields.

## 2. Working systems as the baseline

| | Pipecat (the framework whose parts we use) | LiveKit Agents | OpenAI Realtime (server VAD) | Jarvis v0.12.3 |
|---|---|---|---|---|
| Detector | Silero | Silero | built in | Silero (via Pipecat) |
| Speech needed to start a turn | 0.2 s | 0.05 s | — | **0 s** (and "starting" counted as speech) |
| Silence before "stopped" | 0.2 s, then Smart Turn v3 decides | 0.55 s, then their turn detector | 0.5 s | **0 s** + 0.2 s of our own counting |
| Confidence | 0.7 | 0.5 | 0.5 | 0.5 |
| Loudness gate | 0.6 (BS.1770 scale: 0 = -110 LUFS, 1 = -10 LUFS) | — | — | **0.15 (about -95 LUFS: everything passes)** |
| Audio kept from before the start | (pre-speech in Smart Turn) | 0.5 s | 0.3 s | 0.6 s |
| What it takes to interrupt the assistant | strategies (words, VAD) | **0.5 s of speech** (adaptive model optional) | — | ducked on the **first** frame, stopped after 1 s |

Other sources agree on the interruption side:
- **VideoSDK's hybrid mode:** at least 0.2 s of speech and 2 recognised words.
- **Freya's speakerphone guidance:** ignore the first ~0.3 s while the assistant talks, and require 2+ words.
- **Deepgram:** TV, traffic and other conversations cause false barge-ins; noise suppression reduces them but can
  clip quiet speakers and first words.
- **Hamming's interruption runbook:** false barge-ins come from "noise, echo, short backchannel, overly sensitive
  VAD".

## 3. What simulation showed (sandbox)

Real speech clips (openWakeWord's test recordings) were run through the real Silero detector and Smart Turn v3 at
his measured levels, using the real pipeline processors:

- **Clean speech, or quiet background voices:** the old settings and Pipecat's baseline behave almost the same.
  Silero rightly calls distant voices speech, so smoothing alone was not the fix.
- **Jarvis's own voice left over after the echo canceller** (laptop speakers), in 6 s of Jarvis talking:

  | Echo left over | old | baseline | fitted gate | fitted + echo guard |
  |---|---|---|---|---|
  | about -44 dBFS | 4 times | 3 | 1 | **0** |
  | about -36 dBFS | 4 | 4 | 4 | **1** |
  | about -30 dBFS | 4 | 5 | 5 | 3 |

  His "stop" over Jarvis was caught every time in every setting.

So the main cause of "going quiet at the slightest noise" and "in and out of listening" is **Jarvis hearing himself**:
the duck fired on the first frame of anything while he spoke.

## 4. What v0.12.5 changes

1. **Pipecat's default detector set-up as the baseline:** confidence 0.7, 0.2 s to start, 0.2 s to stop (then Smart
   Turn decides), gate 0.6. "Starting" no longer counts as speech.
2. **Echo guard:** while Jarvis speaks, a second, stricter detector decides (confidence 0.85, gate +0.1). Both hear
   every frame, so the switch is seamless; Silero costs about 1 ms per 32 ms window.
3. **Duck later:** Jarvis gets quieter after 0.3 s of confirmed speech (about 0.5 s in all, LiveKit's default
   interruption duration), not on the first frame. He still stops only after about 1 s of continuous talking (his
   v0.11.2 ask).
4. **Conversation check.bat measures it on his own mic.** He follows prompts for about 50 s: five instructions (one
   with a pause), a tap and a cough, quiet, Jarvis talking while he stays quiet, and Jarvis talking while he says
   "stop".
   - The recording goes through the voice window's own echo canceller and mic set-up.
   - It is then run through the core's detector, Smart Turn and speech model under each candidate: old, baseline,
     fitted gate, and fitted plus echo guard.
   - Each candidate is scored on instructions caught, split, missed, false starts (and how many were Jarvis hearing
     himself), and word errors.
   - The best is saved to `voice/turns.json` and used from the next core start. Until he runs it, the default is the
     baseline plus the echo guard.

**Latency:**
- Turns now start 0.2 s after his first sound, but the 0.6 s of audio kept from before the start means no words are
  lost, and the end of turn is unchanged (0.2 s plus Smart Turn). So time to answer doesn't change.
- Ducking comes 0.3 s later than before, on purpose.

## 5. Still open

- **Headphones beat any echo canceller** (the voice design already says so). If the check still shows Jarvis
  hearing himself, try them.
- **Background voices** (a TV, a roommate) are speech to any detector. The fixes are push-to-talk or a wake word
  (parked on a branch), or background-voice cancellation (LiveKit's BVC or Krisp, both cloud or paid).
- **Barge-in by words** (Pipecat's min-words strategy, VideoSDK's hybrid mode): stop when the transcript has two real
  words. Our "meant words" check does this only while Jarvis is still thinking; it could also cover speaking.

## Sources

- Pipecat, Speech input and VAD: https://docs.pipecat.ai/learn/speech-input ; VADParams defaults:
  https://reference-server.pipecat.ai/en/latest/api/pipecat.audio.vad.vad_analyzer.html ; Smart Turn:
  https://docs.pipecat.ai/server/utilities/smart-turn/smart-turn-overview
- LiveKit, Silero plugin defaults: https://docs.livekit.io/python/livekit/plugins/silero/index.html ; turn-taking
  tuning: https://docs.livekit.io/agents/logic/turns/tuning/ ; turn detector:
  https://docs.livekit.io/agents/logic/turns/turn-detector
- OpenAI, Realtime VAD: https://developers.openai.com/api/docs/guides/realtime-vad
- Deepgram, Audio preprocessing and barge-in: https://developers.deepgram.com/guides/deep-dives/audio-preprocessing-barge-in
- VideoSDK, VAD and interruption config: https://docs.videosdk.live/ai_agents/core-components/voice-activity-detection
- Hamming, Interruption handling runbook: https://hamming.ai/blog/voice-agent-interruption-handling-runbook
- Freya, VAD endpointing settings: https://freya-voice-pipeline-settings.pages.dev/parts/07-vad-endpointing.html
