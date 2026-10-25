"""
main.py  —  Run this to start Capri.
Usage:  python -m capri.main
"""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from capri.character.controller import CharacterController
from capri.desktop.window import CapriWindow


def get_assets_dir() -> str:
    """
    Resolves assets/character/ relative to the project root.
    Works whether you run from the project folder or package it later.
    """
    here = os.path.dirname(os.path.abspath(__file__))          # capri/
    root = os.path.dirname(here)                               # project root
    return os.path.join(root, "assets", "character")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Capri")
    app.setQuitOnLastWindowClosed(True)

    # Optional: set taskbar icon if you have one
    icon_path = os.path.join(get_assets_dir(), "..", "ui", "icon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    assets_dir = get_assets_dir()
    controller = CharacterController(assets_dir)
    window = CapriWindow(controller)
    window.show()

    print("Capri is running. Right-click her to quit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()