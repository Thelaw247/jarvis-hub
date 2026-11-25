# Earcons (N2; remade gentle in F1)

Three original sounds, synthesised by `make_sounds.py` from sine waves (nothing sampled, nothing from the films).
Run `python ui/sounds/make_sounds.py` to make them again (the output is the same every time). Each is a low sine
with at most a faint second harmonic, a gentle low-pass (1.8 kHz), a raised-cosine attack of at least 15 ms (no
click) and a smooth tail to silence; peaks are about 6 dB under v0.4.1's. Mono, 16-bit, 22.05 kHz, all under 32 KB.

| Sound | Length | When |
|---|---|---|
| `wake.wav` | 520 ms | a soft two-note rise (D5 → A5), only on the **first wake of the day** (with the full wake beat) |
| `tick.wav` | 55 ms | the non-verbal "heard you": the orb plays it when listening turns into thinking |
| `critical.wav` | 600 ms | one low tone (G3), when a critical alert arrives (Full only; never for one already there on load) |

**Window pushes are silent** (HUD v2 §7). His v0.4.1 report ("the sounds when windows open") was the tick, with
the old glass rise on a first wake, played ~75 ms before the windows landed, and twice: by the hub and by the Stage,
each with its own audio. Now:
- one page sounds: the one holding the `jarvis-earcons` Web Lock. The Stage takes it while it is open; the hub
  gets it back when the Stage closes (`soundOwner()`);
- the rise plays once a day (`localStorage` `jarvis.earcons.wake-day`, shared by both windows);
- for `ROUTINE_QUIET_MS` (600 ms) after a window push (or recall) nothing but the tick may sound, so no alert
  tone ever rides on windows arriving.

`earcons.js`:
- `play(name)` starts a preloaded WebAudio buffer (measured < 1 ms to start in the tests; target < 10 ms).
  Buffers are fetched and decoded when the page is idle, never on the strip.
- Level: ~18 dB under the voice, another 10 dB down while Jarvis speaks.
- Silent in quiet hours (`settings.quiet_hours`), in game mode (`now_card.moment = game` or
  `settings.game_mode = on`), on the strip (Laptop A), and for anything the level doesn't include.
- Levels: Off / **Minimal** (default: the first wake's rise + the tick) / Full (+ critical). Full adds nothing
  on window opens.
- `shouldPlay(name, ctx)`, `dayKey(now)` and `inQuietHours(q, now)` are pure, for tests.
- Browsers start audio only after a click or key; the Windows app can allow it at launch for Laptop B.
