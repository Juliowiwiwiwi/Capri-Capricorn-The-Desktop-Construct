"""
window.py
The transparent, always-on-top desktop window that displays Capri.

Controls:
  - Left-click + drag  → move Capri around
  - Right-click        → context menu (sleep / wake / quit)
  - Double left-click  → poke (happy reaction)

Blink timer fires every ~4 seconds.
Sleep kicks in after 60 seconds of no interaction.
"""

import random
from pathlib import Path
from PySide6.QtCore  import Qt, QTimer, QPoint, QSize
from PySide6.QtGui   import QPixmap, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout,
    QMenu, QApplication, QSizePolicy
)

from capri.character.controller import CharacterController, CapriState


# ── tuneable constants ────────────────────────────────────────────────
WINDOW_SIZE       = QSize(200, 200)   # px — adjust to your art size
BLINK_INTERVAL_MS = 4_000            # how often she blinks (ms)
BLINK_HOLD_MS     = 150              # how long blink image shows
HAPPY_HOLD_MS     = 1_200            # how long happy expression stays
SLEEP_AFTER_MS    = 60_000           # idle-to-sleep timeout (1 min)
# ─────────────────────────────────────────────────────────────────────


class CapriWindow(QWidget):
    """
    Borderless, transparent, always-on-top window.
    Owns the animation timers and delegates state to CharacterController.
    """

    def __init__(self, controller: CharacterController):
        super().__init__()
        self.controller = controller
        self._drag_start_pos: QPoint | None = None
        self._press_global_pos: QPoint | None = None
        self._chat_window = None
        self._is_sleeping = False
        self._idle_frames = []

        for filename in (
            "capri_idle1.png",
            "capri_idle2.png",
            "capri_idle3.png",
        ):
            image_path = Path(self.controller.assets_dir) / filename
            pixmap = QPixmap(str(image_path))

            if not pixmap.isNull():
                self._idle_frames.append(pixmap)
            else:
                print(f"[CapriWindow] Could not load idle frame: {image_path}")

        self._idle_frame_index = 0

        self._setup_window()
        self._setup_ui()
        self._setup_timers()

        # Tell controller to call our image-update method on state change
        self.controller.register_change_callback(self._update_image)

        # Show initial image
        self._update_image(self.controller.current_image_path())

    def set_chat_window(self, chat_window) -> None:
        """Attach the chat panel created by main.py."""
        self._chat_window = chat_window

    def _toggle_chat(self) -> None:
        """Show or hide the chat panel when Capri is clicked."""
        if self._chat_window is None:
            return
        if self._chat_window.isVisible():
            self._chat_window.hide()
        else:
            self._chat_window.show()
            self._chat_window.raise_()
            self._chat_window.activateWindow()
        self._reset_sleep_timer()

    # ── window setup ─────────────────────────────────────────────────

    def _setup_window(self) -> None:
        """Configure the frameless transparent always-on-top window."""
        self.setWindowFlags(
            Qt.FramelessWindowHint        |
            Qt.WindowStaysOnTopHint       |
            Qt.Tool                        # hides from taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFixedSize(WINDOW_SIZE)

        # Start bottom-right of primary screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.width()  - WINDOW_SIZE.width()  - 40,
            screen.height() - WINDOW_SIZE.height() - 60,
        )

    def _setup_ui(self) -> None:
        """Create the image label that fills the window."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self.image_label)

    def _setup_timers(self) -> None:
        """Set up blink and sleep timers."""
        # Blink timer — fires every BLINK_INTERVAL_MS (+/- random jitter)
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._do_blink)
        self._schedule_next_blink()

        # Blink-reset timer — returns to IDLE after short hold
        self._blink_reset = QTimer(self)
        self._blink_reset.setSingleShot(True)
        self._blink_reset.timeout.connect(self._end_blink)

        # Happy-reset timer — returns to IDLE after happy expression
        self._happy_reset = QTimer(self)
        self._happy_reset.setSingleShot(True)
        self._happy_reset.timeout.connect(self._end_happy)

        # Sleep timer — triggers sleep after prolonged inactivity
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._go_to_sleep)
        self._sleep_timer.start(SLEEP_AFTER_MS)

        # Idle animation — 3-frame loop
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._animate_idle)
        self._idle_timer.start(150)  # ~6.7 frame updates per second

    # ── image display ─────────────────────────────────────────────────
    def _update_image(self, path: str) -> None:
        """Load and display the correct image for Capri's current state."""

        # Use the first idle animation frame whenever Capri returns to idle
        if (
            self.controller.current_state() == CapriState.IDLE
            and self._idle_frames
        ):
            self._idle_frame_index = 0
            pixmap = self._idle_frames[0].scaled(
                WINDOW_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(pixmap)
            return

        # Display the normal image for other states: happy, blink, sleeping
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    WINDOW_SIZE,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.image_label.setPixmap(pixmap)
                return

        # No image found — draw the placeholder
        self._draw_placeholder()

    def _draw_placeholder(self) -> None:
        """Drawn when art files aren't present yet."""
        placeholder = QPixmap(WINDOW_SIZE)
        placeholder.fill(QColor(0, 0, 0, 0))   # transparent

        painter = QPainter(placeholder)
        painter.setRenderHint(QPainter.Antialiasing)

        # Neon circle body
        painter.setPen(QPen(QColor("#ff2d78"), 3))
        painter.setBrush(QColor(20, 10, 30, 220))
        painter.drawEllipse(40, 40, 120, 120)

        # Eyes
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#39ff14"))
        painter.drawEllipse(70,  85, 22, 22)
        painter.drawEllipse(108, 85, 22, 22)

        # Label
        painter.setPen(QColor("#ff2d78"))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.drawText(0, 175, WINDOW_SIZE.width(), 20,
                         Qt.AlignHCenter, "CAPRI  [ no art ]")
        painter.end()

        self.image_label.setPixmap(placeholder)

    # ── animation helpers ─────────────────────────────────────────────
    def _animate_idle(self) -> None:
        """Cycle idle frames only while Capri is idle."""
        if self._is_sleeping:
            return

        if self.controller.current_state() != CapriState.IDLE:
            return

        if not self._idle_frames:
            return

        self._idle_frame_index = (
            self._idle_frame_index + 1
        ) % len(self._idle_frames)

        pixmap = self._idle_frames[self._idle_frame_index].scaled(
            WINDOW_SIZE,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.image_label.setPixmap(pixmap)

    def _schedule_next_blink(self) -> None:
        jitter = random.randint(-800, 800)
        self._blink_timer.start(BLINK_INTERVAL_MS + jitter)

    def _do_blink(self) -> None:
        if self._is_sleeping:
            return
        self.controller.set_state(CapriState.BLINK)
        self._blink_reset.start(BLINK_HOLD_MS)
        self._schedule_next_blink()

    def _end_blink(self) -> None:
        if self.controller.current_state() == CapriState.BLINK:
            self.controller.set_state(CapriState.IDLE)

    def _end_happy(self) -> None:
        if self.controller.current_state() == CapriState.HAPPY:
            self.controller.set_state(CapriState.IDLE)

    def _go_to_sleep(self) -> None:
        self._is_sleeping = True
        self._blink_timer.stop()
        self.controller.set_state(CapriState.SLEEPING)

    def _wake_up(self) -> None:
        self._is_sleeping = False
        self.controller.set_state(CapriState.HAPPY)
        self._happy_reset.start(HAPPY_HOLD_MS)
        self._schedule_next_blink()
        self._reset_sleep_timer()

    def _reset_sleep_timer(self) -> None:
        self._sleep_timer.start(SLEEP_AFTER_MS)

    # ── mouse interactions ────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_global_pos = event.globalPosition().toPoint()
            self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
            if self._is_sleeping:
                self._wake_up()
            else:
                self._reset_sleep_timer()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            release_pos = event.globalPosition().toPoint()
            was_click = (
                self._press_global_pos is not None
                and (release_pos - self._press_global_pos).manhattanLength()
                    < QApplication.startDragDistance()
            )
            self._drag_start_pos = None
            self._press_global_pos = None
            if was_click and not self._is_sleeping:
                self._toggle_chat()

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click = poke = happy reaction."""
        if event.button() == Qt.LeftButton and not self._is_sleeping:
            self.controller.set_state(CapriState.HAPPY)
            self._happy_reset.start(HAPPY_HOLD_MS)
            self._reset_sleep_timer()

    def contextMenuEvent(self, event) -> None:
        """Right-click menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #0d0d1a;
                border: 1px solid #ff2d78;
                color: #e0e0e0;
                font-family: Consolas;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item:selected { background: #ff2d78; color: #000; }
        """)

        if self._is_sleeping:
            wake = menu.addAction("⚡  Wake Capri")
            wake.triggered.connect(self._wake_up)
        else:
            sleep = menu.addAction("💤  Sleep")
            sleep.triggered.connect(self._go_to_sleep)

        menu.addSeparator()
        quit_action = menu.addAction("✕  Quit")
        quit_action.triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    # ── Qt paint override — keep background transparent ───────────────

    def paintEvent(self, event) -> None:
        """Required to keep the window properly transparent."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        super().paintEvent(event)