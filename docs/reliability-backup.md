# Mac Studio Reliability And Backup Plan

## Scope

This project is designed to run for free on one Mac Studio using Docker Compose. It can be reliable for local operations, but it is not high availability because there is only one physical machine.

The design goal is:

- survive container restart
- survive Mac reboot after power loss
- avoid data loss for important metadata
- buffer high-volume gateway events long enough for consumers to recover
- keep private DB/Kafka/ClickHouse/Qdrant ports off the public internet

## Current Free Stack

```txt
Postgres/TimescaleDB
  critical metadata, device registry, audits, metric rollups

Kafka
  high-volume gateway event buffering and replay

ClickHouse
  high-volume request analytics

Qdrant
  vector search for summaries, incidents, and runbooks

Redis
  lightweight cache or small buffering use cases

Adminer and Kafka UI
  local-only admin tools
```

All ports bind to `127.0.0.1` in Docker Compose. From another laptop, use SSH tunnels through the dev gateway or a private VPN.

## Reliability Built Into Compose

The compose file includes:

- persistent Docker volumes for stateful services
- `restart: unless-stopped` for long-running services
- health checks for Postgres, Redis, Kafka, and ClickHouse
- capped Docker JSON logs to reduce disk-fill risk
- Kafka topic retention so traffic buffers do not grow forever
- a local Postgres dump backup service

## Important Data Priority

Priority 1: must back up

- Postgres: devices, users, service definitions, port mappings, audits, AI conversations, metric rollups
- Nginx generated config and rollback files once implemented
- agent/device secrets and token hashes

Priority 2: should back up

- Qdrant vectors and payload metadata
- ClickHouse request analytics
- runbooks and incident summaries

Priority 3: buffer only

- Kafka topics
- Redis cache

Kafka is not the long-term database. It provides replay for a limited retention window. Consumers must write important data to Postgres, ClickHouse, or Qdrant.

## Backup Plan

### Postgres

The `postgres-backup` service writes compressed custom-format dumps to:

```txt
glimpse-monitor/infra/backups/postgres
```

Default schedule:

```txt
every 86400 seconds
keep 14 days
```

Configure in `infra/.env`:

```txt
POSTGRES_BACKUP_INTERVAL_SECONDS=86400
POSTGRES_BACKUP_RETENTION_DAYS=14
```

Restore example:

```bash
docker compose -f glimpse-monitor/infra/docker-compose.yml exec -T postgres \
  pg_restore -U glimpse -d glimpse_monitor --clean --if-exists < glimpse-monitor/infra/backups/postgres/<backup-file>.dump
```

### ClickHouse

For MVP, ClickHouse can be rebuilt from Kafka only while Kafka retention still contains the events. Once request analytics become important, add one of these:

- scheduled ClickHouse native backup to a host-mounted directory
- weekly stopped-container volume backup
- export critical daily aggregates to Postgres

Pragmatic first step: keep critical rollups in TimescaleDB/Postgres and treat ClickHouse raw logs as useful but less critical.

### Qdrant

Vector data can be regenerated if source summaries and runbooks are stored in Postgres or the repo. Keep source text and metadata outside Qdrant.

When vectors become expensive to regenerate, add Qdrant snapshot automation.

### Docker Volumes

Use host-level backup for:

- `glimpse-monitor/infra/backups`
- project repo
- Docker volume data if available from Docker Desktop

For Mac Studio, also use:

- Time Machine to an external drive
- periodic copy of `infra/backups` to another machine
- optional encrypted cloud backup if policy allows

## Power Loss Plan

After power returns:

1. Mac Studio boots.
2. Docker Desktop or Docker service starts.
3. `docker compose up -d` starts services.
4. Compose restarts containers because of `restart: unless-stopped`.
5. Agents reconnect and resume metric/event publishing.
6. Kafka consumers resume from committed offsets.

If Docker does not auto-start after reboot, create a macOS `launchd` job later to run:

```bash
cd /path/to/Glimpse/glimpse-monitor/infra
docker compose up -d
```

## Network Loss Plan

If Mac Studio loses internet but local containers still run:

- local metrics continue
- local Kafka continues accepting local events
- dashboard works over LAN or SSH tunnel
- cloud LLM calls fail, so prefer local Ollama for AI when possible

If a remote device cannot reach Mac Studio:

- the remote agent should write unsent samples/events to a local disk spool
- the local spool should retry with backoff until Mac Studio is reachable
- otherwise samples during the outage are lost
- last heartbeat marks the device offline

Recommended agent spool:

```txt
agent collects event
  -> try POST to ingest API
  -> if failed, append to local SQLite/JSONL spool
  -> retry oldest unsent events first
  -> delete only after ingest API acknowledges
```

Use SQLite for production agents because it gives durable writes, ordering, and simple cleanup. JSONL is acceptable for a quick prototype.

Local spool guardrails:

- cap retained events by size and age
- keep high-priority events longer than routine metrics
- redact sensitive request fields before writing to local spool
- expose local spool depth as an agent health metric

## Expansion Plan

This stack expands cleanly by adding workers:

```txt
Kafka topic
  -> more consumer groups
  -> more DB writers
  -> more AI summarizers
  -> more alert processors
```

Database expansion path:

- keep Postgres for metadata
- keep TimescaleDB for rollups
- keep ClickHouse for request analytics
- keep Qdrant for semantic retrieval
- move Kafka to a multi-node cluster only when you have more machines

Single Mac Studio limitation:

- Kafka replication factor is `1`
- Postgres has no hot standby
- ClickHouse has one replica
- Qdrant has one node

This is acceptable for a free local system, but not for production HA.

## Operational Checklist

Run weekly:

```bash
docker compose -f glimpse-monitor/infra/docker-compose.yml ps
docker compose -f glimpse-monitor/infra/docker-compose.yml logs --tail=100 postgres-backup
ls -lh glimpse-monitor/infra/backups/postgres
```

Run monthly:

- restore a Postgres backup into a temporary DB and verify it works
- check Mac Studio disk usage
- delete or archive old ClickHouse data if disk pressure grows
- verify Kafka topics are not growing unexpectedly
