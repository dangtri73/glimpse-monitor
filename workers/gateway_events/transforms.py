from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

REQUIRED_FIELDS = (
    "eventId",
    "observedAt",
    "gatewayId",
    "requestId",
    "method",
    "host",
    "path",
    "routeTemplate",
    "statusCode",
    "durationMs",
    "upstream",
)

CLICKHOUSE_COLUMNS = [
    "observed_at",
    "event_id",
    "gateway_id",
    "request_id",
    "method",
    "host",
    "path",
    "route_template",
    "query_shape",
    "status_code",
    "status_class",
    "success",
    "duration_ms",
    "latency_bucket",
    "request_bytes",
    "response_bytes",
    "upstream",
    "target_device_id",
    "client_class",
    "user_agent_class",
    "error_class",
    "error_summary",
    "route_key",
    "raw_event",
]


def decode_event(value: bytes | str) -> dict[str, Any]:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("Kafka event must be a JSON object")
    _validate_required(payload)
    return payload


def enrich_gateway_event(event: dict[str, Any]) -> dict[str, Any]:
    _validate_required(event)

    status_code = _int_field(event, "statusCode")
    duration_ms = _int_field(event, "durationMs")
    observed_at = parse_datetime(str(event["observedAt"]))
    route_template = str(event["routeTemplate"])
    gateway_id = str(event["gatewayId"])
    upstream = str(event["upstream"])

    enriched = dict(event)
    enriched["schemaVersion"] = int(event.get("schemaVersion", 1))
    enriched["enrichedAt"] = datetime.now(timezone.utc).isoformat()
    enriched["observedMinute"] = observed_at.replace(second=0, microsecond=0).isoformat()
    enriched["statusCode"] = status_code
    enriched["statusClass"] = f"{status_code // 100}xx"
    enriched["success"] = 200 <= status_code < 400
    enriched["durationMs"] = max(0, duration_ms)
    enriched["latencyBucket"] = latency_bucket(duration_ms)
    enriched["routeKey"] = f"{gateway_id}:{upstream}:{route_template}"
    return enriched


def clickhouse_row(event: dict[str, Any]) -> list[Any]:
    enriched = enrich_gateway_event(event)
    return [
        parse_datetime(str(enriched["observedAt"])),
        str(enriched["eventId"]),
        str(enriched["gatewayId"]),
        str(enriched["requestId"]),
        str(enriched["method"]),
        str(enriched["host"]),
        str(enriched["path"]),
        str(enriched["routeTemplate"]),
        str(enriched.get("queryShape") or "none"),
        int(enriched["statusCode"]),
        str(enriched["statusClass"]),
        bool(enriched["success"]),
        int(enriched["durationMs"]),
        str(enriched["latencyBucket"]),
        _nullable_int(enriched.get("requestBytes")),
        _nullable_int(enriched.get("responseBytes")),
        str(enriched["upstream"]),
        _nullable_string(enriched.get("targetDeviceId")),
        str(enriched.get("clientClass") or "unknown"),
        str(enriched.get("userAgentClass") or "unknown"),
        _nullable_string(enriched.get("errorClass")),
        _nullable_string(enriched.get("errorSummary")),
        str(enriched["routeKey"]),
        json.dumps(enriched, ensure_ascii=False, sort_keys=True),
    ]


def dead_letter_event(
    *,
    source_topic: str,
    consumer_group: str,
    partition: int,
    offset: int,
    error: Exception,
    value: bytes | str | None,
) -> dict[str, Any]:
    if isinstance(value, bytes):
        value_text = value.decode("utf-8", errors="replace")
    else:
        value_text = value

    return {
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "sourceTopic": source_topic,
        "consumerGroup": consumer_group,
        "partition": partition,
        "offset": offset,
        "errorClass": error.__class__.__name__,
        "errorSummary": str(error)[:500],
        "value": value_text[:4000] if value_text else None,
    }


def parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latency_bucket(duration_ms: int) -> str:
    if duration_ms < 100:
        return "lt_100ms"
    if duration_ms < 300:
        return "100_299ms"
    if duration_ms < 1000:
        return "300_999ms"
    if duration_ms < 3000:
        return "1_3s"
    return "gt_3s"


def _validate_required(event: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in event]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _int_field(event: dict[str, Any], field: str) -> int:
    value = event[field]
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def _nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
