"""
text_to_speech.py
Speaks text using Piper TTS (local binary, no cloud).

My layout :
    C:/piper_windows_amd64/piper/piper.exe
    C:/piper_windows_amd64/piper/espeak-ng-data/voices/en_US-libritts-high.onnx
    C:/piper_windows_amd64/piper/espeak-ng-data/voices/en_US-libritts-high.onnx.json

If your paths differ, edit PIPER_EXE and VOICE_MODEL below.
"""

import subprocess
import threading
import tempfile
import os
import sounddevice as sd
import soundfile as sf

# ── edit these if your paths differ ──────────────────────────────────
PIPER_EXE   = r"C:\piper_windows_amd64\piper\piper.exe"
VOICE_MODEL = r"C:\piper_windows_amd64\piper\espeak-ng-data\voices\en_US-libritts-high.onnx"
# ─────────────────────────────────────────────────────────────────────


class TextToSpeech:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop   = threading.Event()
        self._lock   = threading.Lock()

    def speak(self, text: str, on_done: callable = None) -> None:
        """Speak text in background. Interrupts anything currently playing."""
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(text, on_done), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Interrupt speech immediately."""
        self._stop.set()
        sd.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def is_speaking(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_available(self) -> bool:
        return os.path.isfile(PIPER_EXE) and os.path.isfile(VOICE_MODEL)

    def _run(self, text: str, on_done: callable) -> None:
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()

            proc = subprocess.run(
                [PIPER_EXE, "--model", VOICE_MODEL, "--output_file", tmp.name],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if proc.returncode != 0:
                print(f"[TTS] Piper error: {proc.stderr.decode()}")
                return

            if self._stop.is_set():
                return

            data, sr = sf.read(tmp.name)
            sd.play(data, sr)

            # Poll until done or stopped
            while sd.get_stream().active:
                if self._stop.is_set():
                    sd.stop()
                    return
                threading.Event().wait(0.05)

            sd.wait()

        except subprocess.TimeoutExpired:
            print("[TTS] Piper timed out.")
        except Exception as e:
            print(f"[TTS] Error: {e}")
        finally:
            if tmp and os.path.exists(tmp.name):
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
            if on_done and not self._stop.is_set():
                on_done()