from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from agent_common import now_ms, run_text, safe_float, slug


class SystemMetricsCollector:
    def __init__(self) -> None:
        self._previous_network: dict[str, Any] | None = None
        self._user_disk_cache: dict[str, Any] | None = None
        self._user_disk_cache_at = 0.0
        self._user_disk_lock = threading.Lock()
        self._user_disk_scan_in_progress = False

    def host(self) -> dict[str, Any]:
        hostname = socket.gethostname()
        return {
            "deviceId": os.getenv("GLIMPSE_AGENT_DEVICE_ID", slug(hostname)),
            "hostname": hostname,
            "platform": platform.platform(),
            "system": platform.system(),
            "arch": platform.machine(),
            "cpuCount": os.cpu_count() or 1,
            "uptimeSeconds": self._uptime_seconds(),
        }

    def resources(self) -> dict[str, Any]:
        network_totals = self._network_totals()
        return {
            "cpu": self._cpu(),
            "memory": self._memory(),
            "disk": self._disk(),
            "network": self._network_rates(network_totals),
        }

    def top_processes(self) -> list[dict[str, Any]]:
        raw = run_text(["ps", "-axo", "pid,comm,%cpu,%mem"])
        rows = []

        for line in raw.splitlines()[1:]:
            parts = line.split(None, 3)
            if len(parts) != 4:
                continue
            rows.append(
                {
                    "pid": int(parts[0]),
                    "command": parts[1],
                    "cpuPercent": safe_float(parts[2]),
                    "memoryPercent": safe_float(parts[3]),
                }
            )

        rows.sort(key=lambda item: item["cpuPercent"], reverse=True)
        return rows[:8]

    def services(self, service_configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raw = run_text(["ps", "-axo", "pid,comm,args"])
        services = []

        for service in service_configs:
            pattern = service.get("processPattern") or service.get("name") or ""
            matches = []
            if pattern:
                for line in raw.splitlines()[1:]:
                    if pattern.lower() not in line.lower():
                        continue
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        matches.append({"pid": int(parts[0]), "command": parts[1]})

            services.append(
                {
                    "id": service.get("id"),
                    "name": service.get("name"),
                    "status": "running" if matches else "stopped",
                    "processPattern": pattern,
                    "ports": service.get("ports", []),
                    "processes": matches[:5],
                    "actionsEnabled": os.getenv("GLIMPSE_AGENT_ENABLE_SERVICE_ACTIONS") == "true",
                }
            )

        return services

    def connections(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        gateway_id = config.get("gateway", {}).get("id", "dev-gateway")
        connections = []

        for mapping in config.get("portMappings", []):
            connections.append(
                {
                    "id": mapping.get("id"),
                    "from": gateway_id,
                    "to": mapping.get("targetDeviceId"),
                    "label": f"{mapping.get('protocol', 'tcp')}:{mapping.get('publicPort')} -> {mapping.get('targetPort')}",
                    "status": mapping.get("status", "unknown"),
                }
            )

        return connections

    def service_action(self, service_id: str, action: str, service_configs: list[dict[str, Any]]) -> dict[str, Any]:
        services = {item.get("id"): item for item in service_configs}
        service = services.get(service_id)

        if action not in {"start", "stop", "restart"}:
            return {"ok": False, "error": f"Unsupported action: {action}"}
        if not service:
            return {"ok": False, "error": f"Unknown service: {service_id}"}

        enabled = os.getenv("GLIMPSE_AGENT_ENABLE_SERVICE_ACTIONS") == "true"
        command = service.get(f"{action}Command")
        if not enabled:
            return {
                "ok": False,
                "serviceId": service_id,
                "action": action,
                "dryRun": True,
                "error": "Service actions are disabled. Set GLIMPSE_AGENT_ENABLE_SERVICE_ACTIONS=true and configure explicit commands.",
            }
        if not command:
            return {
                "ok": False,
                "serviceId": service_id,
                "action": action,
                "error": f"No {action}Command configured for {service_id}.",
            }

        started_at = time.time()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=20,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
            return {"ok": False, "serviceId": service_id, "action": action, "error": str(exc)}

        return {
            "ok": result.returncode == 0,
            "serviceId": service_id,
            "action": action,
            "exitCode": result.returncode,
            "durationMs": int((time.time() - started_at) * 1000),
            "stdout": result.stdout[-1000:],
            "stderr": result.stderr[-1000:],
        }

    def _uptime_seconds(self) -> float | None:
        if Path("/proc/uptime").exists():
            raw = Path("/proc/uptime").read_text(encoding="utf-8").split()[0]
            return safe_float(raw)

        raw = run_text(["sysctl", "-n", "kern.boottime"])
        match = re.search(r"sec = (\d+)", raw)
        if match:
            return max(0.0, time.time() - float(match.group(1)))

        return None

    def _cpu(self) -> dict[str, Any]:
        cpu_count = os.cpu_count() or 1
        try:
            load1, load5, load15 = os.getloadavg()
        except OSError:
            load1, load5, load15 = 0.0, 0.0, 0.0

        return {
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
            "loadPercent": min(100.0, round((load1 / cpu_count) * 100, 2)),
            "cpuCount": cpu_count,
        }

    def _memory(self) -> dict[str, Any]:
        if Path("/proc/meminfo").exists():
            fields: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, value = line.split(":", 1)
                fields[key] = int(value.strip().split()[0]) * 1024

            total = fields.get("MemTotal", 0)
            available = fields.get("MemAvailable", fields.get("MemFree", 0))
            used = max(0, total - available)
            return _memory_payload(total, used, available)

        total_raw = run_text(["sysctl", "-n", "hw.memsize"])
        total = int(total_raw) if total_raw.isdigit() else 0
        vm_stat = run_text(["vm_stat"])
        page_size_match = re.search(r"page size of (\d+) bytes", vm_stat)
        page_size = int(page_size_match.group(1)) if page_size_match else 4096

        pages: dict[str, int] = {}
        for line in vm_stat.splitlines():
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            value = raw_value.strip().rstrip(".")
            if value.replace(".", "").isdigit():
                pages[key] = int(value.replace(".", ""))

        free = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
        speculative = pages.get("Pages speculative", 0)
        available = (free + speculative) * page_size
        used = max(0, total - available)
        return _memory_payload(total, used, available)

    def _disk(self) -> dict[str, Any]:
        usage = shutil.disk_usage("/")
        return {
            "mount": "/",
            "totalBytes": usage.total,
            "usedBytes": usage.used,
            "freeBytes": usage.free,
            "usedPercent": round((usage.used / usage.total) * 100, 2) if usage.total else 0.0,
            **self._cached_user_disk_usage(usage.total),
        }

    def _cached_user_disk_usage(self, disk_total: int) -> dict[str, Any]:
        ttl_seconds = _env_int("GLIMPSE_AGENT_USER_DISK_CACHE_SECONDS", 300, minimum=30)
        current_time = time.time()

        with self._user_disk_lock:
            cached_payload = self._user_disk_cache
            cached_at = self._user_disk_cache_at
            scan_in_progress = self._user_disk_scan_in_progress

        if cached_payload and current_time - cached_at < ttl_seconds:
            return {
                **cached_payload,
                "userUsageScanAgeSeconds": int(current_time - cached_at),
                "userUsageScanInProgress": scan_in_progress,
            }

        if not scan_in_progress:
            self._start_user_disk_scan(disk_total)

        if cached_payload:
            return {
                **cached_payload,
                "userUsageScanAgeSeconds": int(current_time - cached_at),
                "userUsageScanInProgress": True,
            }

        return {
            **_user_disk_payload(root=_user_disk_root(), error="user disk usage scan in progress"),
            "userUsageScanAgeSeconds": 0,
            "userUsageScanInProgress": True,
        }

    def _start_user_disk_scan(self, disk_total: int) -> None:
        with self._user_disk_lock:
            if self._user_disk_scan_in_progress:
                return
            self._user_disk_scan_in_progress = True

        thread = threading.Thread(target=self._refresh_user_disk_cache, args=(disk_total,), daemon=True)
        thread.start()

    def _refresh_user_disk_cache(self, disk_total: int) -> None:
        try:
            payload = self._user_disk_usage(disk_total)
        except Exception as exc:  # Defensive: disk usage must not break live resource snapshots.
            payload = _user_disk_payload(root=_user_disk_root(), error=str(exc))

        with self._user_disk_lock:
            self._user_disk_cache = payload
            self._user_disk_cache_at = time.time()
            self._user_disk_scan_in_progress = False

    def _user_disk_usage(self, disk_total: int) -> dict[str, Any]:
        if os.getenv("GLIMPSE_AGENT_ENABLE_USER_DISK_USAGE", "true").lower() not in {"1", "true", "yes", "on"}:
            return _user_disk_payload(error="user disk usage scan disabled")

        root = _user_disk_root()
        if not root:
            return _user_disk_payload(error="no user directory found")

        try:
            children = [path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")]
        except OSError as exc:
            return _user_disk_payload(root=root, error=str(exc))

        max_users = _env_int("GLIMPSE_AGENT_USER_DISK_MAX_USERS", 64, minimum=1, maximum=256)
        paths = sorted(children, key=lambda path: path.name.lower())[:max_users]
        if not paths:
            return _user_disk_payload(root=root)

        timeout_seconds = _env_int("GLIMPSE_AGENT_USER_DISK_TIMEOUT_SECONDS", 30, minimum=5, maximum=300)
        try:
            result = subprocess.run(
                ["du", "-skx", *[str(path) for path in paths]],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return _user_disk_payload(root=root, error=f"user disk usage scan timed out after {timeout_seconds}s")
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
            return _user_disk_payload(root=root, error=str(exc))

        rows = []
        for line in result.stdout.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            try:
                used_bytes = int(parts[0]) * 1024
            except ValueError:
                continue

            path = Path(parts[1])
            rows.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "usedBytes": used_bytes,
                    "usedPercentOfDisk": round((used_bytes / disk_total) * 100, 2) if disk_total else 0.0,
                }
            )

        rows.sort(key=lambda item: item["usedBytes"], reverse=True)
        total_user_bytes = sum(item["usedBytes"] for item in rows)
        result_limit = _env_int("GLIMPSE_AGENT_USER_DISK_RESULT_LIMIT", 12, minimum=1, maximum=100)
        error = None
        if result.returncode != 0 and not rows:
            error = "user disk usage scan failed"

        return _user_disk_payload(root=root, rows=rows[:result_limit], total_bytes=total_user_bytes, error=error)

    def _network_totals(self) -> dict[str, Any]:
        if Path("/proc/net/dev").exists():
            interfaces = []
            rx_total = 0
            tx_total = 0
            for line in Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]:
                name, raw = line.split(":", 1)
                parts = raw.split()
                rx = int(parts[0])
                tx = int(parts[8])
                iface = name.strip()
                if iface == "lo":
                    continue
                rx_total += rx
                tx_total += tx
                interfaces.append({"name": iface, "rxBytes": rx, "txBytes": tx})

            return {"atMs": now_ms(), "rxBytes": rx_total, "txBytes": tx_total, "interfaces": interfaces}

        raw = run_text(["netstat", "-ibn"])
        interfaces_by_name: dict[str, dict[str, Any]] = {}
        rx_total = 0
        tx_total = 0

        for line in raw.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            name = parts[0]
            if name.startswith("lo"):
                continue
            try:
                rx = int(parts[6])
                tx = int(parts[9])
            except ValueError:
                continue
            interfaces_by_name[name] = {"name": name, "rxBytes": rx, "txBytes": tx}

        for item in interfaces_by_name.values():
            rx_total += item["rxBytes"]
            tx_total += item["txBytes"]

        return {
            "atMs": now_ms(),
            "rxBytes": rx_total,
            "txBytes": tx_total,
            "interfaces": list(interfaces_by_name.values()),
        }

    def _network_rates(self, current: dict[str, Any]) -> dict[str, Any]:
        previous = self._previous_network
        self._previous_network = current

        if not previous:
            return {**current, "rxBytesPerSecond": 0, "txBytesPerSecond": 0}

        elapsed = max(1, current["atMs"] - previous["atMs"]) / 1000
        rx_rate = max(0, current["rxBytes"] - previous["rxBytes"]) / elapsed
        tx_rate = max(0, current["txBytes"] - previous["txBytes"]) / elapsed

        return {
            **current,
            "rxBytesPerSecond": round(rx_rate, 2),
            "txBytesPerSecond": round(tx_rate, 2),
        }


def _memory_payload(total: int, used: int, available: int) -> dict[str, Any]:
    percent = (used / total * 100) if total else 0.0
    return {
        "totalBytes": total,
        "usedBytes": used,
        "availableBytes": available,
        "usedPercent": round(percent, 2),
    }


def _user_disk_root() -> Path | None:
    configured_root = os.getenv("GLIMPSE_AGENT_USER_DISK_ROOT")
    if configured_root:
        path = Path(configured_root).expanduser()
        return path if path.exists() and path.is_dir() else None

    for candidate in (Path("/System/Volumes/Data/Users"), Path("/Users"), Path("/home")):
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _user_disk_payload(
    *,
    root: Path | None = None,
    rows: list[dict[str, Any]] | None = None,
    total_bytes: int = 0,
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "userUsageRoot": str(root) if root else "",
        "userUsage": rows or [],
        "userUsageTotalBytes": total_bytes,
        "userUsageScannedAtMs": now_ms(),
    }
    if error:
        payload["userUsageError"] = error
    return payload


def _env_int(name: str, fallback: int, *, minimum: int, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(fallback)))
    except ValueError:
        value = fallback
    value = max(minimum, value)
    return min(maximum, value) if maximum is not None else value
