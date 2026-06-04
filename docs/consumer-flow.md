# Gateway Consumer Flow

## Implemented Flow

The current implemented consumer flow is:

```txt
Next.js API routes
  -> Kafka topic gateway.requests.raw
  -> gateway-request-enricher
  -> Kafka topic gateway.requests.enriched
  -> gateway-analytics-writer
  -> ClickHouse table gateway_request_logs
```

This means request events are no longer only buffered in Kafka. They are now copied into ClickHouse for query and dashboard use.

## Services

### gateway-request-enricher

Reads:

```txt
gateway.requests.raw
```

Writes:

```txt
gateway.requests.enriched
gateway.dead-letter
```

Adds:

- `statusClass`
- `success`
- `latencyBucket`
- `routeKey`
- `observedMinute`
- `enrichedAt`

### gateway-analytics-writer

Reads:

```txt
gateway.requests.enriched
```

Writes:

```txt
ClickHouse table: gateway_request_logs
gateway.dead-letter
```

The ClickHouse table is created automatically by the worker.

## ClickHouse Table

Table:

```txt
gateway_request_logs
```

Important columns:

- `observed_at`
- `event_id`
- `gateway_id`
- `request_id`
- `method`
- `host`
- `path`
- `route_template`
- `status_code`
- `status_class`
- `success`
- `duration_ms`
- `latency_bucket`
- `upstream`
- `target_device_id`
- `error_class`
- `route_key`
- `raw_event`

Retention:

```txt
30 days by table TTL
```

## Why Two Consumers

The flow is split into two consumers because each step has a clear responsibility.

```txt
Enricher
  -> validates and normalizes the event
  -> creates stable fields used by all later consumers

Analytics writer
  -> writes queryable rows to ClickHouse
  -> can be replaced or scaled without changing enrichment
```

Later, more consumers can read `gateway.requests.enriched` without changing the dashboard producer:

```txt
metrics-aggregator
ai-summarizer
alert-engine
security-detector
```

## Failure Behavior

If an event cannot be parsed or transformed, the worker writes a dead-letter event to:

```txt
gateway.dead-letter
```

The consumer commits the Kafka offset only after the output write succeeds.

This prevents silent loss during normal failures. Dead-letter events should be checked during development.

## Local Verification

Start infra:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose up -d --build
```

Check workers:

```bash
docker compose ps gateway-request-enricher gateway-analytics-writer
docker compose logs --tail=50 gateway-request-enricher gateway-analytics-writer
```

Trigger dashboard API requests:

```bash
curl http://127.0.0.1:3000/api/monitor/snapshot
curl "http://127.0.0.1:3000/api/monitor/samples?limit=5"
```

Query ClickHouse:

```bash
docker compose exec clickhouse clickhouse-client --user glimpse --password glimpse --database glimpse_gateway --query "SELECT observed_at, method, route_template, status_code, duration_ms FROM gateway_request_logs ORDER BY observed_at DESC LIMIT 10"
```

Check dead letters:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic gateway.dead-letter --from-beginning --max-messages 5
```

## Still Missing

Not implemented yet:

- TimescaleDB/Postgres rollup writer.
- ClickHouse dashboard API routes.
- AI summarizer to `gateway.embedding.jobs`.
- Qdrant embedding worker.
- Alert engine.

Next recommended implementation:

```txt
gateway.requests.enriched
  -> metrics-aggregator
  -> request rollups per minute
  -> dashboard gateway traffic charts
```
