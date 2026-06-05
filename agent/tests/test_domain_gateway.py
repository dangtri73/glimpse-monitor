from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from domain_gateway import DomainGatewayManager  # noqa: E402


class DomainGatewayManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "devices.json"
        os.environ["GLIMPSE_AGENT_CONFIG_PATH"] = str(self.config_path)
        os.environ["MACSTUDIO_LAN_IP"] = "192.168.1.44"
        self.write_config(
            {
                "gateway": {},
                "devices": [],
                "services": [],
                "portMappings": [],
                "domainGateway": {
                    "allowedPublicPorts": [80],
                    "allowedProtocols": ["http"],
                    "allowedTargetHosts": ["${MACSTUDIO_LAN_IP}"],
                    "reservedHosts": ["glimpse-go.site"],
                    "targets": [
                        {
                            "id": "dashboard",
                            "name": "Dashboard",
                            "targetDeviceId": "mac-studio",
                            "targetHost": "${MACSTUDIO_LAN_IP}",
                            "targetPort": 3000,
                            "protocol": "http",
                            "upstream": "http://${MACSTUDIO_LAN_IP}:3000",
                            "enabled": True,
                        },
                        {
                            "id": "disabled",
                            "name": "Disabled",
                            "targetDeviceId": "mac-studio",
                            "targetHost": "${MACSTUDIO_LAN_IP}",
                            "targetPort": 3999,
                            "protocol": "http",
                            "upstream": "http://${MACSTUDIO_LAN_IP}:3999",
                            "enabled": False,
                        },
                        {
                            "id": "external",
                            "name": "External",
                            "targetDeviceId": "other",
                            "targetHost": "203.0.113.10",
                            "targetPort": 3000,
                            "protocol": "http",
                            "upstream": "http://203.0.113.10:3000",
                            "enabled": True,
                        },
                    ],
                },
            }
        )

    def tearDown(self) -> None:
        os.environ.pop("GLIMPSE_AGENT_CONFIG_PATH", None)
        os.environ.pop("MACSTUDIO_LAN_IP", None)
        self.temp_dir.cleanup()

    def write_config(self, config: dict) -> None:
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def read_config(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def test_policy_hides_disabled_targets(self) -> None:
        policy = DomainGatewayManager().policy()
        target_ids = {target["id"] for target in policy["targets"]}

        self.assertIn("dashboard", target_ids)
        self.assertIn("external", target_ids)
        self.assertNotIn("disabled", target_ids)

    def test_create_draft_uses_canonical_target_upstream(self) -> None:
        result = DomainGatewayManager().create_draft(
            {
                "publicHost": "team.example.com",
                "targetId": "dashboard",
                "upstream": "http://evil.example.com:80",
            },
            actor="test-admin",
        )

        self.assertTrue(result["ok"])
        self.assertEqual("http://192.168.1.44:3000", result["mapping"]["upstream"])
        self.assertEqual("192.168.1.44", result["mapping"]["targetHost"])
        self.assertEqual("${MACSTUDIO_LAN_IP}", self.read_config()["domainGateway"]["targets"][0]["targetHost"])

    def test_create_draft_rejects_disabled_target(self) -> None:
        result = DomainGatewayManager().create_draft(
            {
                "publicHost": "team.example.com",
                "targetId": "disabled",
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("Unknown or unavailable target service", result["error"])

    def test_validate_rejects_target_outside_gateway_host_allowlist(self) -> None:
        result = DomainGatewayManager().create_draft(
            {
                "publicHost": "team.example.com",
                "targetId": "external",
            }
        )

        self.assertFalse(result["ok"])
        failed_checks = {check["id"] for check in result["checks"] if not check["ok"]}
        self.assertIn("target-host", failed_checks)

    def test_validate_rejects_tampered_upstream(self) -> None:
        manager = DomainGatewayManager()
        result = manager.create_draft(
            {
                "publicHost": "team.example.com",
                "targetId": "dashboard",
            }
        )
        self.assertTrue(result["ok"])

        config = self.read_config()
        config["portMappings"][0]["upstream"] = "http://203.0.113.20:3000"
        self.write_config(config)

        validation = manager.validate("team-example-com")
        self.assertFalse(validation["ok"])
        failed_checks = {check["id"] for check in validation["checks"] if not check["ok"]}
        self.assertIn("target-canonical", failed_checks)


if __name__ == "__main__":
    unittest.main()
