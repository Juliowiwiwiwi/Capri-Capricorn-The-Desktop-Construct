"""
controller.py
Manages Capri's animation states and which image is displayed.
Add more states here as you get more artwork.
"""

import os
from enum import Enum, auto


class CapriState(Enum):
    IDLE     = auto()
    HAPPY    = auto()
    BLINK    = auto()
    SLEEPING = auto()


# Maps each state to a filename inside assets/character/
STATE_IMAGES = {
    CapriState.IDLE:     "capri_idle.png",
    CapriState.HAPPY:    "capri_happy.png",
    CapriState.BLINK:    "capri_blink.png",
    CapriState.SLEEPING: "capri_sleeping.png",
}

# Fallback order: if a file is missing, try these states instead
FALLBACK_ORDER = [
    CapriState.IDLE,
    CapriState.BLINK,
    CapriState.HAPPY,
    CapriState.SLEEPING,
]


class CharacterController:
    """
    Tracks Capri's current state and resolves
    the correct image path for the window to display.
    """

    def __init__(self, assets_dir: str):
        """
        assets_dir: absolute path to the assets/character/ folder
        """
        self.assets_dir = assets_dir
        self._state = CapriState.IDLE
        self._on_change = None           # callback the window registers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state: CapriState) -> None:
        """Change Capri's state and notify the window."""
        if state != self._state:
            self._state = state
            if self._on_change:
                self._on_change(self.current_image_path())

    def current_state(self) -> CapriState:
        return self._state

    def current_image_path(self) -> str:
        """
        Returns the path to the image for the current state.
        Falls back gracefully if the file doesn't exist yet.
        """
        path = self._resolve_path(self._state)
        if path:
            return path

        # Try fallbacks
        for fallback in FALLBACK_ORDER:
            path = self._resolve_path(fallback)
            if path:
                print(f"[CharacterController] Missing image for {self._state.name}, "
                      f"falling back to {fallback.name}")
                return path

        # Nothing found — return empty string, window will show placeholder
        print("[CharacterController] WARNING: No character images found in assets/character/")
        return ""

    def register_change_callback(self, fn) -> None:
        """Window calls this so it gets notified when state changes."""
        self._on_change = fn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, state: CapriState) -> str:
        filename = STATE_IMAGES.get(state, "")
        if not filename:
            return ""
        full = os.path.join(self.assets_dir, filename)
        return full if os.path.isfile(full) else ""