# Review recording (v0.16.0)

De Wet asked on 2026-11-19 for everything about every interaction to be kept so it can be reviewed (first review:
Sunday 2026-11-22). It is switched on by him ("Start review recording.bat", 4 days, switches itself off) and is the
second switched-on exception to C21 after the 20-minute test recording.

## Where
On Laptop B (the core): `C:\Jarvis\logs\review\<date>\events.jsonl` and `...\<date>\audio\*.wav`.
On each laptop that runs a hub: `C:\Jarvis\logs\voice-host.log` (the hidden voice program's states and errors).
`C:\Jarvis\logs` is the folder this chat can read on Laptop B; nothing here is in git or leaves the laptop by itself.

## What a line is
`{"t": local time, "mono": seconds, "n": order, "k": kind, ...}`. Kinds:

| kind | what |
|---|---|
| `review`, `env`, `load` | recording switched on; what Jarvis runs on and how it is set; memory, CPU, event-loop lateness every 10 s |
| `voice.session`, `voice.client`, `voice.sent`, `client.note` | a voice window connecting; what it sent (meter thinned to 1/s) and was told; its own notes: `start` (mic, speaker, mode), `wake` (score), `window` (wake-word near misses, frames dropped, sound ran dry), `reply_audio` (how each reply's sound arrived) |
| `turn.heard`, `turn.said`, `turn.ended`, `turn.timing` | what the speech model heard; what Claude was asked and Jarvis said; how the turn ended with every flag and the .wav of his side; ms from end of speech to each stage |
| `llm.request`, `llm.response`, `llm.error` | exactly what Claude was sent (system prompt and tool definitions once, then "same as the last request"), what came back, stop reason, tokens, time to first words |
| `tool` | each tool call: input, result, ms, error, what it put on screen |
| `task` | a background task: start, every message of its agent session, end |
| `bus` | every event sent to the hub (orb, captions, windows, toasts, settings); `orb.state` thinned to changes + 4/s |
| `act` | every button or switch he used in the hub, and what the core answered |
| `log` | every log line unfiltered, with the full traceback of the error being handled |

Never in a line: keys, passwords, session tokens, cookies (taken out by field name and by shape), or any sound from
before he woke Jarvis.

## Reviewing
1. Link the chat to Laptop B and read `C:\Jarvis\logs\review`.
2. `python tools/review_summary.py <folder>` gives the first look per day: how turns ended, the wait at each stage,
   model stops and empty replies, tool failures, warnings, what the voice window reported, load.
3. Then read the worst turns line by line (`turn` ties the lines together) and try other speech models on the .wav
   files (the accent work).
