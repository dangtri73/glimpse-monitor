from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .ollama import chat_with_ollama, load_settings, stream_chat_with_ollama


class AiServiceHandler(BaseHTTPRequestHandler):
    server_version = "GlimpseAI/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            settings = load_settings()
            self._json(
                200,
                {
                    "status": "ok",
                    "service": "glimpse-ai-service",
                    "ollamaBaseUrl": settings.base_url,
                    "model": settings.model,
                },
            )
            return

        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self._json(404, {"error": "Not found"})
            return

        started_at = time.monotonic()
        try:
            payload = self._read_json()
            if payload.get("stream") is True:
                self._stream_chat(payload, started_at)
                return

            result = chat_with_ollama(payload)
            result["durationMs"] = round((time.monotonic() - started_at) * 1000)
            self._json(200, result)
        except ValueError as error:
            self._json(400, {"error": str(error)})
        except Exception as error:
            self._json(502, {"error": "Ollama request failed", "detail": str(error)})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        if length > 256_000:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_chat(self, payload: dict[str, Any], started_at: float) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            for chunk in stream_chat_with_ollama(payload):
                self._sse(chunk)
                if chunk.get("done"):
                    break
            self._sse({"done": True, "durationMs": round((time.monotonic() - started_at) * 1000)})
        except Exception as error:
            self._sse(
                {
                    "done": True,
                    "error": "Ollama request failed",
                    "detail": str(error),
                    "durationMs": round((time.monotonic() - started_at) * 1000),
                }
            )
        finally:
            self.close_connection = True

    def _sse(self, payload: dict[str, Any]) -> None:
        frame = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
        self.wfile.write(frame)
        self.wfile.flush()


def main() -> None:
    host = os.getenv("AI_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("AI_SERVICE_PORT", "8770"))
    server = ThreadingHTTPServer((host, port), AiServiceHandler)
    print(f"glimpse ai-service listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
