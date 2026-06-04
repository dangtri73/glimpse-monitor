from __future__ import annotations

import json
import os
import re
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {"gateway": {}, "devices": [], "services": [], "portMappings": [], "domainGateway": {}}
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "devices.json"


def config_path() -> Path:
    raw_path = os.getenv("GLIMPSE_AGENT_CONFIG_PATH")
    if not raw_path:
        return DEFAULT_CONFIG_PATH

    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def run_text(command: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return ""

    return result.stdout.strip()


def run_command(command: list[Any], timeout: float) -> dict[str, Any]:
    if not command or not all(isinstance(part, str) and part for part in command):
        return {"ok": False, "error": "Command must be a non-empty string array."}

    started_at = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
        return {"ok": False, "error": str(exc), "command": command}

    return {
        "ok": result.returncode == 0,
        "command": command,
        "exitCode": result.returncode,
        "durationMs": int((time.time() - started_at) * 1000),
        "stdout": result.stdout[-1000:],
        "stderr": result.stderr[-1000:],
    }


def now_ms() -> int:
    return int(time.time() * 1000)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: str, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return normalized.strip("-") or "unknown-device"


def coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
