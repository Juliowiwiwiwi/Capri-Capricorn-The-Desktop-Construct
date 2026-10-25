"""
chat_window.py
The cyberpunk terminal chat panel.
Matches the aesthetic from the reference image:
  - Dark background with neon cyan/yellow borders
  - Monospace font throughout
  - Status indicator (CONNECTED / OFFLINE / THINKING)
  - Scrollable log pane on top, input bar on bottom
  - Toggled by clicking Capri
"""

from PySide6.QtCore    import Qt, QTimer, Signal, QObject, QMetaObject, Q_ARG
from PySide6.QtGui     import QColor, QTextCursor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QLabel, QPushButton,
    QApplication, QSizePolicy, QFrame,
)

# ── palette ───────────────────────────────────────────────────────────
C_BG        = "#08080f"
C_BORDER    = "#00e5ff"       # neon cyan
C_ACCENT    = "#f5e642"       # yellow
C_PINK      = "#ff2d78"       # hot pink
C_TEXT      = "#c8f0f5"       # pale cyan text
C_DIM       = "#3a5a60"       # dimmed / secondary
C_GREEN     = "#39ff14"       # connected green
C_USER      = "#f5e642"       # user line colour
C_CAPRI     = "#00e5ff"       # capri line colour

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
    """Lets background threads safely update the Qt UI."""
    append_token  = Signal(str)
    append_error  = Signal(str)
    set_status    = Signal(str, str)   # (text, colour)
    generation_done = Signal()


class ChatWindow(QWidget):
    """
    The terminal-style chat panel.
    Opened/closed by CapriWindow. Communicates with OllamaClient.
    """

    def __init__(self, ai_client, character_controller, parent_window):
        super().__init__()
        self._ai       = ai_client
        self._ctrl     = character_controller
        self._parent   = parent_window
        self._thinking = False
        self._bridge   = _SignalBridge()

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._check_connection()

    # ── window setup ─────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("ChatPanel")
        self.setStyleSheet(WINDOW_STYLE)
        self.setFixedSize(420, 520)
        self._reposition()

    def _reposition(self):
        """Place chat window above/beside Capri."""
        if self._parent:
            p = self._parent.pos()
            screen = QApplication.primaryScreen().geometry()
            x = p.x() - self.width() - 10
            if x < 0:
                x = p.x() + self._parent.width() + 10
            y = p.y() - self.height() + self._parent.height()
            y = max(0, min(y, screen.height() - self.height()))
            self.move(x, y)

    # ── UI construction ───────────────────────────────────────────────

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

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_DIM};
                border: none;
                font-size: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ color: {C_PINK}; }}
        """)
        close_btn.clicked.connect(self.hide)

        lay.addWidget(title)
        lay.addStretch()
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
        # Neutral UI status only; Capri's actual personality comes from the Modelfile.
        self._append_system("LOCAL SESSION READY — type a message to begin.")
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

    # ── signals ───────────────────────────────────────────────────────

    def _connect_signals(self):
        self._bridge.append_token.connect(self._on_token)
        self._bridge.append_error.connect(self._on_error)
        self._bridge.set_status.connect(self._set_status)
        self._bridge.generation_done.connect(self._on_generation_done)

    # ── sending & receiving ───────────────────────────────────────────

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._thinking:
            return

        self._input.clear()
        self._append_user(text)
        self._start_thinking()

        self._ai.send(
            text,
            on_token=lambda chunk: self._bridge.append_token.emit(chunk),
            on_done=lambda _full: self._bridge.generation_done.emit(),
            on_error=lambda msg: (
                self._bridge.append_error.emit(msg),
                self._bridge.generation_done.emit(),
            ),
        )

    def _start_thinking(self):
        self._thinking = True
        self._input.setEnabled(False)
        self._bridge.set_status.emit("THINKING", C_PINK)
        # Insert Capri's name prefix — tokens will append after it
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_CAPRI}; font-family:{FONT_FAMILY}; font-size:{FONT_SIZE}px;">'
            f'<br>CAPRI &gt;&nbsp;</span>'
        )
        self._log.moveCursor(QTextCursor.End)
        self._capri_line_open = True

    def _on_token(self, chunk: str):
        """Append a streamed token to the current Capri line."""
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(chunk)
        self._log.moveCursor(QTextCursor.End)

    def _on_error(self, message: str):
        """Display connection/API errors as system messages, not Capri dialogue."""
        escaped = (message.replace("&", "&amp;")
                          .replace("<", "&lt;")
                          .replace(">", "&gt;"))
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<br><span style="color:{C_PINK}; font-family:{FONT_FAMILY}; '
            f'font-size:{FONT_SIZE}px;">{escaped}</span><br>'
        )
        self._log.moveCursor(QTextCursor.End)
        self._set_status("OFFLINE", C_PINK)

    def _on_generation_done(self):
        self._thinking = False
        self._input.setEnabled(True)
        self._input.setFocus()
        self._log.insertHtml("<br>")
        self._log.moveCursor(QTextCursor.End)
        self._set_status("CONNECTED", C_GREEN)
        # Wake Capri's expression back to idle
        from capri.character.controller import CapriState
        self._ctrl.set_state(CapriState.IDLE)

    # ── log helpers ───────────────────────────────────────────────────

    def _append_user(self, text: str):
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_USER}; font-family:{FONT_FAMILY}; font-size:{FONT_SIZE}px;">'
            f'<br>&gt; {escaped}<br></span>'
        )
        self._log.moveCursor(QTextCursor.End)

    def _append_capri(self, text: str):
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_CAPRI}; '
            f'font-family:{FONT_FAMILY}; font-size:{FONT_SIZE}px;">'
            f'<br>CAPRI &gt;&nbsp;</span>'
            f'<span style="color:{C_TEXT}; '
            f'font-family:{FONT_FAMILY}; font-size:{FONT_SIZE}px; '
            f'white-space: pre-wrap;">'
            f'{escaped}<br></span>'
        )
        self._log.moveCursor(QTextCursor.End)


    def _append_system(self, text: str):
        """Dimmed grey system/status messages — not Capri dialogue."""
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.moveCursor(QTextCursor.End)
        self._log.insertHtml(
            f'<span style="color:{C_DIM}; font-family:{FONT_FAMILY}; font-size:{FONT_SIZE}px;">'
            f'<br>// {escaped}<br></span>'
        )
        self._log.moveCursor(QTextCursor.End)
    # ── status indicator ──────────────────────────────────────────────

    def _set_status(self, text: str, colour: str):
        self._status_dot.setStyleSheet(f"color: {colour}; font-size: 14px;")
        self._status_label.setStyleSheet(
            f"color: {colour}; font-size: 10px; font-family: {FONT_FAMILY};"
        )
        self._status_label.setText(text)

    def _check_connection(self):
        """Ping Ollama and update the status dot."""
        def _ping():
            ok = self._ai.is_connected()
            if ok:
                self._bridge.set_status.emit("CONNECTED", C_GREEN)
            else:
                self._bridge.set_status.emit("OFFLINE", C_PINK)
        import threading
        threading.Thread(target=_ping, daemon=True).start()

    # ── show override — reposition each time ─────────────────────────

    def showEvent(self, event):
        self._reposition()
        self._input.setFocus()
        super().showEvent(event)