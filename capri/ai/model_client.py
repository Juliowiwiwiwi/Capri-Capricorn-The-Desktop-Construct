"""
model_client.py
Talks to Ollama running locally.
Runs inference in a background thread so the UI never freezes.
"""

import json
import urllib.request
import urllib.error
import threading
from typing import Callable


OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL_NAME   = "capri:latest"       # custom model built from your Modelfile

# Capri’s personality is defined in the Ollama Modelfile.
# Do not add a second SYSTEM_PROMPT here.



class OllamaClient:
    """
    Sends messages to Ollama and streams the reply back
    via a callback so the UI can update token-by-token.
    """

    def __init__(self):
        self._history: list[dict] = []      # full conversation history
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────

    def send(
        self,
        user_message: str,
        on_token: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Non-blocking. Spawns a thread to call Ollama.

        on_token(chunk)  — called for each streamed token
        on_done(full)    — called when generation is complete
        on_error(msg)    — called if something goes wrong
        """
        thread = threading.Thread(
            target=self._stream,
            args=(user_message, on_token, on_done, on_error),
            daemon=True,
        )
        thread.start()

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()

    def is_connected(self) -> bool:
        """Quick ping to see if Ollama is running."""
        try:
            req = urllib.request.urlopen(
                "http://localhost:11434/api/tags", timeout=2
            )
            return req.status == 200
        except Exception:
            return False

    # ── Internal ──────────────────────────────────────────────────────

    def _stream(self, user_message, on_token, on_done, on_error):
        with self._lock:
            messages = list(self._history) + [
                {"role": "user", "content": user_message}
            ]

        payload = json.dumps({
            "model":    MODEL_NAME,
            "messages": messages,
            "stream":   True,
        }).encode()

        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            full_reply = ""

            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw_line in resp:
                    line = raw_line.decode().strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        full_reply += chunk
                        on_token(chunk)

                    if obj.get("done"):
                        break

            with self._lock:
                self._history.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": full_reply},
                ])

            on_done(full_reply)

        except urllib.error.URLError:
            on_error("// CONNECTION LOST — is Ollama running?")
        except Exception as e:
            on_error(f"// ERROR: {e}")