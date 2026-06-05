# Start And Stop Guide

## Start Everything Locally

Run from the repository root:

```bash
cd /Users/vutri/Desktop/projects/Glimpse
```

### 1. Start The Monitor Agent

Open terminal 1:

```bash
python3 glimpse-monitor/agent/server.py
```

The agent listens on:

```txt
http://127.0.0.1:8765
```

Check it:

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/metrics | head
```

### 2. Configure Ollama

If Ollama runs directly on the Mac host, the default Compose value works:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:270m
```

If Ollama is exposed through the dev gateway, set this in `glimpse-monitor/infra/.env`:

```env
OLLAMA_BASE_URL=https://dev.api.hftvn.com/ai
OLLAMA_MODEL=gemma3
```

### 3. Start Infrastructure

Open terminal 2:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose up -d --build
```

Check containers:

```bash
docker compose ps
```

Check AI service:

```bash
curl http://127.0.0.1:8771/health
```

The infra command also starts the gateway consumer workers:

```txt
dashboard
gateway-request-enricher
gateway-analytics-writer
```

The dashboard is available from Compose at:

```txt
http://127.0.0.1:3000
```

### 4. Optional: Start The Next.js Dashboard For Development

Use this when editing dashboard code locally. If the Compose dashboard is already using port `3000`, either stop it first or use another port.

Open terminal 3:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/dashboard
npm install
cp .env.example .env.local
npm run dev
```

Open:

```txt
http://localhost:3000
```

## Local URLs

```txt
Dashboard:   http://localhost:3000
Agent:       http://127.0.0.1:8765
AI service:  http://127.0.0.1:8771
Prometheus:  http://127.0.0.1:9090
Grafana:     http://127.0.0.1:3001
Kafka UI:    http://127.0.0.1:8082
Adminer:     http://127.0.0.1:8081
Qdrant:      http://127.0.0.1:6333/dashboard
ClickHouse:  http://127.0.0.1:8123
```

Grafana login:

```txt
admin / glimpse
```

## Quick Health Checks

Prometheus targets:

```txt
http://127.0.0.1:9090/targets
```

Prometheus queries:

```txt
glimpse_agent_up
glimpse_host_cpu_load_percent
glimpse_service_up
```

Kafka topics:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```

Gateway request events:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic gateway.requests.raw --from-beginning --max-messages 5
```

Enriched gateway request events:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic gateway.requests.enriched --from-beginning --max-messages 5
```

Trigger events by opening the dashboard or calling:

```bash
curl http://127.0.0.1:3000/api/monitor/snapshot
curl "http://127.0.0.1:3000/api/monitor/samples?limit=5"
```

AI chat through dashboard API:

```bash
curl -s http://127.0.0.1:3000/api/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi"}'
```

Streaming AI chat:

```bash
curl -N http://127.0.0.1:3000/api/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi","stream":true}'
```

ClickHouse request logs:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose exec clickhouse clickhouse-client --user glimpse --password glimpse --database glimpse_gateway --query "SELECT observed_at, method, route_template, status_code, duration_ms FROM gateway_request_logs ORDER BY observed_at DESC LIMIT 10"
```

Consumer worker logs:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose logs --tail=50 gateway-request-enricher gateway-analytics-writer
```

Postgres backup logs:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose logs --tail=50 postgres-backup
```

## Stop

Stop the dashboard:

```txt
Press Ctrl+C in the dashboard terminal.
```

If using the Compose dashboard:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose stop dashboard
```

Stop the agent:

```txt
Press Ctrl+C in the agent terminal.
```

Stop infra containers but keep data:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose stop
```

Stop and remove infra containers but keep named volumes:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose down
```

## Restart

Restart infra:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose restart
```

Restart one service:

```bash
docker compose restart prometheus
docker compose restart grafana
docker compose restart kafka
docker compose restart postgres
docker compose restart dashboard
docker compose restart ai-service
docker compose restart gateway-request-enricher
docker compose restart gateway-analytics-writer
```

## Reset Data

This removes infra containers and named volumes. Use only when you want a clean local environment.

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose down -v
```

Local Postgres backup files under `infra/backups/postgres` are not removed by `docker compose down -v`.

## Docker Hub Build And Deploy

Use this when you want to build a specific Glimpse service locally, push it to Docker Hub, then pull/run it on Mac Studio.

Custom image names:

```txt
dashboard   -> dangtri73/glimpse-monitor-dashboard:<tag>
ai-service  -> dangtri73/glimpse-monitor-ai-service:<tag>
workers     -> dangtri73/glimpse-monitor-workers:<tag>
```

Build and push one service:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor
docker login

DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
./scripts/docker-build-push.sh ai-service
```

Build and push all custom services:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor

DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
./scripts/docker-build-push.sh all
```

For Mac Studio, keep the default platform:

```env
DOCKER_PLATFORM=linux/arm64
```

For an Intel server, override:

```bash
DOCKER_PLATFORM=linux/amd64 \
DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
./scripts/docker-build-push.sh all
```

## Mac Studio Pull And Run

On Mac Studio, create or update:

```txt
/Users/admin/glimpse-monitor-runtime/.env
```

Minimum Docker Hub deploy env:

```env
DOCKERHUB_NAMESPACE=dangtri73
IMAGE_TAG=local-latest
IMAGE_PREFIX=glimpse-monitor
POSTGRES_INIT_SQL=/Users/admin/glimpse-monitor-runtime/sql/monitor_schema.sql

DASHBOARD_IMAGE=dangtri73/glimpse-monitor-dashboard:local-latest
AI_SERVICE_IMAGE=dangtri73/glimpse-monitor-ai-service:local-latest
WORKERS_IMAGE=dangtri73/glimpse-monitor-workers:local-latest
```

Important runtime env:

```env
DASHBOARD_PORT=3000
MONITOR_AGENT_URL=http://host.docker.internal:8765
AI_SERVICE_URL=http://ai-service:8770
AI_CHAT_MODEL=gemma3:270m
AI_CHAT_TIMEOUT_MS=70000

AI_SERVICE_HOST_PORT=8771
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:270m
OLLAMA_TIMEOUT_SECONDS=60
```

Use strong local passwords on Mac Studio:

```env
POSTGRES_PASSWORD=change-me
CLICKHOUSE_PASSWORD=change-me
GRAFANA_ADMIN_PASSWORD=change-me
```

Deploy one service:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh ai-service
```

Deploy the dashboard:

```bash
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh dashboard
```

Deploy both workers:

```bash
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh workers
```

Deploy all custom services:

```bash
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh all
```

Deploy the full stack, including DB, Kafka, ClickHouse, Prometheus, and Grafana:

```bash
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh stack
```

Check status:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose ps
docker compose logs --tail=80 dashboard ai-service gateway-request-enricher gateway-analytics-writer
```

Use `IMAGE_TAG=latest` only for manual testing. For GitHub Actions, use immutable tags such as the short GitHub SHA.

## Mac Studio Remote Access

The infra ports bind to `127.0.0.1`, so they are private to the Mac Studio host.

From a local machine, use SSH tunnels through the dev gateway. Example for Postgres:

```bash
ssh -J tri@dev.hftvn.com -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
```

Then connect locally to:

```txt
127.0.0.1:5433
```

Use the same pattern for Grafana, Prometheus, Kafka UI, ClickHouse, and Qdrant if needed.
