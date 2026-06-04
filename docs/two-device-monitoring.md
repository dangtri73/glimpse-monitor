# Two-Device Monitoring Design

## Goal

Monitor two machines from one dashboard:

- Dev Gateway: public entry point, Nginx, port mapping, local services.
- Mac Studio or another device: compute services such as Ollama, GPU workloads, app services.

The dashboard should show live resources per device, compare historical usage, show service state, and later allow authenticated gateway actions.

## Is A Database Needed?

For live-only monitoring: no.

```txt
Dashboard -> Agent A
Dashboard -> Agent B
```

This is enough to show current CPU, RAM, SSD, network, services, and topology while both agents are reachable.

For the target product: yes.

Use a database when you need:

- charts over minutes, hours, days, or weeks
- "compare between hours" AI answers
- device configuration that survives restart
- offline detection and last-seen timestamps
- audit logs for service control and port mapping
- stable public port mapping records
- reliable dashboard behavior when one device is temporarily unavailable

Recommended default: Postgres with TimescaleDB extension. For only two devices, plain Postgres can work first, but design the metric table in a Timescale-compatible way.

## Recommended Architecture

```txt
Device 1: Dev Gateway
  monitor agent
    collect local CPU/RAM/disk/network/processes/services
    control gateway-local services only
    apply Nginx port mapping only after validation
    push metrics to ingest API

Device 2: Mac Studio
  monitor agent
    collect local CPU/RAM/disk/network/processes/services
    control Mac Studio-local services only
    push metrics to ingest API

Gateway / Backend
  ingest API
    validate agent token
    upsert device heartbeat
    write latest state
    write metric samples
    publish live update event

Storage
  Postgres
    devices
    agent_heartbeats
    services
    service_snapshots
    port_mappings
    audit_events
  Timescale-compatible metric tables
    metric_samples
    network_interface_samples
    process_samples

Dashboard
  device selector
  topology view
  latest resource cards
  historical charts by deviceId
  services by deviceId
  AI asks live tools plus historical query tools
```

## Data Flow

Use push from agents to gateway, not dashboard polling every machine directly.

```txt
agent -> POST /api/ingest/metrics -> DB -> dashboard
```

Reasons:

- dashboard does not need private LAN access to every device
- agents can be authenticated independently
- metrics still collect when nobody has the dashboard open
- history exists for charts and AI comparison
- device offline state is easy to compute from last heartbeat

For network-loss reliability, each remote agent should keep a local disk spool. If the Mac Studio ingest API is unreachable, the agent stores samples locally and replays them when connectivity returns.

## Queue Decision

For two devices, start without Kafka.

Recommended phases:

1. Direct write: agent posts to ingest API, ingest writes Postgres.
2. Add Redis Streams or NATS JetStream if you need buffering/replay.
3. Add Kafka only if there are many devices, high volume, long retention, or multiple consumer teams.

Direct write is acceptable for MVP because two devices at 2-second intervals produce low volume.

Approximate volume:

```txt
2 devices * 1 sample / 2 seconds = 86,400 samples / day
```

That is small for Postgres/TimescaleDB.

## Agent Identity

Each agent needs stable configuration:

```json
{
  "deviceId": "mac-studio",
  "deviceName": "Mac Studio",
  "role": "compute",
  "ingestUrl": "https://dev.api.hftvn.com/api/ingest/metrics",
  "agentToken": "secret-per-device-token"
}
```

Do not trust hostname alone. Hostnames can change and are not authentication.

## API Contracts

Agent registration or heartbeat:

```http
POST /api/ingest/heartbeat
Authorization: Bearer <agent-token>
```

```json
{
  "deviceId": "mac-studio",
  "name": "Mac Studio",
  "role": "compute",
  "hostname": "mac-studio.local",
  "lanIp": "192.168.1.3",
  "agentVersion": "0.1.0",
  "observedAt": "2026-06-02T09:00:00Z"
}
```

Metric ingest:

```http
POST /api/ingest/metrics
Authorization: Bearer <agent-token>
```

```json
{
  "deviceId": "mac-studio",
  "observedAt": "2026-06-02T09:00:00Z",
  "resources": {
    "cpuLoadPercent": 42.1,
    "memoryUsedPercent": 76.4,
    "diskUsedPercent": 61.2,
    "networkRxBytesPerSecond": 124000,
    "networkTxBytesPerSecond": 82000
  },
  "services": [
    {
      "id": "ollama",
      "name": "Ollama",
      "status": "running",
      "ports": [11435]
    }
  ]
}
```

Dashboard latest:

```http
GET /api/devices
GET /api/devices/:deviceId/latest
GET /api/devices/:deviceId/metrics?from=...&to=...
GET /api/devices/:deviceId/services
```

## Tables To Add

Minimum tables:

- `devices`: stable device metadata.
- `agent_tokens`: hashed token per device.
- `agent_heartbeats`: latest and historical heartbeat.
- `metric_samples`: CPU/RAM/disk/network samples.
- `service_snapshots`: latest service state per device.
- `audit_events`: service actions, port mapping changes, auth events.

Keep `port_mappings` attached to gateway-managed target devices.

## Dashboard Behavior

First page:

- show topology with both devices
- show each device status: online, warning, offline
- click a device to expand details
- charts update for selected device
- services panel filters by selected device
- port mappings show gateway-to-device routes

Device is offline when:

```txt
now - lastHeartbeatAt > 3 * expectedInterval
```

If expected interval is 2 seconds, mark offline after about 6 to 10 seconds depending on tolerance.

## AI Behavior

AI should use two types of tools:

- live tools: latest snapshot, service status, port mappings
- history tools: query metrics by device and time window

Example questions that require DB:

- "Compare Mac Studio RAM usage between the last two hours."
- "Which device had higher network upload today?"
- "Was Ollama restarted before CPU increased?"
- "Show me gateway pressure before and after public port mapping."

Without DB, AI can only compare recent in-memory samples from the currently running agent.

## MVP Implementation Order

1. Add `deviceId` to agent config and every snapshot.
2. Add ingest endpoints on the gateway/backend.
3. Add Postgres tables for devices, heartbeats, metric samples, services, and audits.
4. Add local disk spool to the agent for failed ingest attempts.
5. Change agents to push metrics every 2 seconds and replay spooled samples.
6. Change dashboard to query DB by selected `deviceId`.
7. Add live updates with SSE or WebSocket.
8. Add Redis Streams or NATS only if direct writes are unreliable.

## Security Rules

- Use one token per device.
- Store only token hashes in DB.
- Allow service actions only on the target device's local agent.
- Keep gateway port mapping actions gateway-only.
- Require user login and audit logs before enabling service or Nginx actions.
- Never expose raw command execution through dashboard APIs.
