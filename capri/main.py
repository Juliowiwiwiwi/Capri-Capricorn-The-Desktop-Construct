"""
main.py — your working version + voice loading.
Only change: load_voice_components() added, passed to ChatWindow.
window.py and controller.py are NOT touched.
"""

import sys
import os
from PySide6.QtWidgets import QApplication

from capri.character.controller import CharacterController
from capri.desktop.window       import CapriWindow
from capri.desktop.chat_window  import ChatWindow
from capri.ai.model_client      import OllamaClient


def get_assets_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    return os.path.join(root, "assets", "character")


def load_voice_components():
    """
    Try to load STT / TTS / PTT.
    If anything is missing (pip packages, piper binary, voice model),
    prints a clear message and returns (None, None, None).
    Capri then runs in text-only mode — nothing breaks.
    """
    try:
        from capri.voice.speech_to_text import SpeechToText
        from capri.voice.text_to_speech import TextToSpeech
        from capri.voice.ptt            import PushToTalk

        tts = TextToSpeech()
        if not tts.is_available():
            print("[Voice] Piper exe or voice model not found.")
            print("        Check PIPER_EXE and VOICE_MODEL in capri/voice/text_to_speech.py")
            print("[Voice] Running text-only.")
            return None, None, None

        stt = SpeechToText()
        ptt = PushToTalk(on_press=lambda: None, on_release=lambda: None)
        print("[Voice] Loaded. Hold LEFT CTRL to speak.")
        return stt, tts, ptt

    except ImportError as e:
        print(f"[Voice] Missing package: {e}")
        print("        pip install faster-whisper sounddevice soundfile pynput")
        print("[Voice] Running text-only.")
        return None, None, None


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Capri")
    app.setQuitOnLastWindowClosed(False)

    assets_dir = get_assets_dir()
    controller = CharacterController(assets_dir)
    ai_client  = OllamaClient()

    stt, tts, ptt = load_voice_components()

    capri_win = CapriWindow(controller)
    chat_win  = ChatWindow(
        ai_client, controller, capri_win,
        stt=stt, tts=tts, ptt=ptt,
    )

    capri_win.set_chat_window(chat_win)
    capri_win.show()

    print("Capri running. Click her to open chat. Right-click to quit.")
    if ptt:
        print("Hold LEFT CTRL anywhere to speak.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()