# Glimpse Monitor

Gateway and device monitoring slice for the Glimpse workspace.

## What Is Included

- `agent/`: local Python monitor agent for CPU, RAM, SSD, network counters, process list, services, devices, and port mapping metadata.
- `ai-service/`: basic Ollama-backed chatbot service, separated from the monitor agent.
- `dashboard/`: Next.js dashboard with topology-first UX, live charts, service controls, port mapping view, and an AI assistant shell.
- `workers/`: Kafka consumer workers for gateway request enrichment and ClickHouse analytics writes.
- `docs/`: architecture, AI tool wiring, and storage schema.
- `infra/`: optional local Postgres/Redis compose file for the production ingestion path.
- `nginx-docker/`: Dockerized Nginx gateway deployed to the dev server.

## Run Local Development

Start the resource agent:

```bash
python3 glimpse-monitor/agent/server.py
```

Start the dashboard:

```bash
cd glimpse-monitor/dashboard
npm install
npm run dev
```

Open `http://localhost:3000`.

## Run Infrastructure

Start the local/private infrastructure stack:

```bash
cd glimpse-monitor/infra
docker compose up -d --build
```

Default local ports:

- Postgres/TimescaleDB: `127.0.0.1:5433`
- Redis: `127.0.0.1:6380`
- Kafka external listener: `127.0.0.1:9094`
- Kafka UI: `http://127.0.0.1:8082`
- ClickHouse HTTP: `http://127.0.0.1:8123`
- ClickHouse native: `127.0.0.1:9000`
- Qdrant HTTP: `http://127.0.0.1:6333`
- Qdrant gRPC: `127.0.0.1:6334`
- Adminer: `http://127.0.0.1:8081`
- AI service: `http://127.0.0.1:8771`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3001`

Ports are bound to `127.0.0.1` so deploying this on Mac Studio does not expose DB/Kafka/ClickHouse/Qdrant publicly. Use SSH tunnels from a local device when remote admin access is needed.

## GitHub Actions

This repo uses service-level path filters:

- `.github/workflows/app-services.yml` builds and deploys `dashboard`, `ai-service`, and `workers` on Mac Studio.
- `.github/workflows/nginx-docker.yml` builds `nginx-docker` and deploys it to the dev server.

Both workflows use the Mac Studio self-hosted runner labels `self-hosted`, `macOS`, `ARM64`, and `macstudio`.

Common runner commands are in `docs/github-actions-runner.md`.

## Recommendation

Use Python now for fast iteration and AI/LangGraph integration. Use Go later for the privileged gateway daemon once service control and Nginx port mapping become production features.

## Design Docs

- `docs/architecture.md`: overall monitor architecture.
- `docs/two-device-monitoring.md`: recommended two-device collection, ingest, DB, dashboard, and AI design.
- `docs/kafka-knowledge.md`: beginner Kafka guide, Glimpse benefits, storage limits, replay, consumers, and safety rules.
- `docs/consumer-flow.md`: implemented Kafka consumer flow from raw requests to enriched events and ClickHouse logs.
- `docs/ai-chatbot.md`: basic Ollama chatbot service, dashboard chat wiring, and later RAG plan.
- `docs/gateway-api-traffic-rag.md`: high-volume gateway API traffic, Kafka, analytics storage, vector DB, and AI/RAG flow.
- `docs/prometheus-grafana.md`: Prometheus/Grafana metrics, exporters, alert rules, and dashboard placement.
- `docs/reliability-backup.md`: Mac Studio reliability limits, restart behavior, backup priorities, and recovery plan.
- `docs/improvements.md`: completed improvements, missing work, risks, and recommended implementation order.
- `docs/start-stop.md`: local start, stop, restart, reset, health check, and SSH tunnel commands.
- `docs/github-actions-runner.md`: Mac Studio GitHub Actions runner service, logs, Docker checks, and rerun commands.
- `docs/nginx-docker-gateway.md`: dev-server Docker Nginx gateway usage, cert copy, Cloudflare SSL, and curl tests.
- `docs/nginx-cert-management.md`: dev-server certificate add, update, remove, validate, and reload workflow.
- `docs/dockerhub-deploy.md`: Docker Hub build/push scripts and Mac Studio pull/run deployment.
- `docs/ai-tools.md`: LangGraph tool plan.
- `docs/sql/monitor_schema.sql`: baseline monitor schema.
