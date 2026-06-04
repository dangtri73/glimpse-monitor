# Gateway API Traffic, Kafka, And AI/RAG Flow

## Goal

Collect high-volume API request traffic from the dev gateway, store it reliably, expose operational charts, and let an AI agent answer system questions using metrics, logs, incidents, and runbooks.

Kafka is justified for this flow because request traffic can be high volume and has multiple downstream consumers.

If Kafka is new to you, read `docs/kafka-knowledge.md` first. It explains topics, producers, consumers, replay, retention, sizing, and why Kafka is useful for Glimpse.

## Core Principle

Do not write all gateway request traffic directly to a vector database.

Use Kafka as the event backbone, store raw/structured traffic in an analytics store, store time-series aggregates in TimescaleDB/Postgres, and send only selected/summarized/redacted records to the vector database.

## Recommended Flow

```txt
Gateway / Nginx / API middleware
  -> structured request event
  -> Kafka topic: gateway.requests.raw
  -> consumers:
      1. request enricher
      2. metrics aggregator
      3. analytics log writer
      4. AI summarizer and embedding job creator
      5. alert engine
```

## Current Base Implementation

The Next.js dashboard now includes a fail-open Kafka producer for API route traffic.

Implemented producer:

```txt
dashboard/app/lib/gateway-events.ts
```

Wrapped routes:

```txt
/api/monitor/snapshot
/api/monitor/samples
/api/monitor/services
/api/monitor/services/[serviceId]/[action]
/api/monitor/port-maps
/api/ai/system
```

These routes publish compact request events to `gateway.requests.raw` after the handler finishes. Publishing is disabled unless `KAFKA_BROKERS` is configured, so the dashboard can still run without Kafka.

Local dashboard environment:

```env
MONITOR_AGENT_URL=http://127.0.0.1:8765
GATEWAY_ID=dev-gateway
GATEWAY_REQUEST_EVENTS_ENABLED=true
KAFKA_BROKERS=127.0.0.1:9094
KAFKA_CLIENT_ID=glimpse-dashboard
KAFKA_GATEWAY_REQUEST_TOPIC=gateway.requests.raw
KAFKA_PUBLISH_TIMEOUT_MS=75
```

The producer does not read request bodies. Query values are reduced to shape only, for example `limit=redacted`.

Current consumer implementation:

```txt
gateway.requests.raw
  -> gateway-request-enricher
  -> gateway.requests.enriched
  -> gateway-analytics-writer
  -> ClickHouse table gateway_request_logs
```

See `docs/consumer-flow.md` for worker details and verification commands.

Detailed flow:

```txt
Nginx/API logs
  -> gateway collector
  -> redact sensitive fields
  -> gateway.requests.raw

gateway.requests.raw
  -> enricher
  -> add service name, route template, latency bucket, trace id, geo/client class
  -> gateway.requests.enriched

gateway.requests.enriched
  -> metrics aggregator
  -> gateway.metrics.rollup
  -> TimescaleDB/Postgres

gateway.requests.enriched
  -> analytics writer
  -> ClickHouse/OpenSearch/Postgres partitioned logs

gateway.requests.enriched
  -> AI filter/summarizer
  -> gateway.embedding.jobs
  -> embed selected summaries
  -> vector DB

gateway.requests.enriched
  -> alert engine
  -> gateway.alerts
```

## Storage Responsibilities

### Kafka

Use Kafka for:

- high-volume request event buffering
- replay after consumer bugs
- decoupling gateway collection from DB/vector writes
- multiple consumer groups
- dead-letter handling

Kafka is the transport and replay layer, not the final query database.

### Postgres

Use Postgres for:

- devices
- services
- users
- port mappings
- audit events
- AI conversations
- agent tokens
- request processing checkpoints if needed

### TimescaleDB

Use TimescaleDB for time-series aggregates:

- requests per route per minute
- p50/p95/p99 latency
- status-code counts
- upstream error rate
- service availability
- resource metrics from monitor agents

### ClickHouse Or Search Store

Use ClickHouse when traffic is high and analytical queries matter:

- raw or enriched request logs
- route/service/error breakdowns
- high-cardinality filtering
- fast time-window queries

Use OpenSearch if full-text log search is more important than analytical speed.

Use partitioned Postgres only for MVP or low/medium traffic.

### Vector DB

Use vector DB for semantic retrieval over selected knowledge:

- incident summaries
- normalized error summaries
- unusual traffic summaries
- runbooks
- deployment notes
- Nginx/gateway config explanations
- AI-generated daily/hourly summaries

Do not embed every raw request.

## Sensitive Data Rules

Never store or embed these fields without explicit policy:

