# Glimpse Runtime Deploy Bundles

These folders are standalone runtime bundles. Copy a bundle to the machine that runs it, edit `.env`, then run `./deploy.sh`.

## Dev Server: Nginx Gateway

Target path:

```sh
/Users/tri/nginx-docker
```

Copy from the repo:

```sh
rsync -av --exclude '.env' --exclude 'certs/' \
  deploy-runtime/dev-server/nginx-docker/ \
  tri@192.168.1.113:/Users/tri/nginx-docker/
```

Run on the dev server:

```sh
cd /Users/tri/nginx-docker
cp -n .env.example .env
./deploy.sh deploy dangtri73/glimpse-nginx:latest
./deploy.sh status
```

Certificates stay on the dev server under `certs/` and are not copied from Git.

Useful commands:

```sh
./deploy.sh certs list
./deploy.sh certs check cloudflare glimpse-go.site
./deploy.sh test
./deploy.sh reload
./deploy.sh logs
```

## Mac Studio: App Stack

Target path:

```sh
/Users/admin/glimpse-monitor-runtime
```

Copy from the repo:

```sh
rsync -av --exclude '.env' --exclude 'backups/' \
  deploy-runtime/macstudio/glimpse-monitor/ \
  /Users/admin/glimpse-monitor-runtime/
```

Run on Mac Studio:

```sh
cd /Users/admin/glimpse-monitor-runtime
cp -n .env.example .env
./deploy.sh stack
./deploy.sh agent
./deploy.sh dashboard
./deploy.sh ai-service
./deploy.sh tarot-ingest
./deploy.sh workers
```

The Mac Studio monitor agent runs as a host `launchd` service, not as a Docker container. CI/CD copies `agent/` into `/Users/admin/glimpse-monitor-runtime/agent` before running `./deploy.sh agent`, so the dashboard container can reach it at `http://host.docker.internal:8765`.

For Docker Desktop or Colima on Mac Studio, keep app service bind hosts open on the Mac host:

```env
DASHBOARD_BIND_HOST=0.0.0.0
AI_SERVICE_BIND_HOST=0.0.0.0
```

Deploy a CI-built tag:

```sh
IMAGE_TAG=abc1234 ./deploy.sh dashboard
IMAGE_TAG=abc1234 ./deploy.sh all
```

Useful commands:

```sh
./deploy.sh status
./deploy.sh logs dashboard
./deploy.sh restart workers
./deploy.sh stop all
```

Rebuild the tarot vector collection after deploying an AI image that includes the ingest script:

```sh
./deploy.sh stack
./deploy.sh tarot-ingest
./deploy.sh restart ai-service
```

## Public Gateway Vs Private Ports

The dev server Nginx gateway should expose only HTTP services:

```txt
dashboard.glimpse-go.site  -> http://<macstudio-lan-ip>:3000
ai.glimpse-go.site         -> http://<macstudio-lan-ip>:8771
ollama.glimpse-go.site     -> http://<macstudio-lan-ip>:11435
mlx.glimpse-go.site        -> http://<macstudio-lan-ip>:8088
```

Set these in `/Users/tri/nginx-docker/.env`:

```env
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
DASHBOARD_DOMAIN=dashboard.glimpse-go.site
AI_DOMAIN=ai.glimpse-go.site
OLLAMA_DOMAIN=ollama.glimpse-go.site
MLX_DOMAIN=mlx.glimpse-go.site
```

Run `./deploy.sh deploy` after editing `MACSTUDIO_LAN_IP`; it derives `DASHBOARD_UPSTREAM`, `AI_UPSTREAM`, `OLLAMA_UPSTREAM`, and `MLX_UPSTREAM` from that value.

Set the same value in GitHub Actions repository variables:

```txt
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

Add Cloudflare DNS records pointing to the dev server public IP:

```txt
A    dashboard  <dev-server-public-ip>
A    ai         <dev-server-public-ip>
A    ollama     <dev-server-public-ip>
A    mlx        <dev-server-public-ip>
```

Do not expose database or broker ports publicly through Nginx:

```txt
Postgres    5433
Kafka       9094
ClickHouse  8123, 9000
Redis       6380
Qdrant      6333, 6334
Kafka UI    8082
Adminer     8081
Grafana     3001
Prometheus  9090
```

Access private ports with SSH tunnels.

From the same LAN:

```sh
ssh -L 8123:127.0.0.1:8123 admin@<macstudio-lan-ip>
ssh -L 9000:127.0.0.1:9000 admin@<macstudio-lan-ip>
ssh -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
ssh -L 8082:127.0.0.1:8082 admin@<macstudio-lan-ip>
```

From outside the LAN, use the dev server as the jump host:

```sh
ssh -J tri@dev.hftvn.com -L 8123:127.0.0.1:8123 admin@<macstudio-lan-ip>
ssh -J tri@dev.hftvn.com -L 9000:127.0.0.1:9000 admin@<macstudio-lan-ip>
ssh -J tri@dev.hftvn.com -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
ssh -J tri@dev.hftvn.com -L 8082:127.0.0.1:8082 admin@<macstudio-lan-ip>
```

DBeaver ClickHouse over HTTP:

```txt
Host: localhost
Port: 8123
Database: glimpse_gateway
Username: glimpse
Password: glimpse
```

DBeaver ClickHouse native TCP:

```txt
Host: localhost
Port: 9000
Database: glimpse_gateway
Username: glimpse
Password: glimpse
```

DBeaver Postgres:

```txt
Host: localhost
Port: 5433
Database: glimpse_monitor
Username: glimpse
Password: glimpse
```

Find the Mac Studio LAN IP on Mac Studio:

```sh
ipconfig getifaddr en0
ipconfig getifaddr en1
```

Test gateway targets from the dev server:

```sh
curl -I http://<macstudio-lan-ip>:3000
curl -I http://<macstudio-lan-ip>:8771
curl http://<macstudio-lan-ip>:11435/api/tags
curl -I http://<macstudio-lan-ip>:8088
```

## CI Usage

GitHub Actions can still build and deploy automatically. These runtime bundles are also safe for manual recovery because target machines only need Docker, Docker Compose, the runtime folder, and the `.env` file.
