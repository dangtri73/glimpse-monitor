# Improvements And Next Work

## Already Improved

### Architecture

- Split the system into clear layers: monitor agent, dashboard, ingestion/storage, AI operator, and infra.
- Defined the difference between live-only monitoring and persisted multi-device monitoring.
- Added a two-device design for Dev Gateway and Mac Studio.
- Added a high-volume gateway API traffic flow with Kafka, analytics storage, and AI/RAG.
- Clarified that Kafka is justified for high-volume API traffic, but not required for simple CPU/RAM metrics.
- Clarified that vector DB should store selected summaries and runbooks, not every raw request.
- Added `docs/kafka-knowledge.md` as the beginner Kafka reference for this project.

### Infrastructure

- Expanded Docker Compose from Postgres/Redis only to a fuller free Mac Studio stack:
  - Postgres/TimescaleDB
  - Redis
  - Kafka
  - Kafka UI
  - ClickHouse
  - Qdrant
  - Adminer
  - Postgres backup worker
- Bound infra ports to `127.0.0.1` so DB/Kafka/ClickHouse/Qdrant are not publicly exposed.
- Added persistent Docker volumes for stateful services.
- Added `restart: unless-stopped` to long-running services.
- Added health checks for core services.
- Added Docker log caps to reduce disk-fill risk.
- Added Kafka topic initializer with project topics and retention windows.
- Added `.env.example` for configurable local ports and backup settings.
- Added Prometheus and Grafana as the metrics and alerting base.
- Added Postgres, Redis, and Kafka exporters for Prometheus.
- Added ClickHouse Prometheus metrics endpoint.
- Added provisioned Grafana datasource and starter dashboard.
- Added dashboard API request event producer to publish compact, redacted events to Kafka topic `gateway.requests.raw`.
- Added Kafka consumer workers for `gateway.requests.raw -> gateway.requests.enriched -> ClickHouse gateway_request_logs`.

### Reliability

- Added a Mac Studio reliability and backup plan.
- Added daily Postgres custom-format dump backups.
- Added backup retention settings.
- Added `infra/backups/.gitignore` so database dumps are not committed.
- Added network-loss guidance for remote agents.
- Added local disk spool requirement for failed agent uploads.
- Added power-loss recovery expectations for Docker Compose.

### Security

- Kept all stateful infrastructure local-only by default.
- Recommended SSH tunnels or private VPN for remote admin access.
- Kept service control in the local agent, not the browser.
- Required allowlisted service actions instead of arbitrary shell commands.
- Required request redaction before Kafka/vector DB ingestion.
- Documented sensitive fields that must not be stored or embedded by default.

### AI/RAG

- Added LangGraph tool plan.
- Defined live tools, history tools, log tools, and vector-search tools.
- Defined AI behavior for current facts, trend comparisons, and recommended next actions.
- Added guidance to use local/Ollama-compatible models where private system data is involved.

### Metrics And Alerting

- Added Prometheus scrape config for the monitor agent and infra exporters.
- Added base Prometheus alert rules for agent down, high CPU, high RAM, high disk, service down, exporter down, and Kafka lag.
- Added Grafana provisioning so the dashboard and Prometheus datasource are available on first start.

## Still Missing

### Agent

- Add stable `deviceId` to each agent config and every snapshot.
- Add agent authentication token support.
- Add local SQLite spool for failed uploads.
- Add push mode from agent to ingest API.
- Add remote replay from local spool after network recovery.
- Add agent health metrics for spool depth, last upload time, and failed upload count.
- Add per-device service config instead of global static service config.
- Consider porting the production agent to Go once the interface stabilizes.

### Backend / Ingest

- Add ingest API endpoints:
  - `POST /api/ingest/heartbeat`
  - `POST /api/ingest/metrics`
  - `POST /api/ingest/gateway-request`
- Add agent token validation.
- Add device upsert and heartbeat persistence.
- Add metric sample persistence.
- Add service snapshot persistence.
- Add audit event persistence for service and gateway actions.
- Add ingest API Kafka producers for gateway request events outside the dashboard path.

### Database

- Extend SQL schema with:
  - `agent_tokens`
  - `agent_heartbeats`
  - `service_snapshots`
  - `gateway_request_rollups`
  - `ai_summaries`
  - `vector_sources`
- Enable Timescale hypertables when TimescaleDB is available.
- Add retention policies for high-volume metric tables.
- Add indexes for dashboard queries by `device_id` and time range.

### Kafka / Consumers

- Implement gateway request collector for Nginx/access-log traffic.
- Implement metrics aggregator.
- Implement AI summarizer that creates embedding jobs only for useful events.
- Implement embedding worker for Qdrant or pgvector.
- Implement dead-letter handling and retry policy.

### Dashboard

- Add device selector backed by DB.
- Add per-device latest state.
- Add per-device historical charts.
- Add offline/warning/online state from heartbeat age.
- Add service list filtered by selected device.
- Add gateway traffic charts from rollups.
- Add request analytics views for route, status, latency, and upstream.
- Add user login before service control or port mapping.

### Backup

- Add Qdrant snapshot automation after vector data becomes expensive to regenerate.
- Add ClickHouse backup/export once raw request analytics are important.
- Copy Postgres backups to another machine or external drive.
- Add monthly restore test process.
- Add Mac Studio `launchd` job to run `docker compose up -d` after reboot.
- Add disk usage monitoring and alerts.
- Add Alertmanager for external notifications.
- Add Nginx exporter or log-derived gateway request counters.
- Add blackbox exporter for public endpoint uptime checks.

## Recommended Next Implementation Order

1. Add device identity and agent token config.
2. Add ingest API for heartbeat and metrics.
3. Extend Postgres schema for devices, tokens, heartbeats, metrics, services, and audits.
4. Add local SQLite spool in the agent.
5. Change agents to push metrics to the ingest API.
6. Change dashboard to query DB by selected `deviceId`.
7. Add Kafka gateway request metrics aggregator for rollups.
8. Add dashboard gateway traffic charts backed by ClickHouse and rollups.
9. Add AI summarizer and vector DB ingestion.
10. Add authenticated service control and port mapping workflow.
11. Add Mac Studio `launchd` startup automation.
12. Add Qdrant and ClickHouse backup automation.

## Current Risk Assessment

Low risk:

- Live resource collection on one device.
- Local dashboard demo.
- Local-only infra access through SSH tunnels.
- Postgres metadata backup.

Medium risk:

- One Mac Studio is still a single point of failure.
- Kafka has replication factor `1`.
- ClickHouse and Qdrant are not backed up yet.
- Power loss recovery depends on Docker starting correctly.

High risk until implemented:

- Remote agent network outage without local spool.
- Public gateway request capture without redaction.
- Service control without login and audit logs.
- Raw request body ingestion into Kafka or vector DB.

## Design Position

The architecture is optimized for free local expansion on Mac Studio. It is intentionally not a cloud HA design. It can scale from two devices to more devices by adding agents, Kafka consumers, dashboard queries, and storage workers without changing the core data flow.
