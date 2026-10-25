"""
Python Desktop SDK for FastAgent Edge.
Provides non-blocking worker threads and Qt (PyQt/PySide) signals
to prevent GUI freezes during local LLM token generation.
"""
import threading
from typing import Any, Callable, Dict, Optional
import requests

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    HAS_PYQT = True
except ImportError:
    try:
        from PySide6.QtCore import QObject, Signal as pyqtSignal
        HAS_PYQT = True
    except ImportError:
        HAS_PYQT = False
        # Fallback dummy class if Qt is not installed
        class QObject:
            pass

        def pyqtSignal(*args, **kwargs):
            return None


class FastAgentDesktopWorker(QObject if HAS_PYQT else object):
    """
    Non-blocking worker for PyQt/PySide desktop applications.
    Emits Qt signals when tokens arrive, when turns finish, and when memory warnings occur.
    """
    if HAS_PYQT:
        token_received = pyqtSignal(str)          # Emitted for each streaming token
        turn_finished = pyqtSignal(dict)           # Emitted with TurnResponse dict
        memory_warning = pyqtSignal(dict)          # Emitted when memory pressure is high
        error_occurred = pyqtSignal(str)           # Emitted on exception

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8085",
        on_token: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        if HAS_PYQT:
            super().__init__()
        self.endpoint = endpoint
        self.on_token = on_token
        self.on_finished = on_finished
        self.on_error = on_error
        self._active_thread: Optional[threading.Thread] = None

    def stream_async(
        self,
        prompt: str,
        session_id: str = "default",
        grammar: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ):
        """Dispatches streaming request to background thread."""
        def _run():
            try:
                url = f"{self.endpoint}/v1/chat/completions"
                payload = {
                    "prompt": prompt,
                    "session_id": session_id,
                    "stream": True,
                    "grammar": grammar,
                    "json_schema": json_schema,
                }
                resp = requests.post(url, json=payload, stream=True, timeout=120.0)
                resp.raise_for_status()

                accumulated = []
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        chunk_str = line_str[6:].strip()
                        if chunk_str == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(chunk_str)
                            token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                accumulated.append(token)
                                if HAS_PYQT and hasattr(self, "token_received"):
                                    self.token_received.emit(token)
                                if self.on_token:
                                    self.on_token(token)
                        except Exception:
                            pass

                res_dict = {"output": "".join(accumulated), "session_id": session_id}
                if HAS_PYQT and hasattr(self, "turn_finished"):
                    self.turn_finished.emit(res_dict)
                if self.on_finished:
                    self.on_finished(res_dict)

            except Exception as e:
                err_msg = str(e)
                if HAS_PYQT and hasattr(self, "error_occurred"):
                    self.error_occurred.emit(err_msg)
                if self.on_error:
                    self.on_error(err_msg)

        self._active_thread = threading.Thread(target=_run, daemon=True)
        self._active_thread.start()
