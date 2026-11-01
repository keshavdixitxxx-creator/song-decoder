"""Local HTTP receiver that animates visible video captions in a terminal.

Run this in the VS Code terminal. The browser extension sends only newly
visible HTML5 caption text to the loopback-only server (127.0.0.1).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = "127.0.0.1"
PORT = 39471
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
COLORS = ("\033[38;5;213m", "\033[38;5;117m", "\033[38;5;221m", "\033[38;5;158m", "\033[38;5;183m")


def animate_words(text: str, color_index: int, duration: float) -> None:
    words = text.split()
    if not words:
        return
    color = COLORS[color_index % len(COLORS)]
    pause = min(duration / max(1, len(words)), 0.065)
    for word in words:
        sys.stdout.write(f"{BOLD}{color}{word}{RESET} ")
        sys.stdout.flush()
        if pause:
            time.sleep(pause)
    sys.stdout.write("\n")
    sys.stdout.flush()


def make_handler(animation: float, state: dict[str, Any]):
    class CaptionHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes = b"") -> None:
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send(204)

        def do_GET(self) -> None:
            if self.path.rstrip("/") == "/health":
                self._send(200, b'{"ok":true,"message":"Caption terminal is ready."}')
            else:
                self._send(404, b'{"ok":false,"error":"Not found"}')

        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/caption":
                self._send(404, b'{"ok":false,"error":"Not found"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 12000:
                    raise ValueError("Invalid message size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Expected a JSON object")
                handle_message(payload, state, animation)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._send(400, json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                return
            self._send(200, b'{"ok":true}')

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return CaptionHandler


def handle_message(message: dict[str, Any], state: dict[str, Any], animation: float) -> None:
    kind = str(message.get("type", ""))
    if kind == "start":
        title = str(message.get("pageTitle") or "Caption page")[:160]
        print(f"\n{BOLD}{COLORS[0]}▶ CAPTION STREAM CONNECTED{RESET}")
        print(f"{DIM}{title}{RESET}")
        print(f"{DIM}Waiting for visible captions…{RESET}\n", flush=True)
    elif kind == "status":
        note = str(message.get("message", ""))[:500]
        if note:
            print(f"{COLORS[2]}• {note}{RESET}", flush=True)
    elif kind == "caption":
        text = " ".join(str(message.get("text", "")).split())[:4000]
        if text:
            state["color_index"] = int(state.get("color_index", -1)) + 1
            print(f"{DIM}♪{RESET} ", end="", flush=True)
            animate_words(text, state["color_index"], animation)
    elif kind == "stop":
        print(f"\n{COLORS[0]}Caption capture stopped.{RESET}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Animate live visible HTML5 captions in a colourful terminal.")
    parser.add_argument("--animation", type=float, default=0.55,
                        help="target reveal time per caption in seconds (default: 0.55)")
    args = parser.parse_args()
    if args.animation < 0:
        parser.error("--animation must be zero or greater")

    print(f"{BOLD}{COLORS[0]}♫ LIVE CAPTION TERMINAL{RESET}")
    print(f"{DIM}Local receiver: http://{HOST}:{PORT}{RESET}")
    print(f"{DIM}Reads visible native captions only; YouTube / YouTube Music / Spotify are blocked.{RESET}")
    print(f"{DIM}Press Ctrl+C to quit.{RESET}\n")

    state: dict[str, Any] = {"color_index": -1}
    server = ThreadingHTTPServer((HOST, PORT), make_handler(args.animation, state))
    try:
        print(f"{COLORS[3]}● Ready. Play your authorized video, then click Start in the browser extension.{RESET}\n", flush=True)
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print(f"\n{COLORS[0]}Terminal stopped.{RESET}")
    except OSError as exc:
        print(f"{COLORS[2]}Could not start local receiver: {exc}{RESET}")
        return 1
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
