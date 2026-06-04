# Glimpse Monitor Agent

Local resource collector for the dev gateway dashboard.

## Why This Is Separate

Resource monitoring needs host-level access to processes, network counters, disk, memory, and eventually Nginx/system service control. That should not run inside the public Next.js dashboard or the existing Cloudflare Worker.

## Run Locally

```bash
python3 glimpse-monitor/agent/server.py
```

Then open:

```bash
curl http://127.0.0.1:8765/api/snapshot
```

## Endpoints

- `GET /health`
- `GET /api/snapshot`
- `GET /api/samples?limit=120`
- `GET /api/services`
- `POST /api/services/:serviceId/:action`
- `GET /api/port-maps`
- `POST /api/port-maps/drafts`
- `POST /api/port-maps/:mappingId/validate`
- `POST /api/port-maps/:mappingId/verify`
- `POST /api/port-maps/:mappingId/apply`
- `POST /api/port-maps/:mappingId/rollback`

Service actions are disabled by default. To enable them, configure explicit command arrays in `config/devices.json` and set:

```bash
GLIMPSE_AGENT_ENABLE_SERVICE_ACTIONS=true
```

Nginx live apply is also disabled by default. Domain mapping actions create drafts, validate policy, and return dry-run output until the Docker Nginx command arrays are configured and this flag is set:

```bash
GLIMPSE_AGENT_ENABLE_NGINX_APPLY=true
```

For deployed use, protect mutating endpoints with a shared admin token:

```bash
GLIMPSE_AGENT_ADMIN_TOKEN=change-me
```

Set the same value as `MONITOR_AGENT_ADMIN_TOKEN` for the dashboard proxy.

## Source Layout

- `collector.py`: compatibility facade used by `server.py`.
- `system_metrics.py`: host resources, processes, services, and topology connections.
- `domain_gateway.py`: domain draft, verification, Nginx generation, apply, and rollback workflow.
- `agent_common.py`: shared config persistence, timestamps, command helpers, and parsing utilities.
- `prometheus.py`: Prometheus text rendering.
- `samples.py`: in-memory metric sample ring buffer.

## Production Direction

Python is good for fast iteration and LangGraph integration. For a hardened gateway daemon, Go is the better long-term choice because it produces a single binary, has lower runtime overhead, and has mature system/network libraries.
