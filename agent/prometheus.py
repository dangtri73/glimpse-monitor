from __future__ import annotations

from typing import Any


def render_prometheus_metrics(payload: dict[str, Any]) -> str:
    host = payload.get("host", {})
    resources = payload.get("resources", {})
    cpu = resources.get("cpu", {})
    memory = resources.get("memory", {})
    disk = resources.get("disk", {})
    network = resources.get("network", {})
    labels = {
        "device_id": str(host.get("deviceId", "unknown-device")),
        "hostname": str(host.get("hostname", "unknown-host")),
    }

    lines = [
        "# HELP glimpse_agent_up Whether the Glimpse monitor agent is running.",
        "# TYPE glimpse_agent_up gauge",
        f"glimpse_agent_up{_labels(labels)} 1",
        "# HELP glimpse_agent_snapshot_generated_at_ms Unix timestamp in milliseconds for the latest snapshot.",
        "# TYPE glimpse_agent_snapshot_generated_at_ms gauge",
        f"glimpse_agent_snapshot_generated_at_ms{_labels(labels)} {payload.get('generatedAtMs', 0)}",
        "# HELP glimpse_host_cpu_load_percent Host CPU load normalized by CPU count.",
        "# TYPE glimpse_host_cpu_load_percent gauge",
        f"glimpse_host_cpu_load_percent{_labels(labels)} {cpu.get('loadPercent', 0)}",
        "# HELP glimpse_host_cpu_load1 One minute host load average.",
        "# TYPE glimpse_host_cpu_load1 gauge",
        f"glimpse_host_cpu_load1{_labels(labels)} {cpu.get('load1', 0)}",
        "# HELP glimpse_host_cpu_load5 Five minute host load average.",
        "# TYPE glimpse_host_cpu_load5 gauge",
        f"glimpse_host_cpu_load5{_labels(labels)} {cpu.get('load5', 0)}",
        "# HELP glimpse_host_cpu_load15 Fifteen minute host load average.",
        "# TYPE glimpse_host_cpu_load15 gauge",
        f"glimpse_host_cpu_load15{_labels(labels)} {cpu.get('load15', 0)}",
        "# HELP glimpse_host_cpu_count Host CPU count.",
        "# TYPE glimpse_host_cpu_count gauge",
        f"glimpse_host_cpu_count{_labels(labels)} {cpu.get('cpuCount', 0)}",
        "# HELP glimpse_host_memory_used_percent Host memory used percent.",
        "# TYPE glimpse_host_memory_used_percent gauge",
        f"glimpse_host_memory_used_percent{_labels(labels)} {memory.get('usedPercent', 0)}",
        "# HELP glimpse_host_memory_total_bytes Host total memory in bytes.",
        "# TYPE glimpse_host_memory_total_bytes gauge",
        f"glimpse_host_memory_total_bytes{_labels(labels)} {memory.get('totalBytes', 0)}",
        "# HELP glimpse_host_memory_used_bytes Host used memory in bytes.",
        "# TYPE glimpse_host_memory_used_bytes gauge",
        f"glimpse_host_memory_used_bytes{_labels(labels)} {memory.get('usedBytes', 0)}",
        "# HELP glimpse_host_memory_available_bytes Host available memory in bytes.",
        "# TYPE glimpse_host_memory_available_bytes gauge",
        f"glimpse_host_memory_available_bytes{_labels(labels)} {memory.get('availableBytes', 0)}",
        "# HELP glimpse_host_disk_used_percent Host root disk used percent.",
        "# TYPE glimpse_host_disk_used_percent gauge",
        f"glimpse_host_disk_used_percent{_labels({**labels, 'mount': str(disk.get('mount', '/'))})} {disk.get('usedPercent', 0)}",
        "# HELP glimpse_host_disk_total_bytes Host root disk total bytes.",
        "# TYPE glimpse_host_disk_total_bytes gauge",
        f"glimpse_host_disk_total_bytes{_labels({**labels, 'mount': str(disk.get('mount', '/'))})} {disk.get('totalBytes', 0)}",
        "# HELP glimpse_host_disk_free_bytes Host root disk free bytes.",
        "# TYPE glimpse_host_disk_free_bytes gauge",
        f"glimpse_host_disk_free_bytes{_labels({**labels, 'mount': str(disk.get('mount', '/'))})} {disk.get('freeBytes', 0)}",
        "# HELP glimpse_host_network_rx_bytes_per_second Aggregate receive throughput in bytes per second.",
        "# TYPE glimpse_host_network_rx_bytes_per_second gauge",
        f"glimpse_host_network_rx_bytes_per_second{_labels(labels)} {network.get('rxBytesPerSecond', 0)}",
        "# HELP glimpse_host_network_tx_bytes_per_second Aggregate transmit throughput in bytes per second.",
        "# TYPE glimpse_host_network_tx_bytes_per_second gauge",
        f"glimpse_host_network_tx_bytes_per_second{_labels(labels)} {network.get('txBytesPerSecond', 0)}",
        "# HELP glimpse_host_network_rx_bytes_total Aggregate received bytes.",
        "# TYPE glimpse_host_network_rx_bytes_total counter",
        f"glimpse_host_network_rx_bytes_total{_labels(labels)} {network.get('rxBytes', 0)}",
        "# HELP glimpse_host_network_tx_bytes_total Aggregate transmitted bytes.",
        "# TYPE glimpse_host_network_tx_bytes_total counter",
        f"glimpse_host_network_tx_bytes_total{_labels(labels)} {network.get('txBytes', 0)}",
        "# HELP glimpse_service_up Configured service process status.",
        "# TYPE glimpse_service_up gauge",
    ]

    for service in payload.get("services", []):
        service_labels = {
            **labels,
            "service_id": str(service.get("id", "unknown-service")),
            "service_name": str(service.get("name", "Unknown Service")),
        }
        value = 1 if service.get("status") == "running" else 0
        lines.append(f"glimpse_service_up{_labels(service_labels)} {value}")

    return "\n".join(lines) + "\n"


def _labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""

    rendered = ",".join(f'{key}="{_escape_label_value(value)}"' for key, value in sorted(labels.items()))
    return "{" + rendered + "}"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
