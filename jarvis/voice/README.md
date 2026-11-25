# jarvis/voice: the voice loop (M0.4)

`pipeline.build_pipeline(...)`: VAD -> Smart Turn v3 -> streaming STT -> T0 router (on partials) -> T1 talker
(Haiku 5.5, speculative start) -> TTS (ElevenLabs Flash v2.5, phrase cache) -> audio out. Every outside
service is a port (`ports.py`); `fakes.make_rig()` wires the whole graph to fakes. Latency harness:
`jarvis/health/`, report: `python tools/latency_report.py`.

| File | What |
|---|---|
| `frames.py`, `processor.py` | Pipecat-shaped frames and processor graph (no Pipecat import) |
| `router_t0.py`, `approvals_t0.py` | T0 reflexes and the approval grammar (no LLM, ~10 us) |
| `talker_t1.py`, `chunker.py` | Messages API streaming, cached persona prefix, speculative start, speaking rules |
| `tts_elevenlabs.py` | one warm multi-context WebSocket, keep-alives, barge-in closes the context |
| `phrases.py` | phrase cache under `<core root>/data/voice/phrases/` + rotating wordings |
| `adapters_real.py` | Silero VAD, Smart Turn v3, sherpa-onnx Nemotron (Laptop B only) |

Keys: every Claude / ElevenLabs call goes through K1's `mgr.client("anthropic" | "elevenlabs").call(fn)`.

## In the core (v0.10.0): `/ws/voice`

`jarvis/voice/service.py` runs the pipeline inside jarvis-core: a client streams 20 ms 16 kHz PCM to `/ws/voice`
(paired device with write rights) and gets Jarvis's 24 kHz PCM back; orb states and captions go on the core's bus,
so the hub shows them. Models preload at core start when the packages, model, voice ID and keys are all there
(`/api/voice` says what's missing; `/healthz` stays green either way). One client at a time; the newest wins.
`jarvis/voice/client.py` is the client (`Talk to Jarvis.bat`): mic with MicBoost, speakers, half-duplex,
reconnects by itself. Checked in the sandbox with the real VAD, Smart Turn and Nemotron through the WebSocket
(fake Claude and TTS): audio comes back; model load ~11 s in the sandbox, hence the preload.

## First run on Laptop B: `setup-voice.bat`, then `Talk to Jarvis.bat`

`setup-voice.bat` installs the packages below into the core's venv, downloads the STT model to
`<Jarvis folder>\models\stt\` and runs `python -m jarvis.voice.talk --check` (says one line). `Talk to Jarvis.bat`
runs `jarvis/voice/talk.py`: the real pipeline with Laptop B's own mic and speakers, keys from Credential Manager (as
the core reads them), the voice ID from the hub (Controls › Keys › Voice). Half-duplex by default (no echo
cancellation on this laptop); `--barge-in` with headphones. Latency per turn goes to `logs\voice-latency.jsonl`.

Checked in the sandbox 2026-11-16 with the real models: Silero + Smart Turn v3 + Nemotron int8 transcribe the model's
test recordings word for word (after adding a 400 ms pre-roll so the first word isn't lost), decode ~220–260 ms per
560 ms chunk on 2 sandbox cores, end of turn ~70 ms, STT final ~90–280 ms after the VAD stop. Every Windows wheel
exists for Python 3.13. Not run: real mic/speakers, Claude, ElevenLabs (no keys in the sandbox).

## Packages (checked on PyPI 2026-11-16)

```
uv pip install "pipecat-ai[silero]==1.16.0" "sherpa-onnx==2.0.1" "openwakeword==0.6.0" \
               "silero-vad==6.2.3" "onnxruntime==1.32.0" "anthropic==2.8.0" "websockets==17.4" numpy
```

- **STT model:** `sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25` (encoder/decoder/joiner
  `.int8.onnx` + `tokens.txt`) from the sherpa-onnx `asr-models` release; unpack to `C:\Jarvis\models\stt\`.
- **Smart Turn v3:** bundled in pipecat-ai 1.16.0 as `smart-turn-v3.2-cpu.onnx`, run with onnxruntime (a core
  dependency); no download, no extra. The `local-smart-turn` extra (torch, coremltools: v2 only) is **not** needed.
- **Silero VAD:** bundled ONNX in pipecat (`[silero]` extra); `silero-vad` is the fallback package.
- **openWakeWord 0.6.0** runs in the client on Laptop A ("hey jarvis" model), not here.
- Pipecat on native Windows isn't officially supported (VOICE risks): fall back to WSL2 if it misbehaves.
