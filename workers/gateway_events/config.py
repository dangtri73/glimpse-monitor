from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    kafka_brokers: list[str]
    raw_topic: str
    enriched_topic: str
    dead_letter_topic: str
    enricher_group_id: str
    analytics_group_id: str
    kafka_send_timeout_seconds: float
    kafka_poll_timeout_ms: int
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_database: str
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_batch_size: int


def load_settings() -> Settings:
    brokers = [
        broker.strip()
        for broker in os.getenv("KAFKA_BROKERS", "kafka:9092").split(",")
        if broker.strip()
    ]
    if not brokers:
        raise ValueError("KAFKA_BROKERS must contain at least one broker")

    return Settings(
        kafka_brokers=brokers,
        raw_topic=os.getenv("KAFKA_RAW_TOPIC", "gateway.requests.raw"),
        enriched_topic=os.getenv("KAFKA_ENRICHED_TOPIC", "gateway.requests.enriched"),
        dead_letter_topic=os.getenv("KAFKA_DEAD_LETTER_TOPIC", "gateway.dead-letter"),
        enricher_group_id=os.getenv("KAFKA_ENRICHER_GROUP_ID", "gateway-request-enricher"),
        analytics_group_id=os.getenv("KAFKA_ANALYTICS_GROUP_ID", "gateway-analytics-writer"),
        kafka_send_timeout_seconds=_float_env("KAFKA_SEND_TIMEOUT_SECONDS", 10.0),
        kafka_poll_timeout_ms=_int_env("KAFKA_POLL_TIMEOUT_MS", 1000),
        clickhouse_host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        clickhouse_port=_int_env("CLICKHOUSE_PORT", 8123),
        clickhouse_database=os.getenv("CLICKHOUSE_DB", "glimpse_gateway"),
        clickhouse_user=os.getenv("CLICKHOUSE_USER", "glimpse"),
        clickhouse_password=os.getenv("CLICKHOUSE_PASSWORD", "glimpse"),
        clickhouse_batch_size=_int_env("CLICKHOUSE_BATCH_SIZE", 500),
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed
