# Kafka Knowledge For Glimpse

## What Kafka Is

Kafka is an event log.

Applications write events to Kafka topics. Other applications read those events later.

In Glimpse, a gateway request event means:

```txt
An API request happened
  -> method, path, route, status, duration, upstream, timestamp
  -> written to Kafka
  -> consumed by workers for storage, charts, alerts, and AI summaries
```

Kafka is not the final database. It is the reliable buffer and replay layer between producers and storage/AI workers.

## Why Kafka Benefits This Project

Glimpse needs to collect gateway API traffic. This traffic can become much larger than CPU/RAM metrics.

Kafka helps because:

- It protects the gateway from slow databases.
- It allows many consumers to process the same traffic independently.
- It keeps a replay window when a consumer has a bug or is offline.
- It absorbs traffic spikes better than direct database writes.
- It separates collection from processing.
- It gives clear backpressure through consumer lag.

Without Kafka:

```txt
Gateway request
  -> write directly to DB/vector DB
  -> if DB is slow, gateway is affected
  -> if AI worker breaks, data may be lost
  -> adding new processors requires changing the gateway path
```

With Kafka:

```txt
Gateway request
  -> write compact event to Kafka
  -> gateway returns quickly
  -> independent consumers process when ready
  -> failed consumers can replay while data is still retained
```

## Current Glimpse Flow

Current implemented flow:

```txt
Next.js API routes
  -> dashboard/app/lib/gateway-events.ts
  -> Kafka topic gateway.requests.raw
  -> gateway-request-enricher
  -> Kafka topic gateway.requests.enriched
  -> gateway-analytics-writer
  -> ClickHouse table gateway_request_logs
```

Not implemented yet:

```txt
gateway.requests.enriched
  -> TimescaleDB/Postgres metrics rollups
  -> selected AI summaries
  -> Qdrant
```

So today Kafka receives request events and ClickHouse stores queryable request logs. Postgres rollups and Qdrant AI summaries are still future work.

## Kafka Terms

### Broker

A Kafka server.

In local Glimpse, the Mac Studio runs one Kafka broker in Docker.

### Topic

A named stream of events.

Current important topic:

```txt
gateway.requests.raw
```

This stores raw structured gateway request events.

### Producer

Code that writes events to Kafka.

Current producer:

```txt
dashboard/app/lib/gateway-events.ts
```

Important: the browser client does not produce directly to Kafka. The Next.js server produces the event after handling the API request.

### Consumer

Code that reads events from Kafka.

Recommended Glimpse consumers:

```txt
request-enricher
metrics-aggregator
analytics-writer
ai-summarizer
embedding-worker
alert-engine
```

### Consumer Group

A named group of consumers that share work.

Example:

```txt
analytics-writer group
  -> reads every gateway request once
  -> writes rows to ClickHouse

metrics-aggregator group
  -> also reads every gateway request once
  -> writes rollups to TimescaleDB/Postgres
```

Different consumer groups each get their own full copy of the stream.

### Partition

A topic is split into partitions for throughput.

Current Glimpse topics use:

```txt
partitions = 6
```

Ordering is only guaranteed inside one partition. If strict order matters for a device or route, use a stable message key like `gatewayId:routeTemplate` or `deviceId`.

### Offset

An offset is the position of a message inside a partition.

Consumers commit offsets so Kafka knows what each consumer group already processed.

### Retention

Kafka deletes old messages after a configured time or size.

Current Glimpse raw request topic:

```txt
gateway.requests.raw retention = 1 day
```

That means replay is possible only while the event is still inside the retention window.

### Replay

Replay means reading old Kafka messages again.

Useful when:

- a consumer had a bug
- ClickHouse was down
- a new summarizer needs historical events
- you want to rebuild rollups

Replay is limited by retention.

### Buffering

Buffering means Kafka accepts events now and consumers process later.

Example:

```txt
ClickHouse is slow for 10 minutes
  -> gateway still writes events to Kafka
  -> analytics-writer falls behind
  -> when ClickHouse recovers, analytics-writer catches up
```

The difference between producer speed and consumer speed is called consumer lag.

## How Much Data Kafka Can Hold

Kafka can hold as much data as the disk and retention settings allow.

Rough formula:

```txt
storage per day = event size * requests per second * 86,400
```

Examples:

