"""
chat_window.py — your working version + voice additions only.
Changes marked NEW or CHANGED. Everything else identical to your file.
"""

import threading
from PySide6.QtCore    import Qt, QTimer, Signal, QObject
from PySide6.QtGui     import QColor, QTextCursor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QLabel, QPushButton,
    QApplication, QSizePolicy, QFrame,
)

C_BG        = "#08080f"
C_BORDER    = "#00e5ff"
C_ACCENT    = "#f5e642"
C_PINK      = "#ff2d78"
C_TEXT      = "#c8f0f5"
C_DIM       = "#3a5a60"
C_GREEN     = "#39ff14"
C_USER      = "#f5e642"
C_CAPRI     = "#00e5ff"
C_MIC_LIVE  = "#ff2d78"   # NEW

FONT_FAMILY = "Consolas, Courier New, monospace"
FONT_SIZE   = 11

WINDOW_STYLE = f"""
QWidget#ChatPanel {{
    background: {C_BG};
    border: 2px solid {C_BORDER};
}}
QScrollBar:vertical {{
    background: {C_BG};
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {C_DIM};
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
LOG_STYLE = f"""
QTextEdit {{
    background: {C_BG};
    color: {C_TEXT};
    border: none;
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE}px;
    padding: 8px;
    selection-background-color: {C_DIM};
}}
"""
INPUT_STYLE = f"""
QLineEdit {{
    background: {C_BG};
    color: {C_ACCENT};
    border: none;
    border-top: 1px solid {C_DIM};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE}px;
    padding: 8px 8px 8px 4px;
}}
QLineEdit:focus {{
    border-top: 1px solid {C_BORDER};
}}
"""
HEADER_STYLE = f"""
QWidget#Header {{
    background: {C_BG};
    border-bottom: 1px solid {C_DIM};
}}
QLabel {{
    color: {C_ACCENT};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE}px;
    font-weight: bold;
    background: transparent;
}}
"""


class _SignalBridge(QObject):
    append_token    = Signal(str)
    append_error    = Signal(str)
    set_status      = Signal(str, str)
    generation_done = Signal(str)    # CHANGED: now carries full text for TTS
    set_mic_state   = Signal(bool)   # NEW


class ChatWindow(QWidget):

    def __init__(self, ai_client, character_controller, parent_window,
                 stt=None, tts=None, ptt=None):   # CHANGED: optional voice args
        super().__init__()
        self._ai       = ai_client
        self._ctrl     = character_controller
        self._parent   = parent_window
        self._stt      = stt    # NEW
        self._tts      = tts    # NEW
        self._ptt      = ptt    # NEW
        self._thinking = False
        self._bridge   = _SignalBridge()

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._check_connection()

        if self._ptt:    # NEW
            self._ptt._on_press   = self._ptt_pressed
            self._ptt._on_release = self._ptt_released
            self._ptt.start()

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("ChatPanel")
        self.setStyleSheet(WINDOW_STYLE)
        self.setFixedSize(420, 520)
        self._reposition()

    def _reposition(self):
        if self._parent:
            p = self._parent.pos()
            screen = QApplication.primaryScreen().geometry()
            x = p.x() - self.width() - 10
            if x < 0:
                x = p.x() + self._parent.width() + 10
            y = p.y() - self.height() + self._parent.height()
            y = max(0, min(y, screen.height() - self.height()))
            self.move(x, y)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_header())
        root.addWidget(self._make_log())
        root.addWidget(self._make_divider())
        root.addWidget(self._make_input_bar())

    def _make_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("Header")
        header.setStyleSheet(HEADER_STYLE)
        header.setFixedHeight(32)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(10, 0, 10, 0)

        title = QLabel("CAPRI // TERMINAL")
        title.setStyleSheet(f"color: {C_ACCENT}; font-size: 11px; font-weight: bold;")

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {C_DIM}; font-size: 14px;")

        self._status_label = QLabel("CONNECTING")
        self._status_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")

        # NEW ──────────────────────────────────────────────
        self._mic_label = QLabel("● MIC")
        self._mic_label.setStyleSheet(
            f"color: {C_MIC_LIVE}; font-size: 10px; font-family: {FONT_FAMILY};"
        )
        self._mic_label.setVisible(False)

        self._stop_btn = QPushButton("■ STOP")
        self._stop_btn.setFixedHeight(18)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_PINK};
                border: 1px solid {C_PINK}; font-size: 9px;
                font-family: {FONT_FAMILY}; padding: 0 4px;
            }}
            QPushButton:hover {{ background: {C_PINK}; color: #000; }}
        """)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._stop_speech)
        # ──────────────────────────────────────────────────

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_DIM};
                border: none; font-size: 12px; font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ color: {C_PINK}; }}
        """)
        close_btn.clicked.connect(self.hide)

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(self._mic_label)   # NEW
        lay.addSpacing(6)
        lay.addWidget(self._stop_btn)    # NEW
        lay.addSpacing(6)
        lay.addWidget(self._status_dot)
        lay.addWidget(self._status_label)
        lay.addSpacing(8)
        lay.addWidget(close_btn)
        return header

    def _make_log(self) -> QTextEdit:
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(LOG_STYLE)
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hint = " | hold L-CTRL to speak" if self._ptt else ""   # NEW
        self._append_system(f"LOCAL SESSION READY — type a message to begin{hint}.")
        return self._log

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {C_DIM}; background: {C_DIM}; max-height: 1px;")
        return line

    def _make_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background: {C_BG};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(6)
        prompt = QLabel(">_")
        prompt.setStyleSheet(f"color: {C_BORDER}; font-family: {FONT_FAMILY}; font-size: 13px;")
        self._input = QLineEdit()
        self._input.setStyleSheet(INPUT_STYLE)
        self._input.setPlaceholderText("talk to capri...")
        self._input.returnPressed.connect(self._on_send)
        lay.addWidget(prompt)
        lay.addWidget(self._input)
        return bar

    def _connect_signals(self):
        self._bridge.append_token.connect(self._on_token)
        self._bridge.append_error.connect(self._on_error)
        self._bridge.set_status.connect(self._set_status)
        self._bridge.generation_done.connect(self._on_generation_done)
        self._bridge.set_mic_state.connect(self._on_mic_state_changed)   # NEW

    # ── NEW: PTT ─────────────────────────────────────────────────────

    def _ptt_pressed(self):
        if self._thinking or not self._stt:
            return
        if not self._stt.is_ready():
            self._bridge.append_error.emit("// STT still loading — wait a moment.")
            return
        if self._tts:
            self._tts.stop()
        self._stt.start_recording()
        self._bridge.set_mic_state.emit(True)

    def _ptt_released(self):
        if not self._stt:
            return
        self._bridge.set_mic_state.emit(False)
        text = self._stt.stop_and_transcribe()
        if text:
            self._bridge.append_token.emit("\x00__VOICE__:" + text)
        else:
            self._bridge.append_error.emit("// Nothing heard — try again.")

    # ── send ──────────────────────────────────────────────────────────

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._thinking:
            return
        self._input.clear()
        self._dispatch_message(text)   # CHANGED: extracted to shared method

    def _dispatch_message(self, text: str):   # NEW: shared by text + voice
        self._append_user(text)
        self._start_thinking()
        self._ai.send(
            text,
            on_token=lambda chunk: self._bridge.append_token.emit(chunk),
            on_done=lambda full: self._bridge.generation_done.emit(full),   # CHANGED
            on_error=lambda msg: (
                self._bridge.append_error.emit(msg),
                self._bridge.generation_done.emit(""),
            ),
        )

    def _start_thinking(self):
        self._thinking = True
        self._input.setEnabled(False)
        self._bridge.set_status.emit("THINKING", C_PINK)
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_CAPRI}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px;"><br>CAPRI &gt;&nbsp;</span>'
        )
        self._log.moveCursor(QTextCursor.End)
        self._capri_line_open = True

    def _on_token(self, chunk: str):
        if chunk.startswith("\x00__VOICE__:"):   # NEW: route voice input
            self._dispatch_message(chunk[len("\x00__VOICE__:"):])
            return
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(chunk)
        self._log.moveCursor(QTextCursor.End)

    def _on_error(self, message: str):
        escaped = (message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<br><span style="color:{C_PINK}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px;">{escaped}</span><br>'
        )
        self._log.moveCursor(QTextCursor.End)
        self._set_status("OFFLINE", C_PINK)

    def _on_generation_done(self, full_reply: str):   # CHANGED: receives text
        self._thinking = False
        self._input.setEnabled(True)
        self._input.setFocus()
        self._log.insertHtml("<br>")
        self._log.moveCursor(QTextCursor.End)
        self._set_status("CONNECTED", C_GREEN)
        from capri.character.controller import CapriState
        self._ctrl.set_state(CapriState.IDLE)
        # NEW: speak reply
        if self._tts and full_reply.strip():
            self._stop_btn.setVisible(True)
            self._tts.speak(
                full_reply,
                on_done=lambda: self._bridge.set_mic_state.emit(False),
            )

    def _stop_speech(self):   # NEW
        if self._tts:
            self._tts.stop()
        self._stop_btn.setVisible(False)

    def _on_mic_state_changed(self, is_live: bool):   # NEW
        self._mic_label.setVisible(is_live)
        if not is_live and self._tts and not self._tts.is_speaking():
            self._stop_btn.setVisible(False)

    # ── log helpers (unchanged) ───────────────────────────────────────

    def _append_user(self, text: str):
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_USER}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px;"><br>&gt; {escaped}<br></span>'
        )
        self._log.moveCursor(QTextCursor.End)

    def _append_capri(self, text: str):
        escaped = (text.replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;").replace("\n", "<br>"))
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_CAPRI}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px;"><br>CAPRI &gt;&nbsp;</span>'
            f'<span style="color:{C_TEXT}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px; white-space: pre-wrap;">{escaped}<br></span>'
        )
        self._log.moveCursor(QTextCursor.End)

    def _append_system(self, text: str):
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_DIM}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px;"><br>// {escaped}<br></span>'
        )
        self._log.moveCursor(QTextCursor.End)

    def _set_status(self, text: str, colour: str):
        self._status_dot.setStyleSheet(f"color: {colour}; font-size: 14px;")
        self._status_label.setStyleSheet(
            f"color: {colour}; font-size: 10px; font-family: {FONT_FAMILY};"
        )
        self._status_label.setText(text)

    def _check_connection(self):
        def _ping():
            ok = self._ai.is_connected()
            self._bridge.set_status.emit(
                "CONNECTED" if ok else "OFFLINE",
                C_GREEN if ok else C_PINK,
            )
        threading.Thread(target=_ping, daemon=True).start()

    def showEvent(self, event):
        self._reposition()
        self._input.setFocus()
        super().showEvent(event)

    def keyPressEvent(self, event):   # NEW: ESC stops speech
        if event.key() == Qt.Key_Escape and self._tts:
            self._stop_speech()
        super().keyPressEvent(event)