from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from collector import MetricsCollector, SampleStore


collector = MetricsCollector()
samples = SampleStore()
latest_snapshot: dict[str, Any] | None = None
MAX_REQUEST_BYTES = 64 * 1024


def _json(data: Any, status: int = 200) -> tuple[int, bytes]:
    return status, json.dumps(data, ensure_ascii=False).encode("utf-8")


def _poll_loop(interval_seconds: float) -> None:
    global latest_snapshot

    while True:
        snapshot = collector.collect_snapshot()
        latest_snapshot = snapshot
        samples.append(snapshot)
        time.sleep(interval_seconds)


class Handler(BaseHTTPRequestHandler):
    server_version = "GlimpseMonitorAgent/0.1"

    def do_OPTIONS(self) -> None:
        self._send(204, b"")

    def do_GET(self) -> None:
        global latest_snapshot

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            return self._send_json({"ok": True, "service": "glimpse-monitor-agent"})

        if path == "/api/snapshot":
            if latest_snapshot is None:
                latest_snapshot = collector.collect_snapshot()
                samples.append(latest_snapshot)
            return self._send_json(latest_snapshot)

        if path == "/metrics":
            if latest_snapshot is None:
                latest_snapshot = collector.collect_snapshot()
                samples.append(latest_snapshot)
            payload = collector.prometheus_metrics(latest_snapshot).encode("utf-8")
            return self._send(200, payload, content_type="text/plain; version=0.0.4; charset=utf-8")

        if path == "/api/samples":
            limit = int(query.get("limit", ["120"])[0])
            return self._send_json({"samples": samples.list(limit=max(1, min(limit, 720)))})

        if path == "/api/services":
            snapshot = latest_snapshot or collector.collect_snapshot()
            return self._send_json({"services": snapshot.get("services", [])})

        if path == "/api/port-maps":
            snapshot = latest_snapshot or collector.collect_snapshot()
            return self._send_json(
                {
                    "portMappings": snapshot.get("portMappings", []),
                    "domainGateway": snapshot.get("domainGateway", {}),
                }
            )

        return self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        actor = self.headers.get("X-Glimpse-Actor")

        if not self._is_authorized_mutation():
            return self._send_json({"ok": False, "error": "Unauthorized"}, status=401)

        if len(parts) == 4 and parts[:2] == ["api", "services"]:
            service_id = parts[2]
            action = parts[3]
            return self._send_json(collector.service_action(service_id, action))

        if parts == ["api", "port-maps", "drafts"]:
            payload = self._read_json()
            if payload is None:
                return self._send_json({"ok": False, "error": "Invalid JSON body."}, status=400)
            return self._send_json(collector.create_port_mapping_draft(payload, actor=actor))

        if len(parts) == 4 and parts[:2] == ["api", "port-maps"]:
            mapping_id = parts[2]
            action = parts[3]
            if action == "validate":
                return self._send_json(collector.validate_port_mapping(mapping_id))
            if action == "verify":
                return self._send_json(collector.verify_port_mapping(mapping_id, actor=actor))
            if action == "apply":
                return self._send_json(collector.apply_port_mapping(mapping_id, actor=actor))
            if action == "rollback":
                return self._send_json(collector.rollback_port_mapping(mapping_id, actor=actor))
            return self._send_json({"ok": False, "error": f"Unsupported port mapping action: {action}"}, status=400)

        return self._send_json({"error": "Not found"}, status=404)

    def _read_json(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return None
        if content_length > MAX_REQUEST_BYTES:
            return None
        if content_length == 0:
            return {}

        try:
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        return payload if isinstance(payload, dict) else None

    def _is_authorized_mutation(self) -> bool:
        token = os.getenv("GLIMPSE_AGENT_ADMIN_TOKEN")
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def _send_json(self, data: Any, status: int = 200) -> None:
        code, payload = _json(data, status=status)
        self._send(code, payload, content_type="application/json; charset=utf-8")

    def _send(self, status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", os.getenv("GLIMPSE_AGENT_CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Glimpse-Actor")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("GLIMPSE_AGENT_LOG_REQUESTS") == "true":
            super().log_message(format, *args)


def main() -> None:
    host = os.getenv("GLIMPSE_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("GLIMPSE_AGENT_PORT", "8765"))
    interval = float(os.getenv("GLIMPSE_AGENT_POLL_SECONDS", "2"))

    thread = threading.Thread(target=_poll_loop, args=(interval,), daemon=True)
    thread.start()

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"glimpse monitor agent listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
