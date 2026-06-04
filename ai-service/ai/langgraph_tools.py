from __future__ import annotations

import json
import statistics
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_AGENT_URL = "http://127.0.0.1:8765"


@dataclass
class SystemToolClient:
    agent_url: str = DEFAULT_AGENT_URL

    def snapshot(self) -> dict[str, Any]:
        return self._get("/api/snapshot")

    def samples(self, limit: int = 120) -> list[dict[str, Any]]:
        payload = self._get(f"/api/samples?limit={limit}")
        return payload.get("samples", [])

    def compare_recent_windows(self, window_size: int = 30) -> dict[str, Any]:
        data = self.samples(limit=window_size * 2)
        older = data[:window_size]
        newer = data[window_size:]

        return {
            "windowSize": window_size,
            "older": _window_summary(older),
            "newer": _window_summary(newer),
            "delta": _window_delta(_window_summary(older), _window_summary(newer)),
        }

    def service_status(self) -> dict[str, Any]:
        return self._get("/api/services")

    def port_mappings(self) -> dict[str, Any]:
        return self._get("/api/port-maps")

    def _get(self, path: str) -> dict[str, Any]:
        with urllib.request.urlopen(f"{self.agent_url}{path}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))


def _window_summary(samples: list[dict[str, Any]]) -> dict[str, float]:
    if not samples:
        return {
            "cpuAvg": 0.0,
            "memoryAvg": 0.0,
            "diskAvg": 0.0,
            "rxAvg": 0.0,
            "txAvg": 0.0,
        }

    return {
        "cpuAvg": round(statistics.mean(item.get("cpuLoadPercent", 0) for item in samples), 2),
        "memoryAvg": round(statistics.mean(item.get("memoryUsedPercent", 0) for item in samples), 2),
        "diskAvg": round(statistics.mean(item.get("diskUsedPercent", 0) for item in samples), 2),
        "rxAvg": round(statistics.mean(item.get("networkRxBytesPerSecond", 0) for item in samples), 2),
        "txAvg": round(statistics.mean(item.get("networkTxBytesPerSecond", 0) for item in samples), 2),
    }


def _window_delta(older: dict[str, float], newer: dict[str, float]) -> dict[str, float]:
    return {key: round(newer.get(key, 0.0) - older.get(key, 0.0), 2) for key in newer}


def available_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_system_snapshot",
            "description": "Return current CPU, RAM, disk, network, services, devices, and port mappings.",
        },
        {
            "name": "get_metric_samples",
            "description": "Return recent time-series samples for charting and historical comparison.",
        },
        {
            "name": "compare_recent_windows",
            "description": "Compare the newest metric window against the previous metric window.",
        },
        {
            "name": "get_service_status",
            "description": "List configured services and whether each service process is running.",
        },
        {
            "name": "get_port_mappings",
            "description": "List gateway-to-device port mappings and planned public exposure rules.",
        },
    ]


def build_langgraph_app(llm: Any, agent_url: str = DEFAULT_AGENT_URL) -> Any:
    try:
        from langchain_core.tools import tool
        from langgraph.prebuilt import create_react_agent
    except ImportError as exc:
        raise RuntimeError(
            "Install langgraph and langchain-core to build the system assistant graph."
        ) from exc

    client = SystemToolClient(agent_url=agent_url)

    @tool
    def get_system_snapshot() -> dict[str, Any]:
        """Return current host and gateway monitoring state."""
        return client.snapshot()

    @tool
    def get_metric_samples(limit: int = 120) -> list[dict[str, Any]]:
        """Return recent metric samples for trend analysis."""
        return client.samples(limit=limit)

    @tool
    def compare_recent_windows(window_size: int = 30) -> dict[str, Any]:
        """Compare newest metrics against the immediately previous window."""
        return client.compare_recent_windows(window_size=window_size)

    @tool
    def get_service_status() -> dict[str, Any]:
        """Return configured service status."""
        return client.service_status()

    @tool
    def get_port_mappings() -> dict[str, Any]:
        """Return current and planned gateway port mappings."""
        return client.port_mappings()

    return create_react_agent(
        llm,
        tools=[
            get_system_snapshot,
            get_metric_samples,
            compare_recent_windows,
            get_service_status,
            get_port_mappings,
        ],
    )