- passwords
- bearer tokens
- cookies
- authorization headers
- API keys
- full request bodies
- full response bodies
- payment data
- private user PII

Redact before Kafka when possible. If raw data must enter Kafka, keep it in a restricted topic with short retention and strict access control.

Recommended event fields:

```json
{
  "eventId": "01J...",
  "observedAt": "2026-06-02T09:00:00Z",
  "gatewayId": "dev-gateway",
  "requestId": "req_...",
  "traceId": "trace_...",
  "method": "POST",
  "host": "dev.api.hftvn.com",
  "path": "/api/chat/messages",
  "routeTemplate": "/api/chat/messages",
  "queryShape": "redacted",
  "statusCode": 200,
  "durationMs": 184,
  "requestBytes": 1240,
  "responseBytes": 8021,
  "upstream": "ollama",
  "targetDeviceId": "mac-studio",
  "clientClass": "browser",
  "errorClass": null,
  "errorSummary": null
}
```

## Kafka Topics

Start with:

```txt
gateway.requests.raw
gateway.requests.enriched
gateway.metrics.rollup
gateway.embedding.jobs
gateway.alerts
gateway.dead-letter
```

Optional later:

```txt
gateway.security.events
gateway.nginx.config-events
gateway.service.actions
gateway.incident.summaries
```

## Consumer Responsibilities

### Request Enricher

Reads `gateway.requests.raw`.

Adds:

- route template
- upstream service
- target device
- latency bucket
- normalized error class
- trace correlation

Writes `gateway.requests.enriched`.

### Metrics Aggregator

Reads `gateway.requests.enriched`.

Writes rollups:

- request count per route/service/minute
- status counts
- p50/p95/p99 latency
- error rate
- upstream/device pressure correlation

Writes to `gateway.metrics.rollup` and TimescaleDB.

### Analytics Writer

Reads `gateway.requests.enriched`.

Writes searchable logs to ClickHouse, OpenSearch, or partitioned Postgres.

### AI Summarizer

Reads `gateway.requests.enriched`.

Only creates embedding jobs for useful records:

- 5xx errors
- slow requests
- repeated error patterns
- route anomalies
- gateway config changes
- service action events
- hourly/daily summaries

Writes `gateway.embedding.jobs`.

### Embedding Worker

Reads `gateway.embedding.jobs`.

Creates embeddings and stores:

- vector
- summary text
- source event IDs
- time range
- service/device/route metadata
- severity

### Alert Engine

Reads enriched requests and rollups.

Triggers alerts when:

- error rate crosses threshold
- p95 latency exceeds threshold
- upstream unavailable
- gateway-to-device route fails
- traffic anomaly detected

## AI Agent Query Flow

The AI agent should not answer only from vector DB. It should combine tools:

```txt
User asks question
  -> LangGraph planner
  -> query live device state
  -> query TimescaleDB metrics
  -> query analytics logs by filters
  -> search vector DB for related summaries/runbooks
  -> synthesize answer with source references
```

Example tools:

- `get_system_snapshot(deviceId)`
- `query_gateway_metrics(from, to, route, service)`
- `query_request_logs(from, to, filters)`
- `search_incident_summaries(query)`
- `search_runbooks(query)`
- `get_port_mappings()`
- `get_service_status(deviceId)`

## Example AI Questions

Questions answered from metrics:

- "Compare gateway traffic between the last two hours."
- "Which route had the worst p95 latency today?"
- "Did Mac Studio CPU increase when Ollama traffic increased?"

Questions answered from logs plus summaries:

- "Why did users get 502 errors this morning?"
- "Which upstream caused the most gateway failures?"
- "Show examples of slow requests to the Ollama route."

Questions answered from RAG:

- "How should I fix this Nginx upstream timeout?"
- "What changed before latency increased?"
- "What is the safest rollback for the public Ollama mapping?"

## MVP Order

1. Add structured gateway request events. Done for the Next.js dashboard API routes.
2. Add Kafka with `gateway.requests.raw`. Done in Docker Compose.
3. Add request enricher and `gateway.requests.enriched`. Done.
4. Write enriched logs to ClickHouse. Done.
5. Write rollups to TimescaleDB/Postgres.
6. Add AI summarizer for errors, slow requests, and hourly summaries.
7. Add vector DB for summaries and runbooks.
8. Add LangGraph tools that query metrics, logs, vector DB, and live device state.

## Practical Recommendation

Use Kafka now if gateway API traffic is high or if losing/replaying request events matters.

Use this initial stack:

```txt
Kafka
Postgres + TimescaleDB
ClickHouse for request analytics
pgvector for initial vector search
LangGraph for AI tool orchestration
```

Move from `pgvector` to Qdrant when semantic search volume, filtering, or retrieval latency becomes a real bottleneck.
