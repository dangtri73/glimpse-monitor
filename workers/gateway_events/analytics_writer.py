from __future__ import annotations

import logging

from .clickhouse import ClickHouseRequestLogWriter
from .config import load_settings
from .kafka_io import make_consumer, make_producer
from .transforms import clickhouse_row, dead_letter_event, decode_event

LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("kafka").setLevel(logging.WARNING)
    settings = load_settings()
    writer = ClickHouseRequestLogWriter(settings)
    consumer = make_consumer(settings.enriched_topic, settings.analytics_group_id, settings)
    producer = make_producer(settings)

    LOGGER.info(
        "gateway analytics writer started topic=%s group=%s table=gateway_request_logs",
        settings.enriched_topic,
        settings.analytics_group_id,
    )

    while True:
        polled = consumer.poll(timeout_ms=settings.kafka_poll_timeout_ms, max_records=settings.clickhouse_batch_size)
        if not polled:
            continue

        rows = []
        dead_letters = []

        for messages in polled.values():
            for message in messages:
                try:
                    event = decode_event(message.value)
                    rows.append(clickhouse_row(event))
                except Exception as error:
                    LOGGER.exception(
                        "failed to transform enriched request partition=%s offset=%s",
                        message.partition,
                        message.offset,
                    )
                    dead_letters.append(
                        dead_letter_event(
                            source_topic=settings.enriched_topic,
                            consumer_group=settings.analytics_group_id,
                            partition=message.partition,
                            offset=message.offset,
                            error=error,
                            value=message.value,
                        )
                    )

        writer.insert_rows(rows)

        for item in dead_letters:
            producer.send(
                settings.dead_letter_topic,
                key=f"{item['sourceTopic']}:{item['partition']}:{item['offset']}",
                value=item,
                headers=[("event_type", b"gateway.dead_letter"), ("schema_version", b"1")],
            ).get(timeout=settings.kafka_send_timeout_seconds)

        consumer.commit()
        LOGGER.info("processed gateway events rows=%s dead_letters=%s", len(rows), len(dead_letters))
