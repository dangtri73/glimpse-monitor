# Mac Studio Glimpse Monitor Runtime

This directory is the persistent runtime bundle for Mac Studio:

```sh
/Users/admin/glimpse-monitor-runtime
```

It runs the Docker app stack and the host monitor agent.

## Services

Docker Compose runs:

- `dashboard`
- `ai-service`
- `gateway-request-enricher`
- `gateway-analytics-writer`
- Postgres, Redis, Kafka, ClickHouse, Qdrant, Prometheus, Grafana, and admin tools

The monitor agent is different: it runs on the Mac Studio host through `launchd`, not in Docker. It needs host-level process, network, disk, and service visibility. The dashboard container reaches it through:

```env
MONITOR_AGENT_URL=http://host.docker.internal:8765
```

If mutating agent endpoints are enabled later, set the same shared value for `MONITOR_AGENT_ADMIN_TOKEN` and `GLIMPSE_AGENT_ADMIN_TOKEN` in `.env`.

## First-Time Setup

From a repo checkout on Mac Studio:

```sh
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor

DOCKERHUB_NAMESPACE=dangtri73 \
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh stack
```

The repo-side script copies this runtime bundle into `RUNTIME_DIR`, copies `agent/` into `RUNTIME_DIR/agent`, then runs the runtime deploy script.

## Runtime Commands

Run these from `/Users/admin/glimpse-monitor-runtime`:

```sh
./deploy.sh stack
./deploy.sh all
./deploy.sh dashboard
./deploy.sh ai-service
./deploy.sh workers
./deploy.sh agent
```

Status and logs:

```sh
./deploy.sh status
./deploy.sh agent-status
./deploy.sh logs dashboard
./deploy.sh logs agent
```

If the GitHub runner does not have a GUI launchd domain, the deploy script falls back from `gui/<uid>` to `user/<uid>`. You can force a domain in `.env`:

```env
GLIMPSE_AGENT_LAUNCHD_DOMAIN=user/501
```

Deploy stops known Glimpse `launchd` jobs before starting the new agent. It can also stop an existing Python `server.py` process on the configured agent port:

```env
GLIMPSE_AGENT_REPLACE_PORT_OWNER=true
```

If another unknown process owns `GLIMPSE_AGENT_PORT`, deploy fails and prints `lsof` output instead of stopping it.

When `GLIMPSE_AGENT_AUTO_PORT_FALLBACK=true`, deploy can instead pick a nearby free port and update both `GLIMPSE_AGENT_PORT` and `MONITOR_AGENT_URL` in `.env`.

Every successful agent deploy force-recreates the dashboard container so the server-side Next.js API routes read the current `MONITOR_AGENT_URL`.

Restart or stop:

```sh
./deploy.sh restart dashboard
./deploy.sh restart agent
./deploy.sh stop agent
./deploy.sh stop all
```

## Agent Health Checks

Check the host agent directly:

```sh
curl -i http://127.0.0.1:8765/health
curl -i http://127.0.0.1:8765/api/snapshot
```

Check that the dashboard container can reach the host agent:

```sh
docker exec glimpse-monitor-dashboard node -e "fetch('http://host.docker.internal:8765/health').then(r=>r.text()).then(console.log).catch(e=>{console.error(e);process.exit(1)})"
```

If the host `curl` fails, the `launchd` agent is not running. If the host `curl` works but the Docker check fails, fix `MONITOR_AGENT_URL` in `.env` or Docker Desktop host networking.

## CI/CD

The GitHub Actions app-services workflow supports agent deploys:

- `agent/**` changes deploy the agent only.
- `dashboard/**`, `ai-service/**`, and `workers/**` changes still build and push Docker images.
- Runtime/script/infra workflow changes deploy `all`, which updates Docker app services and the host agent.
- Agent-only deploys skip Docker Hub login/build because there is no agent image.

Manual workflow dispatch options include:

- `agent`
- `dashboard`
- `ai-service`
- `workers`
- `all`

The workflow calls:

```sh
RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime \
ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env \
./scripts/deploy-macstudio.sh <target>
```

## Runtime Files

Persistent runtime state:

- `.env`
- `agent/`
- `logs/agent/`
- Docker volumes
- `backups/`

Do not commit `.env`, copied `agent/`, logs, or backups from the runtime directory.
