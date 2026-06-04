from __future__ import annotations

from collections import deque
from typing import Any


class SampleStore:
    def __init__(self, max_samples: int = 720) -> None:
        self._samples: deque[dict[str, Any]] = deque(maxlen=max_samples)

    def append(self, snapshot: dict[str, Any]) -> None:
        resources = snapshot.get("resources", {})
        self._samples.append(
            {
                "generatedAt": snapshot.get("generatedAt"),
                "generatedAtMs": snapshot.get("generatedAtMs"),
                "cpuLoadPercent": resources.get("cpu", {}).get("loadPercent", 0),
                "memoryUsedPercent": resources.get("memory", {}).get("usedPercent", 0),
                "diskUsedPercent": resources.get("disk", {}).get("usedPercent", 0),
                "networkRxBytesPerSecond": resources.get("network", {}).get("rxBytesPerSecond", 0),
                "networkTxBytesPerSecond": resources.get("network", {}).get("txBytesPerSecond", 0),
            }
        )

    def list(self, limit: int = 120) -> list[dict[str, Any]]:
        return list(self._samples)[-limit:]
