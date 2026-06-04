from __future__ import annotations

import json
import unittest

from gateway_events.transforms import clickhouse_row, decode_event, enrich_gateway_event, latency_bucket


class TransformTests(unittest.TestCase):
    def test_enrich_gateway_event_adds_query_fields(self) -> None:
        event = sample_event(statusCode=502, durationMs=1200)

        enriched = enrich_gateway_event(event)

        self.assertEqual(enriched["statusClass"], "5xx")
        self.assertIs(enriched["success"], False)
        self.assertEqual(enriched["latencyBucket"], "1_3s")
        self.assertEqual(enriched["routeKey"], "dev-gateway:monitor-agent:/api/monitor/snapshot")
        self.assertEqual(enriched["observedMinute"], "2026-06-02T03:30:00+00:00")

    def test_decode_event_rejects_missing_fields(self) -> None:
        payload = {"eventId": "event-1"}

        with self.assertRaisesRegex(ValueError, "missing required fields"):
            decode_event(json.dumps(payload))

    def test_clickhouse_row_maps_expected_columns(self) -> None:
        row = clickhouse_row(sample_event())

        self.assertEqual(row[1], "event-1")
        self.assertEqual(row[4], "GET")
        self.assertEqual(row[9], 200)
        self.assertEqual(row[10], "2xx")
        self.assertIs(row[11], True)
        self.assertEqual(row[13], "lt_100ms")
        self.assertEqual(row[22], "dev-gateway:monitor-agent:/api/monitor/snapshot")

    def test_latency_bucket(self) -> None:
        cases = [
            (99, "lt_100ms"),
            (100, "100_299ms"),
            (300, "300_999ms"),
            (1000, "1_3s"),
            (3000, "gt_3s"),
        ]

        for duration_ms, expected in cases:
            with self.subTest(duration_ms=duration_ms):
                self.assertEqual(latency_bucket(duration_ms), expected)


def sample_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "eventId": "event-1",
        "observedAt": "2026-06-02T03:30:12.000Z",
        "gatewayId": "dev-gateway",
        "requestId": "request-1",
        "method": "GET",
        "host": "localhost:3000",
        "path": "/api/monitor/snapshot",
        "routeTemplate": "/api/monitor/snapshot",
        "queryShape": "none",
        "statusCode": 200,
        "durationMs": 42,
        "requestBytes": None,
        "responseBytes": None,
        "upstream": "monitor-agent",
        "targetDeviceId": None,
        "clientClass": "browser",
        "errorClass": None,
        "errorSummary": None,
        "userAgentClass": "chrome",
    }
    event.update(overrides)
    return event


if __name__ == "__main__":
    unittest.main()
