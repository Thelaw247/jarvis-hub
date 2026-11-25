""""Hey Jarvis", heard on the laptop itself (v0.13.0): openWakeWord's pretrained hey_jarvis model, ONNX on CPU.

v0.13.4: the three openWakeWord models run here directly on onnxruntime (the same steps as openWakeWord 0.6.0's
streaming path: melspectrogram -> speech embedding -> hey_jarvis), so the openwakeword package and the
scikit-learn/scipy it pulls in aren't needed (scikit-learn failed to import on Laptop A). Scores match
openWakeWord's (tests/voice/test_wake_ptt.py compares them when it's installed).

The models (hey_jarvis ~1.3 MB, plus the shared melspectrogram and embedding models) live in
<Jarvis>/voice/wakeword; setup downloads them once from openWakeWord's GitHub release. About 2 ms of CPU per 80 ms
of audio. "Hey Jane", "Alexa" and "hey Mycroft" scored at most 0.02 against the 0.5 threshold in the sandbox;
Wake word test.bat shows the live score so the threshold can be set to his voice.

    python -m jarvis.voice.wake --download      # fetch the models (setup does this)
    python -m jarvis.voice.wake --test          # say "hey Jarvis" and watch the score
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

from jarvis.voice import mic_profile

MODEL = "hey_jarvis"
FILES = ("hey_jarvis_v0.1.onnx", "melspectrogram.onnx", "embedding_model.onnx")
RELEASE = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/"
CHUNK = 1280                 # 80 ms at 16 kHz: what the model takes
THRESHOLD = 0.5
COOLDOWN_S = 1.5             # one "hey Jarvis" wakes once
PREROLL_S = 0.2              # sent ahead of the first frame after the wake word, so no syllable is clipped


def folder(base: Path | None = None) -> Path:
    return (base or mic_profile.root()) / "voice" / "wakeword"


def available(base: Path | None = None) -> bool:
    try:
        import onnxruntime  # noqa: F401, PLC0415
    except ImportError:
        return False
    return all((folder(base) / f).exists() for f in FILES)


def download(base: Path | None = None) -> Path:
    target = folder(base)
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = target / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        part = dest.with_suffix(".part")
        with urllib.request.urlopen(RELEASE + name, timeout=60) as r, open(part, "wb") as f:  # noqa: S310 - fixed URL
            f.write(r.read())
        part.replace(dest)
    return target


class HeyJarvisModel:
    """openWakeWord 0.6.0's streaming pipeline for one model, fed exactly one 80 ms chunk at a time."""

    def __init__(self, d: Path) -> None:
        import numpy as np  # noqa: PLC0415
        import onnxruntime as ort  # noqa: PLC0415

        self._np = np
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = opts.intra_op_num_threads = 1
        cpu = ["CPUExecutionProvider"]
        self._mel = ort.InferenceSession(str(d / FILES[1]), sess_options=opts, providers=cpu)
        self._emb = ort.InferenceSession(str(d / FILES[2]), sess_options=opts, providers=cpu)
        self._ww = ort.InferenceSession(str(d / FILES[0]), sess_options=opts, providers=cpu)
        self._ww_input = self._ww.get_inputs()[0].name
        self._n_features = int(self._ww.get_inputs()[0].shape[1])   # 16 embeddings
        self.reset()

    def _melspec(self, pcm):
        np = self._np
        out = self._mel.run(None, {"input": pcm.astype(np.float32)[None, :]})[0]
        return np.squeeze(out) / 10 + 2

    def _embed(self, window):
        np = self._np
        return self._emb.run(None, {"input_1": window.astype(np.float32)[None, :, :, None]})[0].squeeze()

    def reset(self) -> None:
        np = self._np
        self._raw: deque[int] = deque(maxlen=16000 * 10)
        self._mels = np.ones((76, 32))
        noise = np.random.randint(-1000, 1000, 16000 * 4).astype(np.int16)   # openWakeWord's warm-up history
        mel = self._melspec(noise)
        self._features = np.vstack([self._embed(mel[i:i + 76]) for i in range(0, mel.shape[0] - 76 + 1, 8)])
        self._scores = 0

    def predict(self, chunk) -> dict[str, float]:
        np = self._np
        self._raw.extend(chunk.tolist())
        self._mels = np.vstack((self._mels, self._melspec(np.array(list(self._raw)[-CHUNK - 160 * 3:], dtype=np.int16))))
        self._mels = self._mels[-970:]
        self._features = np.vstack((self._features, self._embed(self._mels[-76:])))[-120:]
        feats = self._features[-self._n_features:][None].astype(np.float32)
        score = float(self._ww.run(None, {self._ww_input: feats})[0][0][0])
        self._scores += 1
        return {MODEL: score if self._scores > 5 else 0.0}   # openWakeWord zeroes its first 5


def threshold() -> float:
    with contextlib.suppress(ValueError):
        v = float(os.environ.get("JARVIS_WAKE_THRESHOLD", ""))
        if 0.1 <= v <= 0.95:
            return v
    return THRESHOLD


class WakeWord:
    def __init__(self, base: Path | None = None, *, level: float | None = None, model=None, clock=time.monotonic):
        import numpy as np  # noqa: PLC0415

        self._np = np
        self.level = level if level is not None else threshold()
        self.clock = clock
        self._model = model if model is not None else HeyJarvisModel(folder(base))
        self._buf = bytearray()
        self._last = -1e9
        self.score = 0.0
        self.recent: deque[bytes] = deque(maxlen=int(PREROLL_S * 1000 / 20))   # 20 ms frames

    def feed(self, pcm: bytes) -> bool:
        """One 20 ms frame of 16 kHz mono PCM. True once when "hey Jarvis" was just said."""
        self.recent.append(pcm)
        self._buf += pcm
        heard = False
        while len(self._buf) >= CHUNK * 2:
            chunk = self._np.frombuffer(bytes(self._buf[:CHUNK * 2]), dtype=self._np.int16)
            del self._buf[:CHUNK * 2]
            scores = self._model.predict(chunk)
            self.score = float(max(scores.values())) if scores else 0.0
            now = self.clock()
            if self.score >= self.level and now - self._last >= COOLDOWN_S:
                self._last = now
                heard = True
        if heard:
            with contextlib.suppress(Exception):
                self._model.reset()   # a fresh start for the next one
        return heard

    def preroll(self) -> list[bytes]:
        out = list(self.recent)
        self.recent.clear()
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jarvis.voice.wake")
    parser.add_argument("--download", action="store_true", help="fetch the wake-word models")
    parser.add_argument("--test", action="store_true", help="say 'hey Jarvis' and watch the score")
    parser.add_argument("--mic", type=int, help="microphone number")
    args = parser.parse_args(argv)
    if args.download:
        print(f"Wake-word models in {download()}")
        return 0
    if not available():
        print("The wake word isn't set up yet: run the setup again (it downloads the model).")
        return 1
    import sounddevice as sd  # noqa: PLC0415

    wake = WakeWord()
    print(f"Say \"hey Jarvis\" a few times, and some other things too. It fires at {wake.level:.2f}. Ctrl+C to stop.")
    peak, shown = 0.0, time.monotonic()
    with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=320, device=args.mic) as stream:
        while True:
            data, _ = stream.read(320)
            if wake.feed(bytes(data)):
                print(f"  HEARD  (score {wake.score:.2f})", flush=True)
            peak = max(peak, wake.score)
            if time.monotonic() - shown >= 1.0:
                bar = "#" * int(peak * 40)
                print(f"  {peak:4.2f} {bar}", flush=True)
                peak, shown = 0.0, time.monotonic()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
