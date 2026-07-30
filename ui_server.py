"""
Local demo UI for the Institutional Memory Agent.

Serves a single page that shows the session 1 vs session 2 answers side by
side, a diff between them, the contents of the memory store, and buttons to
run create_agent.py / run_session_1.py / run_session_2.py.

Stdlib only — no extra dependencies.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python ui_server.py            # then open http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from difflib import unified_diff
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "ui"
OUTPUT_DIR = ROOT / "outputs"

HOST = "127.0.0.1"
PORT = int(os.environ.get("UI_PORT", "8765"))

# Only these scripts can ever be launched from the UI.
SCRIPTS: dict[str, str] = {
    "create_agent": "create_agent.py",
    "session_1": "run_session_1.py",
    "session_2": "run_session_2.py",
}

STATIC_FILES: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class JobRunner:
    """Runs one allowlisted script at a time and buffers its output."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.key: str | None = None
        self.lines: list[str] = []
        self.running = False
        self.exit_code: int | None = None

    def start(self, key: str) -> tuple[bool, str]:
        script = SCRIPTS.get(key)
        if script is None:
            return False, f"Unknown script: {key}"

        with self._lock:
            if self.running:
                return False, f"{self.key} is still running."
            self.key = key
            self.lines = [f"$ python {script}"]
            self.running = True
            self.exit_code = None
            self._thread = threading.Thread(
                target=self._run, args=(script,), daemon=True
            )
            self._thread.start()

        return True, f"Started {script}"

    def _run(self, script: str) -> None:
        try:
            process = subprocess.Popen(
                [sys.executable, "-u", script],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                with self._lock:
                    self.lines.append(line.rstrip("\n"))
            code = process.wait()
        except Exception as exc:  # surface failures in the UI log
            with self._lock:
                self.lines.append(f"[runner error] {exc}")
            code = -1

        with self._lock:
            self.exit_code = code
            self.running = False
            self.lines.append(f"[exit code {code}]")

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "key": self.key,
                "running": self.running,
                "exitCode": self.exit_code,
                "lines": list(self.lines[-500:]),
            }


JOB = JobRunner()


def read_output(name: str) -> str:
    path = OUTPUT_DIR / name
    if not path.exists():
        return ""
    return path.read_text(errors="replace")


def read_payload(name: str) -> dict:
    """Load the structured citation payload written by the session scripts."""
    path = OUTPUT_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(errors="replace"))
    except json.JSONDecodeError:
        return {}


def build_diff(left: str, right: str) -> str:
    if not left or not right:
        return ""
    return "\n".join(
        unified_diff(
            left.splitlines(),
            right.splitlines(),
            fromfile="session1.txt",
            tofile="session2.txt",
            lineterm="",
        )
    )


def read_id(name: str) -> str:
    path = ROOT / name
    return path.read_text().strip() if path.exists() else ""


def collect_state() -> dict:
    session1 = read_output("session1.txt")
    session2 = read_output("session2.txt")
    payload1 = read_payload("session1.json")
    payload2 = read_payload("session2.json")
    return {
        "session1": session1,
        "session2": session2,
        "diff": build_diff(session1, session2),
        "citations1": payload1.get("citations", []),
        "citations2": payload2.get("citations", []),
        "apiKeyPresent": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "ids": {
            "agent": read_id(".agent_id"),
            "environment": read_id(".environment_id"),
            "memoryStore": read_id(".memory_store_id"),
        },
        "job": JOB.snapshot(),
    }


def collect_memories() -> dict:
    """Read the memory store the same way inspect_memory.py does."""
    store_id = read_id(".memory_store_id")
    if not store_id:
        return {"error": "No .memory_store_id yet — run create_agent.py first."}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY is not set in this server's environment."}

    try:
        from anthropic import Anthropic

        client = Anthropic()
        page = client.beta.memory_stores.memories.list(store_id, path_prefix="/")
        memories = []
        for item in sorted(page.data, key=lambda entry: entry.path):
            if item.type != "memory":
                memories.append({"path": item.path, "isDir": True, "content": ""})
                continue
            retrieved = client.beta.memory_stores.memories.retrieve(
                item.id, memory_store_id=store_id
            )
            memories.append(
                {
                    "path": item.path,
                    "isDir": False,
                    "content": retrieved.content or "",
                }
            )
        return {"storeId": store_id, "memories": memories}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "MemoryAgentUI/1.0"

    def log_message(self, fmt: str, *args) -> None:
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[self.path]
            path = UI_DIR / filename
            if not path.exists():
                self.send_error(404, "UI asset missing")
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/state":
            self._send_json(collect_state())
            return

        if self.path == "/api/job":
            self._send_json(JOB.snapshot())
            return

        if self.path == "/api/memory":
            self._send_json(collect_memories())
            return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/run":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send_json({"ok": False, "message": "Invalid JSON body."}, 400)
            return

        started, message = JOB.start(str(payload.get("script", "")))
        self._send_json({"ok": started, "message": message}, 200 if started else 409)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Memory agent UI running at http://{HOST}:{PORT}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Warning: ANTHROPIC_API_KEY not set — the run buttons will fail.")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
