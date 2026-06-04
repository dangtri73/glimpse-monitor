from __future__ import annotations

import re
from typing import Any

import clickhouse_connect

from .config import Settings
from .transforms import CLICKHOUSE_COLUMNS

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS gateway_request_logs
(
  observed_at DateTime64(3, 'UTC'),
  event_id String,
  gateway_id LowCardinality(String),
  request_id String,
  method LowCardinality(String),
  host LowCardinality(String),
  path String,
  route_template LowCardinality(String),
  query_shape String,
  status_code UInt16,
  status_class LowCardinality(String),
  success Bool,
  duration_ms UInt32,
  latency_bucket LowCardinality(String),
  request_bytes Nullable(UInt64),
  response_bytes Nullable(UInt64),
  upstream LowCardinality(String),
  target_device_id Nullable(String),
  client_class LowCardinality(String),
  user_agent_class LowCardinality(String),
  error_class Nullable(String),
  error_summary Nullable(String),
  route_key String,
  raw_event String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(observed_at)
ORDER BY (observed_at, gateway_id, route_template, status_code)
TTL toDateTime(observed_at) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192
"""


class ClickHouseRequestLogWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ensure_database()
        self.client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
        )
        self.client.command(CREATE_TABLE_SQL)

    def insert_rows(self, rows: list[list[Any]]) -> None:
        if not rows:
            return
        self.client.insert("gateway_request_logs", rows, column_names=CLICKHOUSE_COLUMNS)

    def _ensure_database(self) -> None:
        database = _safe_identifier(self.settings.clickhouse_database)
        client = clickhouse_connect.get_client(
            host=self.settings.clickhouse_host,
            port=self.settings.clickhouse_port,
            username=self.settings.clickhouse_user,
            password=self.settings.clickhouse_password,
            database="default",
        )
        client.command(f"CREATE DATABASE IF NOT EXISTS `{database}`")


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe ClickHouse identifier: {value}")
    return value
