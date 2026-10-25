# fast_agent/daemon.py
"""
Headless Edge Agent Daemon for Desktop Applications (Electron, Tauri, Flutter).
Provides REST and Server-Sent Events (SSE) streaming API, parent-process health monitoring,
multi-tab slot caching, memory budget enforcement, and offline license verification.
"""
import atexit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import psutil
import requests

from .core import FastAgent, find_free_port, safe_parse_args
from .grammar_engine import GrammarEngine
from .license_manager import FastAgentLicense, LicenseManager
from .memory_manager import MemoryBudgetManager, MemoryPressureWarning
from .model_catalog import ModelManager
from .slot_manager import SlotCacheManager


def get_runtime_metadata_path() -> Path:
    """Returns path to the runtime discovery lockfile with fallback."""
    candidates = []
    if os.name == "nt":
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            candidates.append(Path(appdata) / "FastAgent")
    candidates.append(Path.home() / ".fastagent")
    candidates.append(Path.cwd() / ".fastagent")

    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base / "daemon.json"
        except (PermissionError, OSError):
            continue

    fallback = Path.cwd() / ".fastagent"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "daemon.json"


class EdgeDaemonHandler(BaseHTTPRequestHandler):
    """HTTP request handler for FastAgent Edge Daemon with SSE streaming."""

    daemon_instance: Any = None  # Reference to FastAgentDaemon

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP logs unless debugging
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-ID")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        daemon = self.daemon_instance

        if path in ("/", "/health", "/v1/status"):
            snapshot = daemon.get_status()
            self._send_json(200, snapshot)

        elif path == "/v1/slots":
            slots = daemon.slot_manager.list_slots()
            self._send_json(200, {"active_slots": slots, "count": len(slots)})

        elif path == "/v1/models":
            catalog = ModelManager.list_catalog()
            local_models = ModelManager.find_local_models()
            self._send_json(200, {
                "active_model": daemon.model_path,
                "local_models": local_models,
                "catalog": catalog,
            })

        elif path == "/v1/license":
            self._send_json(200, daemon.license.to_dict())

        else:
            self._send_json(404, {"error": "Not Found", "path": path})

    def do_POST(self):
        path = self.path.split("?")[0]
        daemon = self.daemon_instance

        # Read JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON body: {e}"})
            return

        try:
            # 1. License activation
            if path == "/v1/license/activate":
                token = body.get("license_key") or body.get("token")
                license_obj = LicenseManager.verify_license(token)
                daemon.license = license_obj
                daemon.slot_manager.max_active_slots = license_obj.max_concurrent_slots
                self._send_json(200, {
                    "status": "activated",
                    "license": license_obj.to_dict(),
                })

            # 2. Slot management
            elif path == "/v1/slots/manage":
                action = body.get("action", "list")
                session_id = body.get("session_id")
                if action == "evict" and session_id:
                    success = daemon.slot_manager.evict_slot(session_id)
                    self._send_json(200, {"evicted": success, "session_id": session_id})
                elif action == "compact":
                    keep = int(body.get("keep_turns", 2))
                    daemon.slot_manager.compact_all_slots(keep_last_n_turns=keep)
                    self._send_json(200, {"status": "compacted", "slots": daemon.slot_manager.list_slots()})
                else:
                    self._send_json(200, {"slots": daemon.slot_manager.list_slots()})

            # 3. Model switching
            elif path == "/v1/models/load":
                model_name = body.get("model")
                if not model_name:
                    self._send_json(400, {"error": "Missing 'model' parameter"})
                    return
                daemon.reload_model(model_name)
                self._send_json(200, {"status": "loaded", "model": daemon.model_path})

            # 4. Turn execution (Single step with slot caching)
            elif path == "/v1/agent/turn":
                prompt = body.get("prompt", "")
                session_id = body.get("session_id", "default")
                grammar = body.get("grammar")
                json_schema = body.get("json_schema")
                max_tokens = int(body.get("max_tokens", 160))
                temperature = float(body.get("temperature", 0.1))

                result = daemon.execute_turn(
                    prompt=prompt,
                    session_id=session_id,
                    grammar=grammar,
                    json_schema=json_schema,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self._send_json(200, result)

            # 5. Autonomous Agent Ask
            elif path == "/v1/agent/ask":
                prompt = body.get("prompt", "")
                session_id = body.get("session_id", "default")
                max_steps = int(body.get("max_steps", 5))
                use_grammar = bool(body.get("use_grammar", False))

                result = daemon.execute_ask(
                    prompt=prompt,
                    session_id=session_id,
                    max_steps=max_steps,
                    use_grammar=use_grammar,
                )
                self._send_json(200, {"result": result, "session_id": session_id})

            # 6. Tool execution (Direct sandboxed invocation)
            elif path == "/v1/agent/tools/execute":
                tool_name = body.get("tool_name")
                args_str = body.get("args", "")
                res = daemon.execute_tool(tool_name, args_str)
                self._send_json(200, {"tool": tool_name, "result": res})

            # 7. OpenAI-compatible /chat/completions with Streaming SSE support
            elif path in ("/v1/chat/completions", "/chat/completions"):
                stream = bool(body.get("stream", False))
                session_id = body.get("session_id") or self.headers.get("X-Session-ID", "default")
                messages = body.get("messages", [])
                grammar = body.get("grammar")
                json_schema = body.get("json_schema")

                # Extract latest user message
                user_msg = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_msg = msg.get("content", "")
                        break
                if not user_msg and "prompt" in body:
                    user_msg = body["prompt"]

                if stream:
                    self._handle_sse_stream(user_msg, session_id, grammar=grammar, json_schema=json_schema)
                else:
                    turn_res = daemon.execute_turn(
                        prompt=user_msg,
                        session_id=session_id,
                        grammar=grammar,
                        json_schema=json_schema,
                    )
                    self._send_json(200, {
                        "id": f"chatcmpl-{int(time.time()*1000)}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "choices": [{
                            "index": 0,
                            "message": {"role": "assistant", "content": turn_res["output"]},
                            "finish_reason": "stop",
                        }],
                        "session_id": session_id,
                        "timings": {"prompt_eval_ms": turn_res["prompt_eval_ms"]},
                    })

            else:
                self._send_json(404, {"error": "Endpoint not found", "path": path})

        except MemoryPressureWarning as mpw:
            self._send_json(503, {"error": "MemoryBudgetExceeded", "message": str(mpw)})
        except Exception as ex:
            self._send_json(500, {"error": "InternalServerError", "message": str(ex)})

    def _handle_sse_stream(
        self,
        prompt: str,
        session_id: str,
        grammar: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ):
        """Streams LLM tokens to desktop app via Server-Sent Events (SSE)."""
        daemon = self.daemon_instance

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

        # Emit initial ping / session event
        init_event = json.dumps({"session_id": session_id, "status": "started"})
        self.wfile.write(f"event: init\ndata: {init_event}\n\n".encode("utf-8"))
        self.wfile.flush()

        try:
            for token_chunk in daemon.stream_turn(prompt, session_id, grammar=grammar, json_schema=json_schema):
                data = json.dumps({
                    "choices": [{"delta": {"content": token_chunk}, "index": 0}],
                })
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()

            # End of stream marker
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as e:
            err_data = json.dumps({"error": str(e)})
            self.wfile.write(f"event: error\ndata: {err_data}\n\n".encode("utf-8"))
            self.wfile.flush()


