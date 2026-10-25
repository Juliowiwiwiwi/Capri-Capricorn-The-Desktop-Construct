"""
speech_to_text.py
Push-to-talk speech recognition using faster-whisper.
Runs on CPU so it doesn't compete with Gemma for VRAM.
"""

import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE  = 16_000
CHANNELS     = 1
MODEL_SIZE   = "base"    # swap to "tiny" if CPU is struggling
COMPUTE_TYPE = "int8"
DEVICE       = "cpu"     # keep off GPU — Gemma needs the VRAM
MIN_SECONDS  = 0.3
SILENCE_DB   = -40


class SpeechToText:
    def __init__(self):
        self._model  = None
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock   = threading.Lock()
        self._stream = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def is_ready(self) -> bool:
        return self._model is not None

    def start_recording(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._recording = True
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop_and_transcribe(self) -> str:
        with self._lock:
            self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            return ""
        audio = np.concatenate(self._frames, axis=0).flatten()
        if len(audio) < SAMPLE_RATE * MIN_SECONDS:
            return ""
        rms_db = 20 * np.log10(np.sqrt(np.mean(audio ** 2)) + 1e-9)
        if rms_db < SILENCE_DB:
            print(f"[STT] Too quiet ({rms_db:.1f} dB), skipping.")
            return ""
        return self._transcribe(audio)

    def _load_model(self) -> None:
        print(f"[STT] Loading Whisper {MODEL_SIZE}...")
        self._model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("[STT] Whisper ready.")

    def _audio_callback(self, indata, frames, time, status) -> None:
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            return ""
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if text:
            print(f"[STT] Heard: {text!r}")
        return text