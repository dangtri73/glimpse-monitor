from __future__ import annotations

import time
from typing import Any

from agent_common import load_config, now_ms
from domain_gateway import DomainGatewayManager
from prometheus import render_prometheus_metrics
from samples import SampleStore
from system_metrics import SystemMetricsCollector


class MetricsCollector:
    def __init__(self) -> None:
        self._system = SystemMetricsCollector()
        self._domain_gateway = DomainGatewayManager()

    def collect_snapshot(self) -> dict[str, Any]:
        config = load_config()
        return {
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "generatedAtMs": now_ms(),
            "host": self._system.host(),
            "resources": self._system.resources(),
            "topProcesses": self._system.top_processes(),
            "services": self._system.services(config.get("services", [])),
            "topology": {
                "gateway": config.get("gateway", {}),
                "devices": config.get("devices", []),
                "connections": self._system.connections(config),
            },
            "portMappings": config.get("portMappings", []),
            "domainGateway": self._domain_gateway.policy(config),
        }

    def service_action(self, service_id: str, action: str) -> dict[str, Any]:
        config = load_config()
        return self._system.service_action(service_id, action, config.get("services", []))

    def domain_gateway_policy(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._domain_gateway.policy(config)

    def create_port_mapping_draft(self, payload: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        return self._domain_gateway.create_draft(payload, actor=actor)

    def validate_port_mapping(self, mapping_id: str) -> dict[str, Any]:
        return self._domain_gateway.validate(mapping_id)

    def verify_port_mapping(self, mapping_id: str, actor: str | None = None) -> dict[str, Any]:
        return self._domain_gateway.verify(mapping_id, actor=actor)

    def apply_port_mapping(self, mapping_id: str, actor: str | None = None) -> dict[str, Any]:
        return self._domain_gateway.apply(mapping_id, actor=actor)

    def rollback_port_mapping(self, mapping_id: str, actor: str | None = None) -> dict[str, Any]:
        return self._domain_gateway.rollback(mapping_id, actor=actor)

    def prometheus_metrics(self, snapshot: dict[str, Any] | None = None) -> str:
        return render_prometheus_metrics(snapshot or self.collect_snapshot())
