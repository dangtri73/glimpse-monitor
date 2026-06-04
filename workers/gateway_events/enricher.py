from __future__ import annotations

import logging

from .config import load_settings
from .kafka_io import make_consumer, make_producer
from .transforms import dead_letter_event, decode_event, enrich_gateway_event

LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("kafka").setLevel(logging.WARNING)
    settings = load_settings()
    consumer = make_consumer(settings.raw_topic, settings.enricher_group_id, settings)
    producer = make_producer(settings)

    LOGGER.info("gateway request enricher started topic=%s group=%s", settings.raw_topic, settings.enricher_group_id)

    for message in consumer:
        try:
            event = decode_event(message.value)
            enriched = enrich_gateway_event(event)
            key = message.key or f"{enriched['gatewayId']}:{enriched['routeTemplate']}"
            producer.send(
                settings.enriched_topic,
                key=key,
                value=enriched,
                headers=[("event_type", b"gateway.request.enriched"), ("schema_version", b"1")],
            ).get(timeout=settings.kafka_send_timeout_seconds)
        except Exception as error:
            LOGGER.exception("failed to enrich gateway request partition=%s offset=%s", message.partition, message.offset)
            producer.send(
                settings.dead_letter_topic,
                key=f"{settings.raw_topic}:{message.partition}:{message.offset}",
                value=dead_letter_event(
                    source_topic=settings.raw_topic,
                    consumer_group=settings.enricher_group_id,
                    partition=message.partition,
                    offset=message.offset,
                    error=error,
                    value=message.value,
                ),
                headers=[("event_type", b"gateway.dead_letter"), ("schema_version", b"1")],
            ).get(timeout=settings.kafka_send_timeout_seconds)

        consumer.commit()