class FastAgentDaemon:
    """
    Headless Edge Agent Daemon for desktop apps.
    Manages process lifecycles, memory budgets, slot caches, and REST/SSE communication.
    """

    def __init__(
        self,
        model_path: str = "gemma-2b-q4.gguf",
        port: int = 8085,
        memory_budget_mb: Optional[int] = None,
        parent_pid: Optional[int] = None,
        license_key: Optional[str] = None,
        host: str = "127.0.0.1",
    ):
        self.host = host
        self.port = find_free_port(port)
        self.model_path = ModelManager.resolve_model_path(model_path)
        self.parent_pid = parent_pid
        self.license = LicenseManager.verify_license(license_key)

        # Initialize Memory and Slot Managers
        self.memory_manager = MemoryBudgetManager(
            budget_mb=memory_budget_mb,
            on_pressure_callback=self._handle_memory_pressure,
        )
        self.slot_manager = SlotCacheManager(
            max_active_slots=self.license.max_concurrent_slots,
        )

        # Start Underlying FastAgent Core Engine
        self.agent = FastAgent(
            model_path=self.model_path,
            port=find_free_port(self.port + 10),
            auto_port=True,
        )

        # Pin system prompt into slot manager
        self.slot_manager.set_pinned_system_prompt(self.agent._build_system_prompt())

        # Attach memory watchdog to underlying llama-server process if running
        if self.agent.server_process:
            self.memory_manager.attach_engine_process(self.agent.server_process.pid)
        self.memory_manager.start_watchdog()

        # Setup HTTP server
        EdgeDaemonHandler.daemon_instance = self
        self.httpd = ThreadingHTTPServer((self.host, self.port), EdgeDaemonHandler)
        self.server_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Start parent PID watchdog thread if parent_pid was specified
        self._parent_watchdog_thread: Optional[threading.Thread] = None
        if self.parent_pid:
            self._start_parent_watchdog()

        # Register metadata lockfile
        self._write_lockfile()
        atexit.register(self.shutdown)

    def _handle_memory_pressure(self, metrics: Dict[str, Any]):
        """Callback when memory usage is high: compacts inactive slots to prevent OOM."""
        print(f"[FastAgent-Daemon] High Memory Pressure Detected ({metrics['budget_utilization_percent']}%). Compacting slots...")
        self.slot_manager.compact_all_slots(keep_last_n_turns=2)

    def _start_parent_watchdog(self):
        """Monitors parent desktop app PID; self-terminates if parent crashes."""
        def _watch_parent():
            while not self._stop_event.is_set():
                if self.parent_pid and not psutil.pid_exists(self.parent_pid):
                    print(f"[FastAgent-Daemon] Parent process {self.parent_pid} exited. Terminating daemon to free RAM...")
                    self.shutdown()
                    sys.exit(0)
                time.sleep(1.5)

        self._parent_watchdog_thread = threading.Thread(target=_watch_parent, daemon=True)
        self._parent_watchdog_thread.start()

    def _write_lockfile(self):
        """Writes runtime metadata to user cache so desktop apps can discover the daemon."""
        try:
            lockfile = get_runtime_metadata_path()
            data = {
                "pid": os.getpid(),
                "host": self.host,
                "port": self.port,
                "model": self.model_path,
                "memory_budget_mb": self.memory_manager.budget_mb,
                "tier": self.license.tier,
                "created_at": time.time(),
            }
            with open(lockfile, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _remove_lockfile(self):
        try:
            lockfile = get_runtime_metadata_path()
            if lockfile.exists():
                lockfile.unlink()
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic and telemetry status."""
        mem_metrics = self.memory_manager.get_system_snapshot()
        return {
            "status": "ready",
            "host": self.host,
            "port": self.port,
            "engine_endpoint": self.agent.endpoint,
            "model_path": self.model_path,
            "memory": mem_metrics,
            "slots": {
                "active_count": self.slot_manager.active_slot_count(),
                "max_allowed": self.slot_manager.max_active_slots,
                "list": self.slot_manager.list_slots(),
            },
            "license": self.license.to_dict(),
        }

    def reload_model(self, model_name: str):
        """Hot reloads the underlying model."""
        resolved = ModelManager.resolve_model_path(model_name)
        self.agent.shutdown()
        self.model_path = resolved
        self.agent = FastAgent(
            model_path=resolved,
            port=find_free_port(self.port + 10),
            auto_port=True,
        )
        if self.agent.server_process:
            self.memory_manager.attach_engine_process(self.agent.server_process.pid)
        self._write_lockfile()

    def execute_turn(
        self,
        prompt: str,
        session_id: str = "default",
        grammar: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        max_tokens: int = 160,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Runs single turn with slot cache routing and circuit breaker checking."""
        self.memory_manager.check_headroom_or_raise()

        # Check for json_schema or grammar
        active_grammar = grammar
        if json_schema and not active_grammar:
            active_grammar = GrammarEngine.json_schema_to_gbnf(json_schema)

        # Retrieve slot and record user turn
        slot = self.slot_manager.get_or_create_slot(session_id)
        slot.add_user_turn(prompt)

        full_prompt = f"{self.slot_manager.pinned_system_prompt}\n\n" + "\n".join(slot.conversation_history)

        payload: Dict[str, Any] = {
            "prompt": full_prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "cache_prompt": True,
            "stop": ["\nObservation:", "\nUser:"],
        }
        if active_grammar:
            payload["grammar"] = active_grammar
        elif json_schema:
            payload["json_schema"] = json_schema

        resp = requests.post(self.agent.endpoint, json=payload, timeout=60.0)
        resp.raise_for_status()

        data = resp.json()
        output_text = data.get("content", "").strip()
        prompt_eval_ms = round(data.get("timings", {}).get("prompt_ms", 0.0), 2)

        slot.append_agent_turn(output_text, prompt_eval_ms=prompt_eval_ms)

        # Validate structured JSON if requested
        parsed_json = None
        if json_schema:
            _, parsed_json, _ = GrammarEngine.validate_and_parse(output_text, json_schema)

        return {
            "output": output_text,
            "parsed_json": parsed_json,
            "session_id": session_id,
            "prompt_eval_ms": prompt_eval_ms,
            "turn_count": slot.turn_count,
        }

    def stream_turn(
        self,
        prompt: str,
        session_id: str = "default",
        grammar: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        max_tokens: int = 256,
        temperature: float = 0.1,
    ):
        """Generator yielding streaming token chunks from llama-server."""
        self.memory_manager.check_headroom_or_raise()

        active_grammar = grammar
        if json_schema and not active_grammar:
            active_grammar = GrammarEngine.json_schema_to_gbnf(json_schema)

        slot = self.slot_manager.get_or_create_slot(session_id)
        slot.add_user_turn(prompt)

        full_prompt = f"{self.slot_manager.pinned_system_prompt}\n\n" + "\n".join(slot.conversation_history)

        payload: Dict[str, Any] = {
            "prompt": full_prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "cache_prompt": True,
            "stream": True,
            "stop": ["\nObservation:", "\nUser:"],
        }
        if active_grammar:
            payload["grammar"] = active_grammar

        resp = requests.post(self.agent.endpoint, json=payload, stream=True, timeout=120.0)
        resp.raise_for_status()

        accumulated = []
        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                chunk_json = line_str[6:].strip()
                if chunk_json == "[DONE]":
                    break
                try:
                    chunk = json.loads(chunk_json)
                    token = chunk.get("content", "")
                    if token:
                        accumulated.append(token)
                        yield token
                except Exception:
                    pass

        slot.append_agent_turn("".join(accumulated))

    def execute_ask(
        self,
        prompt: str,
        session_id: str = "default",
        max_steps: int = 5,
        use_grammar: bool = False,
    ) -> str:
        """Runs multi-step agent loop in slot context."""
        return self.agent.ask(prompt, max_steps=max_steps, use_grammar=use_grammar)

    def execute_tool(self, tool_name: str, args_str: str) -> str:
        """Runs a tool safely."""
        return self.agent.execute_tool(tool_name, args_str)

    def start(self, blocking: bool = False):
        """Starts the daemon HTTP server."""
        print(f"[FastAgent-Daemon] Serving at http://{self.host}:{self.port} (PID: {os.getpid()})")
        if blocking:
            try:
                self.httpd.serve_forever()
            except KeyboardInterrupt:
                self.shutdown()
        else:
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()

    def shutdown(self):
        """Gracefully shuts down HTTP server and child processes."""
        self._stop_event.set()
        self.memory_manager.stop_watchdog()
        self._remove_lockfile()
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass
        if self.agent:
            self.agent.shutdown()
        print("[FastAgent-Daemon] Daemon terminated cleanly.")
