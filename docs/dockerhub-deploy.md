# Docker Hub Build and Mac Studio Deploy

Use this flow before GitHub Actions automation:

1. Build a specific project service image on the development machine.
2. Push it to Docker Hub.
3. SSH to Mac Studio.
4. Pull the image and restart only the affected compose service.

The same scripts can be called by GitHub Actions workflows.

## Services

Custom images:

```txt
dashboard   -> Docker Hub: <namespace>/glimpse-monitor-dashboard:<tag>
ai-service  -> Docker Hub: <namespace>/glimpse-monitor-ai-service:<tag>
workers     -> Docker Hub: <namespace>/glimpse-monitor-workers:<tag>
```

`workers` is one image used by both worker containers:

```txt
gateway-request-enricher
gateway-analytics-writer
```

Infrastructure images such as Postgres, Kafka, ClickHouse, Prometheus, Grafana, Redis, and Qdrant are pulled from public upstream registries.

## Build and Push From Local

Login once:

```bash
docker login
```

Build and push one service:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor

DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
./scripts/docker-build-push.sh ai-service
```

Build and push everything:

```bash
DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
./scripts/docker-build-push.sh all
```

For Mac Studio, keep:

```env
DOCKER_PLATFORM=linux/arm64
```

For an Intel/Linux server, use:

```env
DOCKER_PLATFORM=linux/amd64
```

## Mac Studio Runtime

Mac Studio does not need a manually maintained repo checkout for runtime. GitHub Actions checks out code into the runner workspace only while building images. Long-lived runtime state should live here:

```txt
/Users/admin/glimpse-monitor-runtime
```

The deploy script copies these runtime files from the runner checkout into that directory:

```txt
docker-compose.yml
sql/monitor_schema.sql
.env
```

Create `/Users/admin/glimpse-monitor-runtime/.env` on Mac Studio:

```env
POSTGRES_INIT_SQL=/Users/admin/glimpse-monitor-runtime/sql/monitor_schema.sql
DOCKERHUB_NAMESPACE=dangtri73
IMAGE_TAG=local-latest
IMAGE_PREFIX=glimpse-monitor

DASHBOARD_PORT=3000
DASHBOARD_BIND_HOST=127.0.0.1
MONITOR_AGENT_URL=http://host.docker.internal:8765
MONITOR_AGENT_ADMIN_TOKEN=
AI_SERVICE_HOST_PORT=8771
AI_SERVICE_BIND_HOST=127.0.0.1
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:270m
OLLAMA_TIMEOUT_SECONDS=60

POSTGRES_DB=glimpse_monitor
POSTGRES_USER=glimpse
POSTGRES_PASSWORD=change-me
POSTGRES_PORT=5433

REDIS_PORT=6380

KAFKA_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk
KAFKA_EXTERNAL_HOST=localhost
KAFKA_EXTERNAL_PORT=9094
KAFKA_UI_PORT=8082
KAFKA_LOG_RETENTION_HOURS=168
KAFKA_LOG_SEGMENT_BYTES=1073741824

CLICKHOUSE_DB=glimpse_gateway
CLICKHOUSE_USER=glimpse
CLICKHOUSE_PASSWORD=change-me
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_NATIVE_PORT=9000

QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334

ADMINER_PORT=8081

PROMETHEUS_PORT=9090
PROMETHEUS_RETENTION_TIME=15d

GRAFANA_PORT=3001
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=change-me

POSTGRES_BACKUP_INTERVAL_SECONDS=86400
POSTGRES_BACKUP_RETENTION_DAYS=14
```

Do not commit real passwords.

`deploy-macstudio.sh` reads `DOCKERHUB_NAMESPACE`, `IMAGE_TAG`, and `IMAGE_PREFIX` from this file when they are not provided in the shell.

## Deploy on Mac Studio

Manual commands in this section need a temporary checkout because the deploy script lives in the repo. GitHub Actions provides that checkout automatically. The runtime directory remains `/Users/admin/glimpse-monitor-runtime`.

Login once if the Docker Hub repository is private:

```bash
docker login
```

Pull and run one service:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor

DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh ai-service
```

Deploy dashboard:

```bash
DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh dashboard
```

Deploy both workers:

```bash
DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh workers
```

Deploy all custom services:

```bash
DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh all
```

If `/Users/admin/glimpse-monitor-runtime/.env` already contains the Docker Hub settings, this is enough:

```bash
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh all
```

Deploy the full stack:

```bash
DOCKERHUB_NAMESPACE=dangtri73 \
IMAGE_TAG=local-latest \
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh stack
```

## Public Gateway Routing

Keep database and broker ports bound to `127.0.0.1`. Application HTTP services that the dev gateway must reach on Mac Studio should bind with `0.0.0.0`, then the dev gateway points to `MACSTUDIO_LAN_IP`.

Mac Studio runtime `.env`:

```env
DASHBOARD_BIND_HOST=0.0.0.0
AI_SERVICE_BIND_HOST=0.0.0.0
```

Dev server Nginx runtime `.env`:

```env
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

Example public routes:

```txt
https://task-dev.hanwhafintech.com      -> http://${MACSTUDIO_LAN_IP}:3000
https://task-api-dev.hanwhafintech.com  -> http://${MACSTUDIO_LAN_IP}:4000
https://task.hanwhafintech.com          -> http://${MACSTUDIO_LAN_IP}:3001
https://task-api.hanwhafintech.com      -> http://${MACSTUDIO_LAN_IP}:4001
https://report-st.hanwhafintech.com     -> http://${MACSTUDIO_LAN_IP}:3002
https://report-st-api.hanwhafintech.com -> http://${MACSTUDIO_LAN_IP}:3003
https://h-q1.hanwhafintech.com          -> http://${MACSTUDIO_LAN_IP}:9000
https://embed.glimpse-go.site           -> http://${MACSTUDIO_LAN_IP}:8089
https://rerank.glimpse-go.site          -> http://${MACSTUDIO_LAN_IP}:8090
https://mlx.glimpse-go.site             -> http://${MACSTUDIO_LAN_IP}:8088
https://mlx-classify.glimpse-go.site    -> http://${MACSTUDIO_LAN_IP}:8092
https://mlx-vlm.glimpse-go.site         -> http://${MACSTUDIO_LAN_IP}:8093
```

## GitHub Actions Plan

Required GitHub Actions secrets:

```txt
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

Required GitHub Actions variables:

```txt
DOCKERHUB_NAMESPACE=dangtri73
DOCKER_PLATFORM=linux/arm64
MACSTUDIO_RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime
MACSTUDIO_ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env
```

Build job on the Mac Studio self-hosted runner:

```bash
echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
DOCKERHUB_NAMESPACE="$DOCKERHUB_NAMESPACE" IMAGE_TAG="$GITHUB_SHA" ./scripts/docker-build-push.sh all
```

Deploy job on the Mac Studio self-hosted runner:

```bash
DOCKERHUB_NAMESPACE="$DOCKERHUB_NAMESPACE" IMAGE_TAG="$GITHUB_SHA" RUNTIME_DIR="$MACSTUDIO_RUNTIME_DIR" ENV_FILE="$MACSTUDIO_ENV_FILE" ./scripts/deploy-macstudio.sh all
```

Use `latest` only for manual testing. For automated deploys, prefer immutable tags such as the short GitHub SHA.
