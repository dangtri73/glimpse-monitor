from __future__ import annotations

import os
import re
import secrets
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agent_common import (
    coerce_int,
    config_path,
    expand_config_env,
    load_config,
    now_ms,
    run_command,
    run_text,
    save_config,
    slug,
    utc_now,
)


DEFAULT_NGINX_GENERATED_CONF_PATH = (
    Path(__file__).resolve().parent.parent / "nginx-docker" / "nginx" / "generated" / "domain-maps.conf"
)
DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SAFE_UPSTREAM_HOST_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class DomainGatewayManager:
    def _config_pair(self) -> tuple[dict[str, Any], dict[str, Any]]:
        raw_config = load_config(expand_env=False)
        return raw_config, expand_config_env(raw_config)

    def policy(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = config or load_config()
        gateway_config = payload.get("domainGateway", {})
        targets = [
            {
                "id": target.get("id"),
                "name": target.get("name"),
                "targetDeviceId": target.get("targetDeviceId"),
                "targetHost": target.get("targetHost"),
                "targetPort": target.get("targetPort"),
                "protocol": target.get("protocol", "http"),
                "ownerTeamId": target.get("ownerTeamId"),
                "allowedTeamIds": target.get("allowedTeamIds", []),
            }
            for target in gateway_config.get("targets", [])
            if target.get("enabled", True)
        ]

        return {
            "baseCname": gateway_config.get("baseCname"),
            "publicIp": gateway_config.get("publicIp"),
            "allowedPublicPorts": gateway_config.get("allowedPublicPorts", [80]),
            "allowedHostSuffixes": gateway_config.get("allowedHostSuffixes", []),
            "targets": targets,
        }

    def create_draft(self, payload: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        raw_config, config = self._config_pair()
        gateway_config = config.get("domainGateway", {})
        targets = self._target_lookup(config)
        target_id = str(payload.get("targetId") or "").strip()
        target = targets.get(target_id)

        if not target:
            return {"ok": False, "error": "Unknown or unavailable target service.", "targets": list(targets)}

        public_host = normalize_public_host(payload.get("publicHost"))
        public_port = coerce_int(
            payload.get("publicPort"),
            int((gateway_config.get("allowedPublicPorts") or [80])[0]),
        )
        protocol = str(payload.get("protocol") or target.get("protocol") or "http").lower()
        owner_team_id = str(
            payload.get("ownerTeamId") or payload.get("teamId") or target.get("ownerTeamId") or ""
        ).strip()
        upstream = target_upstream(target)
        now = utc_now()
        token = f"glimpse-domain={secrets.token_urlsafe(18)}"

        mapping = {
            "id": self._unique_mapping_id(config, public_host),
            "name": str(payload.get("name") or public_host or target.get("name") or "Domain route").strip(),
            "publicHost": public_host,
            "publicPort": public_port,
            "targetId": target_id,
            "targetDeviceId": target.get("targetDeviceId"),
            "targetHost": target.get("targetHost"),
            "targetPort": int(target.get("targetPort", 0)),
            "upstream": upstream,
            "protocol": protocol,
            "status": "draft",
            "authRequired": bool(payload.get("authRequired", True)),
            "ownerTeamId": owner_team_id or None,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": actor,
            "verification": {
                "method": "dns-txt",
                "name": f"_glimpse.{public_host}" if public_host else "",
                "value": token,
                "status": "pending",
                "checkedAt": None,
            },
        }

        validation = self.validate_mapping(config, mapping)
        if not validation["ok"]:
            return {"ok": False, "mapping": mapping, **validation}

        raw_config.setdefault("portMappings", []).append(mapping)
        self._append_audit(raw_config, actor, "port_mapping.draft_created", "port_mapping", mapping["id"], mapping)
        save_config(raw_config)
        return {"ok": True, "mapping": mapping, **validation}

    def validate(self, mapping_id: str) -> dict[str, Any]:
        config = load_config()
        mapping = self._find_mapping(config, mapping_id)
        if not mapping:
            return {"ok": False, "error": f"Unknown port mapping: {mapping_id}"}

        return {"mapping": mapping, **self.validate_mapping(config, mapping)}

    def verify(self, mapping_id: str, actor: str | None = None) -> dict[str, Any]:
        raw_config, config = self._config_pair()
        mapping = self._find_mapping(config, mapping_id)
        raw_mapping = self._find_mapping(raw_config, mapping_id)
        if not mapping:
            return {"ok": False, "error": f"Unknown port mapping: {mapping_id}"}
        assert raw_mapping is not None

        verification = raw_mapping.get("verification") or {}
        name = verification.get("name")
        expected = verification.get("value")
        if not name or not expected:
            return {"ok": False, "mapping": mapping, "error": "Mapping has no DNS verification challenge."}

        if not shutil.which("dig"):
            return {
                "ok": False,
                "mapping": mapping,
                "error": "dig is not installed on this host, so DNS TXT verification cannot run.",
            }

        raw = run_text(["dig", "+short", "TXT", str(name)], timeout=8.0)
        flattened = raw.replace('"', "").replace("\\", "")
        verified = str(expected) in flattened
        verification["checkedAt"] = utc_now()
        verification["status"] = "verified" if verified else "pending"
        raw_mapping["verification"] = verification
        raw_mapping["updatedAt"] = utc_now()
        mapping = expand_config_env(raw_mapping)

        if verified:
            self._append_audit(raw_config, actor, "port_mapping.domain_verified", "port_mapping", mapping_id, verification)

        save_config(raw_config)
        return {
            "ok": verified,
            "mapping": mapping,
            "records": raw.splitlines(),
            "expected": expected,
            "error": None if verified else "Expected TXT challenge was not found.",
        }

    def apply(self, mapping_id: str, actor: str | None = None) -> dict[str, Any]:
        raw_config, config = self._config_pair()
        mapping = self._find_mapping(config, mapping_id)
        if not mapping:
            return {"ok": False, "error": f"Unknown port mapping: {mapping_id}"}

        validation = self.validate_mapping(config, mapping)
        if not validation["ok"]:
            return {"ok": False, "mapping": mapping, **validation}

        next_raw_config = deepcopy(raw_config)
        next_raw_mapping = self._find_mapping(next_raw_config, mapping_id)
        assert next_raw_mapping is not None
        next_raw_mapping["status"] = "active"
        next_raw_mapping["updatedAt"] = utc_now()
        self._append_audit(next_raw_config, actor, "port_mapping.applied", "port_mapping", mapping_id, next_raw_mapping)

        next_config = expand_config_env(next_raw_config)
        next_mapping = self._find_mapping(next_config, mapping_id)
        assert next_mapping is not None
        rendered_config = self.render_nginx_config(next_config)
        if os.getenv("GLIMPSE_AGENT_ENABLE_NGINX_APPLY") != "true":
            return {
                "ok": True,
                "dryRun": True,
                "mapping": next_mapping,
                "renderedConfig": rendered_config,
                "message": "Live Nginx apply is disabled. Set GLIMPSE_AGENT_ENABLE_NGINX_APPLY=true after configuring test/reload command arrays.",
            }

        if (
            next_mapping.get("verification", {}).get("status") != "verified"
            and os.getenv("GLIMPSE_AGENT_ALLOW_UNVERIFIED_DOMAINS") != "true"
        ):
            return {
                "ok": False,
                "mapping": mapping,
                "error": "Domain ownership is not verified.",
                "verification": mapping.get("verification"),
            }

        write_result = self._write_test_reload_nginx(next_config, rendered_config)
        if not write_result["ok"]:
            return {"ok": False, "mapping": mapping, **write_result}

        save_config(next_raw_config)
        return {"ok": True, "dryRun": False, "mapping": next_mapping, **write_result}

    def rollback(self, mapping_id: str, actor: str | None = None) -> dict[str, Any]:
        raw_config, config = self._config_pair()
        mapping = self._find_mapping(config, mapping_id)
        if not mapping:
            return {"ok": False, "error": f"Unknown port mapping: {mapping_id}"}

        next_raw_config = deepcopy(raw_config)
        next_raw_mapping = self._find_mapping(next_raw_config, mapping_id)
        assert next_raw_mapping is not None
        next_raw_mapping["status"] = "disabled"
        next_raw_mapping["updatedAt"] = utc_now()
        self._append_audit(next_raw_config, actor, "port_mapping.rolled_back", "port_mapping", mapping_id, next_raw_mapping)

        next_config = expand_config_env(next_raw_config)
        next_mapping = self._find_mapping(next_config, mapping_id)
        assert next_mapping is not None
        rendered_config = self.render_nginx_config(next_config)

        if os.getenv("GLIMPSE_AGENT_ENABLE_NGINX_APPLY") != "true":
            return {
                "ok": True,
                "dryRun": True,
                "mapping": next_mapping,
                "renderedConfig": rendered_config,
                "message": "Live Nginx apply is disabled; rollback was not written to Nginx.",
            }

        write_result = self._write_test_reload_nginx(next_config, rendered_config)
        if not write_result["ok"]:
            return {"ok": False, "mapping": mapping, **write_result}

        save_config(next_raw_config)
        return {"ok": True, "dryRun": False, "mapping": next_mapping, **write_result}

    def validate_mapping(self, config: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
        checks = []
        warnings = []
        gateway_config = config.get("domainGateway", {})
        public_host = normalize_public_host(mapping.get("publicHost"))
        public_port = coerce_int(mapping.get("publicPort"), 80)
        allowed_ports = [int(port) for port in gateway_config.get("allowedPublicPorts", [80])]
        allowed_protocols = gateway_config.get("allowedProtocols", ["http"])
        reserved_hosts = {
            normalize_public_host(host)
            for host in gateway_config.get("reservedHosts", [])
            if normalize_public_host(host)
        }
        allowed_suffixes = [
            normalize_public_host(suffix)
            for suffix in gateway_config.get("allowedHostSuffixes", [])
            if normalize_public_host(suffix)
        ]

        domain_ok = valid_domain(public_host)
        checks.append(
            {
                "id": "domain-syntax",
                "ok": domain_ok,
                "message": "Public host is a valid DNS name." if domain_ok else "Public host must be a valid domain name.",
            }
        )

        reserved_ok = public_host not in reserved_hosts
        checks.append(
            {
                "id": "reserved-host",
                "ok": reserved_ok,
                "message": "Host is available for member mappings."
                if reserved_ok
                else "Host is reserved by the gateway baseline config.",
            }
        )

        suffix_ok = not allowed_suffixes or any(
            public_host == suffix or public_host.endswith(f".{suffix}") for suffix in allowed_suffixes
        )
        checks.append(
            {
                "id": "allowed-suffix",
                "ok": suffix_ok,
                "message": "Host suffix is allowed." if suffix_ok else "Host is outside the allowed domain suffix list.",
            }
        )

        conflict = next(
            (
                item
                for item in config.get("portMappings", [])
                if item.get("id") != mapping.get("id")
                and item.get("status") != "disabled"
                and normalize_public_host(item.get("publicHost")) == public_host
                and coerce_int(item.get("publicPort"), 80) == public_port
            ),
            None,
        )
        checks.append(
            {
                "id": "domain-conflict",
                "ok": conflict is None,
                "message": "No public host/port conflict."
                if conflict is None
                else f"Conflicts with mapping {conflict.get('id')}.",
            }
        )

        port_ok = public_port in allowed_ports
        checks.append(
            {
                "id": "public-port",
                "ok": port_ok,
                "message": "Public port is allowed." if port_ok else f"Public port must be one of {allowed_ports}.",
            }
        )

        protocol = str(mapping.get("protocol") or "").lower()
        protocol_ok = protocol in allowed_protocols
        checks.append(
            {
                "id": "protocol",
                "ok": protocol_ok,
                "message": "Protocol is allowed." if protocol_ok else f"Protocol must be one of {allowed_protocols}.",
            }
        )

        target = self._target_lookup(config).get(str(mapping.get("targetId") or ""))
        checks.append(
            {
                "id": "target",
                "ok": target is not None,
                "message": "Target service is enabled and allowed." if target else "Target service is not enabled in the allowlist.",
            }
        )

        upstream = str(mapping.get("upstream") or "")
        upstream_ok = valid_upstream(upstream)
        checks.append(
            {
                "id": "upstream",
                "ok": upstream_ok,
                "message": "Target upstream is safe for Nginx generation."
                if upstream_ok
                else "Target upstream must be an http/https service URL without a path.",
            }
        )

        canonical_target_ok = bool(target and mapping_uses_target(mapping, target))
        checks.append(
            {
                "id": "target-canonical",
                "ok": canonical_target_ok,
                "message": "Mapping uses the configured target host, port, protocol, and upstream."
                if canonical_target_ok
                else "Mapping target fields must match the selected target allowlist entry.",
            }
        )

        allowed_target_hosts = [
            normalize_target_host(host)
            for host in gateway_config.get("allowedTargetHosts", [])
            if normalize_target_host(host)
        ]
        target_host = normalize_target_host(target.get("targetHost") if target else mapping.get("targetHost"))
        host_ok = not allowed_target_hosts or target_host in allowed_target_hosts
        checks.append(
            {
                "id": "target-host",
                "ok": host_ok,
                "message": "Target host is reachable through the gateway allowlist."
                if host_ok
                else f"Target host must be one of {allowed_target_hosts}.",
            }
        )

        allowed_team_ids = {
            str(team_id).strip() for team_id in (target or {}).get("allowedTeamIds", []) if str(team_id).strip()
        }
        owner_team_id = str(mapping.get("ownerTeamId") or "").strip()
        team_ok = not allowed_team_ids or owner_team_id in allowed_team_ids
        checks.append(
            {
                "id": "target-team",
                "ok": team_ok,
                "message": "Team is allowed to use this target." if team_ok else "Team is not allowed to use this target.",
            }
        )

        verification = mapping.get("verification") or {}
        if verification.get("status") != "verified":
            warnings.append(
                {
                    "id": "domain-verification",
                    "message": "DNS TXT ownership verification is still pending.",
                    "verification": verification,
                }
            )

        nginx_config = gateway_config.get("nginx", {})
        if not nginx_config.get("testCommand") or not nginx_config.get("reloadCommand"):
            warnings.append(
                {
                    "id": "nginx-commands",
                    "message": "Nginx test/reload command arrays are not configured; live apply will stay disabled.",
                }
            )

        return {"ok": all(check["ok"] for check in checks), "checks": checks, "warnings": warnings}

    def render_nginx_config(self, config: dict[str, Any]) -> str:
        lines = [
            "# Generated by Glimpse monitor agent. Do not edit this file by hand.",
            f"# Generated at {utc_now()}",
            "",
        ]

        active_mappings = [mapping for mapping in config.get("portMappings", []) if mapping.get("status") == "active"]
        if not active_mappings:
            lines.append("# No active member domain mappings.")
            lines.append("")
            return "\n".join(lines)

        for mapping in active_mappings:
            public_host = normalize_public_host(mapping.get("publicHost"))
            public_port = coerce_int(mapping.get("publicPort"), 80)
            upstream = str(mapping.get("upstream") or "")
            if not valid_domain(public_host) or not valid_upstream(upstream):
                continue

            lines.extend(
                [
                    "server {",
                    f"    listen {public_port};",
                    f"    server_name {public_host};",
                    "",
                    "    client_max_body_size 25m;",
                    "",
                    "    location = /nginx-health {",
                    "        access_log off;",
                    '        return 200 "ok\\n";',
                    "    }",
                    "",
                    "    location / {",
                    f"        proxy_pass {upstream};",
                    "        include /etc/nginx/snippets/proxy-headers.conf;",
                    "    }",
                    "}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _target_lookup(self, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        targets: dict[str, dict[str, Any]] = {}
        for target in config.get("domainGateway", {}).get("targets", []):
            target_id = str(target.get("id") or "").strip()
            if target_id and target.get("enabled", True):
                targets[target_id] = target
        return targets

    def _find_mapping(self, config: dict[str, Any], mapping_id: str) -> dict[str, Any] | None:
        for mapping in config.get("portMappings", []):
            if mapping.get("id") == mapping_id:
                return mapping
        return None

    def _unique_mapping_id(self, config: dict[str, Any], public_host: str) -> str:
        base = slug(public_host or "domain-route")
        existing = {mapping.get("id") for mapping in config.get("portMappings", [])}
        candidate = base
        index = 2
        while candidate in existing:
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def _write_test_reload_nginx(self, config: dict[str, Any], rendered_config: str) -> dict[str, Any]:
        nginx_config = config.get("domainGateway", {}).get("nginx", {})
        generated_path = self._nginx_generated_path(config)
        test_command = nginx_config.get("testCommand")
        reload_command = nginx_config.get("reloadCommand")

        if not isinstance(test_command, list) or not isinstance(reload_command, list):
            return {"ok": False, "error": "Nginx test/reload command arrays are not configured."}

        previous = generated_path.read_text(encoding="utf-8") if generated_path.exists() else None
        generated_path.parent.mkdir(parents=True, exist_ok=True)
        generated_path.write_text(rendered_config, encoding="utf-8")

        test_result = run_command(test_command, timeout=20)
        if not test_result["ok"]:
            self._restore_generated_config(generated_path, previous)
            return {
                "ok": False,
                "error": "nginx -t failed; generated config was rolled back.",
                "test": test_result,
                "generatedConfigPath": str(generated_path),
            }

        reload_result = run_command(reload_command, timeout=20)
        if not reload_result["ok"]:
            self._restore_generated_config(generated_path, previous)
            return {
                "ok": False,
                "error": "Nginx reload failed; generated config was rolled back.",
                "test": test_result,
                "reload": reload_result,
                "generatedConfigPath": str(generated_path),
            }

        return {
            "ok": True,
            "generatedConfigPath": str(generated_path),
            "test": test_result,
            "reload": reload_result,
        }

    def _nginx_generated_path(self, config: dict[str, Any]) -> Path:
        raw_path = os.getenv(
            "GLIMPSE_NGINX_GENERATED_CONF_PATH",
            str(config.get("domainGateway", {}).get("nginx", {}).get("generatedConfPath") or ""),
        )
        if not raw_path:
            return DEFAULT_NGINX_GENERATED_CONF_PATH

        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        return (config_path().parent / path).resolve()

    def _restore_generated_config(self, generated_path: Path, previous: str | None) -> None:
        if previous is None:
            generated_path.unlink(missing_ok=True)
        else:
            generated_path.write_text(previous, encoding="utf-8")

    def _append_audit(
        self,
        config: dict[str, Any],
        actor: str | None,
        event_type: str,
        target_type: str,
        target_id: str,
        payload: dict[str, Any],
    ) -> None:
        config.setdefault("auditEvents", []).append(
            {
                "id": f"{now_ms()}-{slug(event_type)}",
                "actor": actor or "local-dashboard",
                "eventType": event_type,
                "targetType": target_type,
                "targetId": target_id,
                "payload": payload,
                "createdAt": utc_now(),
            }
        )


def normalize_public_host(value: Any) -> str:
    host = str(value or "").strip().lower().rstrip(".")
    if host.startswith("http://") or host.startswith("https://") or "/" in host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def valid_domain(host: str) -> bool:
    if not host or len(host) > 253 or "." not in host:
        return False
    if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.endswith(".local"):
        return False
    return all(DOMAIN_LABEL_RE.match(label) for label in host.split("."))


def normalize_target_host(value: Any) -> str:
    return str(value or "").strip().lower().rstrip(".")


def valid_upstream(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return False
    if not parsed.hostname or not SAFE_UPSTREAM_HOST_RE.match(parsed.netloc):
        return False
    if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False

    try:
        port = parsed.port
    except ValueError:
        return False
    return port is None or 1 <= port <= 65535


def target_upstream(target: dict[str, Any]) -> str:
    explicit = str(target.get("upstream") or "").strip()
    if explicit:
        return explicit
    protocol = str(target.get("protocol") or "http").lower()
    return f"{protocol}://{target.get('targetHost')}:{target.get('targetPort')}"


def mapping_uses_target(mapping: dict[str, Any], target: dict[str, Any]) -> bool:
    return (
        str(mapping.get("targetDeviceId") or "") == str(target.get("targetDeviceId") or "")
        and normalize_target_host(mapping.get("targetHost")) == normalize_target_host(target.get("targetHost"))
        and coerce_int(mapping.get("targetPort"), 0) == coerce_int(target.get("targetPort"), -1)
        and str(mapping.get("protocol") or "").lower() == str(target.get("protocol") or "http").lower()
        and str(mapping.get("upstream") or "") == target_upstream(target)
    )
