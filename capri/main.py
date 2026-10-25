"""
main.py  —  Phase 2 entry point
Run: python -m capri.main
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


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Capri")
    app.setQuitOnLastWindowClosed(False)   # chat window closing won't kill the app

    assets_dir = get_assets_dir()

    # Build components
    controller  = CharacterController(assets_dir)
    ai_client   = OllamaClient()
    capri_win   = CapriWindow(controller)
    chat_win    = ChatWindow(ai_client, controller, capri_win)

    # Wire chat window into Capri window
    capri_win.set_chat_window(chat_win)

    capri_win.show()

    print("Capri running.")
    print("Click her to open chat. Right-click to quit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()