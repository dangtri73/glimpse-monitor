from __future__ import annotations

import json
from typing import Any

from kafka import KafkaConsumer, KafkaProducer

from .config import Settings


def make_consumer(topic: str, group_id: str, settings: Settings) -> KafkaConsumer:
    return KafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka_brokers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        max_poll_records=settings.clickhouse_batch_size,
    )


def make_producer(settings: Settings) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=settings.kafka_brokers,
        acks="all",
        retries=5,
        linger_ms=10,
        value_serializer=_json_serializer,
        key_serializer=_key_serializer,
    )


def _json_serializer(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _key_serializer(value: str | bytes | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")
