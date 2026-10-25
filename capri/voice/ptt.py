"""
ptt.py
Global push-to-talk — hold LEFT CTRL to record, release to send.
Works even when the chat window doesn't have focus.

Install: pip install pynput
Change PTT_KEY below if you want a different key.
"""

import threading
from pynput import keyboard
from typing import Callable

PTT_KEY = keyboard.Key.ctrl_l   # LEFT CTRL
# Alternatives:
#   keyboard.Key.alt_l
#   keyboard.KeyCode.from_char('v')


class PushToTalk:
    def __init__(self, on_press: Callable, on_release: Callable):
        self._on_press   = on_press
        self._on_release = on_release
        self._held       = False
        self._listener   = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.daemon = True
        self._listener.start()
        print("[PTT] Ready — hold LEFT CTRL to speak.")

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()

    def _handle_press(self, key) -> None:
        if key == PTT_KEY and not self._held:
            self._held = True
            threading.Thread(target=self._on_press, daemon=True).start()

    def _handle_release(self, key) -> None:
        if key == PTT_KEY and self._held:
            self._held = False
            threading.Thread(target=self._on_release, daemon=True).start()