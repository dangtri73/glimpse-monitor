# Prometheus And Grafana Design

## Purpose

Prometheus and Grafana are the metrics and alerting layer for Glimpse Monitor.

Use them for:

- host CPU, RAM, disk, and network metrics
- configured service up/down state
- infrastructure health for Postgres, Redis, Kafka, and ClickHouse
- Kafka consumer lag alerts
- operational dashboards and alert rules

Do not use them for:

- raw API request logs
- request or response bodies
- high-cardinality per-request storage
- semantic RAG
- event replay

## Place In The Architecture

```txt
Monitor agents
  -> /metrics
  -> Prometheus
  -> Grafana dashboards and Prometheus alert rules

Gateway request events
  -> Kafka
  -> ClickHouse/Postgres/Qdrant
  -> AI/RAG and request analytics
```

Prometheus complements Kafka. It does not replace Kafka.

Kafka stores high-volume event streams with buffering and replay. Prometheus scrapes numeric time-series metrics and evaluates alerts.

## Current Base Implementation

Docker Compose includes:

- `prometheus`: scrapes metrics and evaluates alert rules.
- `grafana`: local dashboard UI with provisioned Prometheus datasource.
- `postgres-exporter`: Postgres metrics.
- `redis-exporter`: Redis metrics.
- `kafka-exporter`: Kafka broker/topic/consumer metrics.
- ClickHouse Prometheus endpoint at `clickhouse:9363`.

The monitor agent exposes:

```txt
GET /metrics
```

Current custom metrics:

- `glimpse_agent_up`
- `glimpse_agent_snapshot_generated_at_ms`
- `glimpse_host_cpu_load_percent`
- `glimpse_host_cpu_load1`
- `glimpse_host_cpu_load5`
- `glimpse_host_cpu_load15`
- `glimpse_host_cpu_count`
- `glimpse_host_memory_used_percent`
- `glimpse_host_memory_total_bytes`
- `glimpse_host_memory_used_bytes`
- `glimpse_host_memory_available_bytes`
- `glimpse_host_disk_used_percent`
- `glimpse_host_disk_total_bytes`
- `glimpse_host_disk_free_bytes`
- `glimpse_host_network_rx_bytes_per_second`
- `glimpse_host_network_tx_bytes_per_second`
- `glimpse_host_network_rx_bytes_total`
- `glimpse_host_network_tx_bytes_total`
- `glimpse_service_up`

Per-process metrics are intentionally not exported by default because process IDs and command names create high-cardinality metrics.

## Local Access

Default ports:

```txt
Prometheus: http://127.0.0.1:9090
Grafana:    http://127.0.0.1:3001
```

Default Grafana login:

```txt
user: admin
pass: glimpse
```

Change this in `infra/.env` before long-running deployment.

## Mac Studio Scrape Path

When Prometheus runs in Docker Desktop on Mac Studio and the agent runs on the Mac host:

```txt
prometheus container -> host.docker.internal:8765/metrics
```

For another device, either:

- expose that device agent only on a private network/VPN
- run Prometheus on that device too
- use the agent ingest path for product data and keep Prometheus for Mac Studio infra health

Do not publicly expose `/metrics` through Nginx without authentication.

## Alert Rules

Base rules live at:

```txt
infra/prometheus/rules/glimpse-alerts.yml
```

Current alerts:

- agent down
- high CPU load
- high memory usage
- high disk usage
- configured service down
- Postgres exporter down
- Redis exporter down
- Kafka exporter down
- Kafka consumer lag high

Prometheus evaluates the rules. Alert delivery can be added later with Alertmanager, email, Telegram, Slack, or another webhook.

## Grafana Dashboard

Base dashboard:

```txt
infra/grafana/dashboards/glimpse-overview.json
```

It shows:

- host pressure
- network throughput
- configured service up/down state

This dashboard is for infra/operator visibility. Keep the custom Next.js dashboard for product-specific topology, port mapping, service actions, and AI operator flows.

## Expansion Plan

Add later:

- Alertmanager for external notifications.
- Node exporter if running on Linux hosts.
- Docker/cAdvisor metrics if container-level visibility is needed.
- Nginx exporter for gateway request counters.
- Blackbox exporter for public endpoint uptime checks.
- Grafana dashboards for Kafka, Postgres, ClickHouse, and Qdrant.

For Mac Studio, avoid overloading the stack with every exporter at once. Start with the agent metrics and the core infra exporters already in Compose.
