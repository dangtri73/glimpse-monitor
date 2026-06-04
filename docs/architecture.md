# Dashboard Monitor Architecture

## Goal

Build a dev gateway dashboard that shows live resource usage, network/device topology, services, gateway port mappings, and an AI operator that can answer questions about current and historical system state.

## Recommended Shape

```txt
Devices / Gateway
  monitor agent
    CPU/RAM/disk/network/process collectors
    service controller allowlist
    Nginx config generator later
    local health endpoints
    optional queue producer

Reliable ingestion
  Redis Streams or NATS JetStream for small gateway deployments
  Kafka only when there are many machines, high event volume, or multiple consumer teams

Storage
  Postgres for devices, services, users, port mappings, audits
  TimescaleDB extension for metric samples and retention policies

Dashboard
  Next.js App Router
  API routes proxy monitor agent or query stored metrics
  charts, topology, service actions, port mapping UX

AI
  LangGraph agent
  tools call live snapshot, recent samples, service status, port mappings, docs/RAG
```

## Why Not Kafka First

Kafka is reliable and powerful, but it is heavy for one dev gateway and a few LAN devices. Start with Redis Streams or NATS JetStream:

- simpler deployment
- good enough persistence and replay
- easier local operations
- lower memory/CPU overhead

Move to Kafka when you need long retention, high throughput, consumer groups across teams, or compatibility with an existing data platform.

## Logstash Fit

Use Logstash or OpenTelemetry Collector for logs and traces. For CPU/RAM/disk/network metrics, a lightweight agent plus queue plus TimescaleDB is simpler. If you later need broad observability, prefer OpenTelemetry Collector because it can route metrics, logs, and traces without locking you into Elastic-only pipelines.

## Realtime Data Flow

MVP:

```txt
Next.js dashboard -> Next.js API route -> local monitor agent -> OS counters
```

Production:

```txt
monitor agent -> queue -> ingestor -> Timescale/Postgres
dashboard -> API -> latest materialized state + timeseries queries
dashboard -> SSE/WebSocket -> live updates
```

The direct MVP is useful immediately. The production path gives reliability when the dashboard is closed or the agent temporarily loses connectivity.

## Data Model

Use Postgres for metadata:

- `devices`
- `services`
- `port_mappings`
- `service_actions`
- `audit_events`

Use TimescaleDB hypertables for metrics:

- `metric_samples`
- `network_interface_samples`
- `process_samples`

See `docs/sql/monitor_schema.sql`.

## Service Control Safety

Service control must live in the local agent, not in browser code.

Rules:

- only allow configured service IDs
- only run explicit command arrays
- do not accept arbitrary shell strings from users
- require login and role checks before dashboard actions
- write audit events for start, stop, restart
- return command result and last known service state

## Port Mapping Safety

Port mapping should be a controlled workflow:

1. User logs in.
2. User requests public host/port to target device/port.
3. Backend validates conflicts and policy.
4. Agent writes generated Nginx config to a staging file.
5. Agent runs `nginx -t`.
6. Agent promotes config and reloads Nginx.
7. System records audit event and rollback file.

Never let the dashboard edit raw Nginx config directly.

## Language Choice

Best long-term system language: Go.

Why:

- single static-ish binary for the gateway
- lower memory overhead than Python
- strong concurrency for polling multiple devices
- good OS/process/network libraries
- easier to run as `systemd` or `launchd`

Best current iteration language: Python.

Why:

- available in this workspace
- fast to prototype collectors
- clean LangGraph/LangChain integration
- good enough for a local dev gateway MVP

Pragmatic path: build the agent behavior in Python now, then port the stable collector/controller interface to Go when gateway service control becomes production-critical.