```txt
1 KB/event * 100 req/s   = about 8.6 GB/day
1 KB/event * 1,000 req/s = about 86 GB/day
5 KB/event * 1,000 req/s = about 432 GB/day
```

Glimpse request events should stay compact. Do not store request bodies or response bodies in Kafka by default.

Current risk: the compose stack uses time retention but does not yet set a strict per-topic `retention.bytes`. If traffic becomes high, add size retention so Kafka cannot fill the Mac Studio disk.

Recommended raw request topic settings for local Mac Studio:

```txt
retention.ms=86400000
retention.bytes=<safe disk budget>
cleanup.policy=delete
```

## Is Kafka Safe Storage

Kafka is durable enough for buffering, but not enough as the only source of truth in this local setup.

Current local setup:

```txt
broker count = 1
replication factor = 1
local Docker volume
```

This means:

- If Kafka restarts normally, messages remain.
- If the Kafka volume is deleted, messages are gone.
- If the Mac Studio disk fails, messages are gone.
- If retention expires, messages are gone.

So important data must be copied from Kafka into query storage quickly:

```txt
ClickHouse for request logs
TimescaleDB/Postgres for rollups and metadata
Qdrant for selected AI summaries
```

## Is Kafka Easy To Query

No.

Kafka is easy to consume in order, but it is not easy to query by filters.

Bad fit for Kafka:

```txt
Show p95 latency by route for the last 6 hours
Find 502 errors for /api/chat today
Compare traffic between two hours
Search requests by upstream service
Ask AI to cite relevant incidents
```

Good fit:

```txt
Read every event in order
Replay events from an offset
Fan out the same stream to many workers
Buffer when a database is temporarily slow
```

Dashboard and AI should query ClickHouse/Postgres/Qdrant, not Kafka.

## Security Rules

Kafka should stay internal.

For Glimpse:

- Do not expose Kafka through the public dev gateway.
- Keep Kafka bound to `127.0.0.1` or a private network.
- Do not let browsers produce directly to Kafka.
- Remote devices should send data to an authenticated ingest API.
- The ingest API validates, rate limits, redacts, then produces to Kafka.

If direct remote Kafka access is ever required, use:

```txt
private VPN
SASL/SCRAM or mTLS
topic ACLs
separate producer credentials per device/service
```

For current local development, unauthenticated Kafka is acceptable only because it is bound to localhost.

## What Should Go Into Kafka

Allowed by default:

- request metadata
- route template
- query shape, not query values
- status code
- duration
- upstream name
- target device ID
- normalized error class
- small error summary

Avoid by default:

- authorization headers
- cookies
- bearer tokens
- API keys
- passwords
- full request bodies
- full response bodies
- private user PII

## Recommended Glimpse Topics

Current base topics:

```txt
gateway.requests.raw
gateway.requests.enriched
gateway.metrics.rollup
gateway.embedding.jobs
gateway.alerts
gateway.dead-letter
```

Later topics:

```txt
gateway.security.events
gateway.nginx.config-events
gateway.service.actions
gateway.incident.summaries
```

## Recommended Consumers

Recommended location:

```txt
glimpse-monitor/workers/
```

Workers:

```txt
request-enricher
  reads: gateway.requests.raw
  writes: gateway.requests.enriched

analytics-writer
  reads: gateway.requests.enriched
  writes: ClickHouse gateway_request_logs

metrics-aggregator
  reads: gateway.requests.enriched
  writes: TimescaleDB/Postgres rollups

ai-summarizer
  reads: gateway.requests.enriched
  writes: gateway.embedding.jobs

embedding-worker
  reads: gateway.embedding.jobs
  writes: Qdrant

alert-engine
  reads: gateway.requests.enriched and gateway.metrics.rollup
  writes: alerts and notifications
```

Use Python first because Glimpse already uses Python for agent and AI/LangGraph work. Move hot-path consumers to Go later only if Python cannot keep up.

## Local Commands

List topics:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```

Read gateway request events:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic gateway.requests.raw --from-beginning --max-messages 5
```

Describe a topic:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic gateway.requests.raw
```

Open Kafka UI:

```txt
http://127.0.0.1:8082
```

## Practical Rule

Use Kafka for movement, buffering, and replay.

Use databases for querying.

For Glimpse, the correct long-term flow is:

```txt
Gateway/API events
  -> Kafka
  -> consumers
  -> ClickHouse/Postgres/Qdrant
  -> dashboard charts and AI answers
```
