# Turns that got lost (2026-11-18): what the logs showed, what changed in v0.14.0

Source: Laptop B's `voice-latency.jsonl` and `core.jsonl` (ids, timings and flags only, C21). Every voice turn since
the core first ran there: **310 turns, 35 answered**.

| What happened to the turn | Turns | Cause | Fix (v0.14.0) |
|---|---|---|---|
| Sound, no words ("empty") | 165 | Mostly before v0.12.5's voice detector; noise, echo, taps | Already much lower since v0.12.5 (3 of the last 23) |
| Interrupted | 59 | He went on talking after a pause; the first half was cancelled and thrown away | The two parts are joined and answered as one thought |
| Dropped as "mm-hmm" | 23 | Words over Jarvis's voice with under 2 real words, including "yeah" on the last word of his question | A short answer to a question Jarvis just asked counts |
| Claude returned no text | 21 | Unknown from the flags (the stop reason wasn't logged); `max_tokens` was 200, tool search ran before most tools | Retried once with room and a plain instruction; says so if still empty; stop reason logged; all tools loaded; 600 tokens |
| Text but no voice | 6 | Interrupted before the voice started, or the turn had ended before late words arrived | Late words re-open the turn; a turn isn't closed while the talker is still working |
| Never ended | 3+ | The voice service never closed the context; `bot_speaking` stayed on, so everything after was "talking over" it | A watchdog closes a finished turn after 8 s without sound |

Other findings from the same night:
- **The orb closing and reopening:** `orb_state()` ignored that he was talking, so an older empty turn finishing sent
  "idle" under his voice, and the next meter tick sent "listening" again (the store treats a tick with a different
  state as a state change). Two "heard you" chimes were the same split thought ending twice. Now there is one rule
  for the orb's state, idle waits 0.4 s, a meter tick always carries the state already shown, and the chime plays at
  most once in 2.5 s.
- **The glow:** the level was only sent inside a detected turn, and Jarvis's own level was measured when his audio
  was *sent* (up to 0.3 s before it's heard, the first 0.3 s in one burst). The voice window now measures what its
  mic hears and what its speaker is playing and sends both ~12 times a second, asleep or awake; the orb's resting
  light and the standby sphere's halo follow the room.
- **Hearing ran behind real time:** every 20 ms frame waited on the speech model inside the call that reads the
  microphone socket. The worst turn's words arrived 19.4 s after he stopped, and the voice window dropped its
  connection five times on a keep-alive timeout. The model itself is fast enough (30% of real time on two sandbox
  cores, identical transcripts when fed in batches); the long stalls line up with the Claude desktop app's Linux VM
  being active on Laptop B (16 GB, 82% used when idle). The speech model now has its own ordered worker, the mic side
  never waits, each turn logs how fast the model ran (`stt_pct`) and, when it's slow, the free memory.
- **"Check my first class tomorrow" went to Canvas** because no tool could read a calendar. Added `calendar`
  (Google Calendar through Composio, read-only).
- **The sign-in** opened as a browser tab, nothing watched it, and the question was never picked up again. It now
  opens in a window of its own (Chrome's app window, same Jarvis profile); when the window closes, Jarvis is told
  and carries on with the question.
- **Speech starting and stopping audibly:** audio was written straight to the sound card. `playout.py` fades every
  start, end, stop and gap, ducks smoothly, and keeps the amplifier awake with noise at about -84 dBFS.

Latency effect: none on the first word of an ordinary answer. Tools are about one round trip faster (no tool
search). A sentence said in two parts costs one cancelled Claude call, as before, but is now answered whole. Idle
shows 0.4 s later by design.

## His accent
Read speech scored 21/22 words in the Hearing check, so the model is not far off; conversation is where it slips.
Three steps, in order of cost:
1. **Now:** Claude is told that what it hears is speech-to-text with mistakes and to work out what was meant from
   the conversation; `Teach Jarvis your voice.bat` measures the model on 24 things he'd really say and saves the
   words it gets wrong for him as a note Claude reads with every question.
2. **Next, with his recordings:** try other speech models on his own voice (the lessons folder and the opt-in test
   recordings are exactly that data) and switch if one is clearly better. A stronger model run once at the end of
   the turn is the likely winner on a laptop without a GPU.
3. **Later:** fine-tuning a model on his voice needs about an hour of transcribed speech; not worth it before step 2.
