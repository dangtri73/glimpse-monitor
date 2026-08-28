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
./deploy.sh certs check cloudflare hanwhafintech.com
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
task-dev.hanwhafintech.com      -> http://<macstudio-lan-ip>:3000
task-api-dev.hanwhafintech.com  -> http://<macstudio-lan-ip>:4000
task.hanwhafintech.com          -> http://<macstudio-lan-ip>:3001
task-api.hanwhafintech.com      -> http://<macstudio-lan-ip>:4001
report-st.hanwhafintech.com     -> http://<macstudio-lan-ip>:3002
report-st-api.hanwhafintech.com -> http://<macstudio-lan-ip>:3003
report.hanwhafintech.com        -> http://<macstudio-lan-ip>:3005
report-api.hanwhafintech.com    -> http://<macstudio-lan-ip>:3004
api-rag-runtime-st.hanwhafintech.com -> http://<macstudio-lan-ip>:18000
h-q1.hanwhafintech.com          -> http://<macstudio-lan-ip>:9000
h-assistant-playground.hanwhafintech.com -> http://<macstudio-lan-ip>:18100
embed.glimpse-go.site           -> http://<macstudio-lan-ip>:8089
rerank.glimpse-go.site          -> http://<macstudio-lan-ip>:8090
mlx.glimpse-go.site             -> http://<macstudio-lan-ip>:8088
mlx-classify.glimpse-go.site    -> http://<macstudio-lan-ip>:8092
mlx-vlm.glimpse-go.site         -> http://<macstudio-lan-ip>:8093
```

Set these in `/Users/tri/nginx-docker/.env`:

```env
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
NGINX_TEMPLATE_MODE=ssl
TASK_DEV_DOMAIN=task-dev.hanwhafintech.com
TASK_DEV_API_DOMAIN=task-api-dev.hanwhafintech.com
TASK_PROD_DOMAIN=task.hanwhafintech.com
TASK_PROD_API_DOMAIN=task-api.hanwhafintech.com
REPORT_ST_DOMAIN=report-st.hanwhafintech.com
REPORT_ST_API_DOMAIN=report-st-api.hanwhafintech.com
REPORT_DOMAIN=report.hanwhafintech.com
REPORT_API_DOMAIN=report-api.hanwhafintech.com
API_RAG_RUNTIME_ST_DOMAIN=api-rag-runtime-st.hanwhafintech.com
H_Q1_DOMAIN=h-q1.hanwhafintech.com
H_ASSISTANT_PLAYGROUND_DOMAIN=h-assistant-playground.hanwhafintech.com
EMBED_DOMAIN=embed.glimpse-go.site
RERANK_DOMAIN=rerank.glimpse-go.site
MLX_DOMAIN=mlx.glimpse-go.site
MLX_CLASSIFY_DOMAIN=mlx-classify.glimpse-go.site
MLX_VLM_DOMAIN=mlx-vlm.glimpse-go.site
TASK_DEV_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3000
TASK_DEV_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4000
TASK_PROD_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3001
TASK_PROD_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4001
REPORT_ST_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3002
REPORT_ST_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3003
REPORT_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3005
REPORT_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3004
API_RAG_RUNTIME_ST_UPSTREAM=http://${MACSTUDIO_LAN_IP}:18000
H_Q1_UPSTREAM=http://${MACSTUDIO_LAN_IP}:9000
H_ASSISTANT_PLAYGROUND_UPSTREAM=http://${MACSTUDIO_LAN_IP}:18100
EMBED_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8089
RERANK_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8090
MLX_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8088
MLX_CLASSIFY_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8092
MLX_VLM_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8093
HANWHA_SSL_CERTIFICATE=/etc/ssl/cloudflare/hanwhafintech.com/fullchain.pem
HANWHA_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/hanwhafintech.com/privkey.pem
GLIMPSE_SSL_CERTIFICATE=/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem
GLIMPSE_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/glimpse-go.site/privkey.pem
```

Run `./deploy.sh deploy` after editing `MACSTUDIO_LAN_IP`; it derives the task, report, RAG runtime staging API, H-Q1, assistant playground, embed, rerank, MLX, MLX classify, and MLX VLM upstream URLs from that value.

Install Cloudflare Origin Certificates on the dev server for both zone groups:

```txt
hanwhafintech.com
*.hanwhafintech.com
glimpse-go.site
*.glimpse-go.site
```

The hanwha wildcard covers the listed one-label `hanwhafintech.com` routes, including `api-rag-runtime-st.hanwhafintech.com`. The glimpse wildcard keeps `embed.glimpse-go.site`, `rerank.glimpse-go.site`, `mlx.glimpse-go.site`, `mlx-classify.glimpse-go.site`, and `mlx-vlm.glimpse-go.site` working.

Set the same value in GitHub Actions repository variables:

```txt
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

Add Cloudflare DNS records pointing to the dev server public IP.

In the `hanwhafintech.com` zone:

```txt
A    task-dev       <dev-server-public-ip>
A    task-api-dev   <dev-server-public-ip>
A    task           <dev-server-public-ip>
A    task-api       <dev-server-public-ip>
A    report-st      <dev-server-public-ip>
A    report-st-api  <dev-server-public-ip>
A    report         <dev-server-public-ip>
A    report-api     <dev-server-public-ip>
A    api-rag-runtime-st <dev-server-public-ip>
A    h-q1           <dev-server-public-ip>
A    h-assistant-playground <dev-server-public-ip>
```

In the `glimpse-go.site` zone:

```txt
A    embed      <dev-server-public-ip>
A    rerank     <dev-server-public-ip>
A    mlx        <dev-server-public-ip>
A    mlx-classify <dev-server-public-ip>
A    mlx-vlm      <dev-server-public-ip>
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
ssh -J tri@hanwhafintech.com -L 8123:127.0.0.1:8123 admin@<macstudio-lan-ip>
ssh -J tri@hanwhafintech.com -L 9000:127.0.0.1:9000 admin@<macstudio-lan-ip>
ssh -J tri@hanwhafintech.com -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
ssh -J tri@hanwhafintech.com -L 8082:127.0.0.1:8082 admin@<macstudio-lan-ip>
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
curl -I http://<macstudio-lan-ip>:3002
curl -I http://<macstudio-lan-ip>:3003
curl -I http://<macstudio-lan-ip>:9000
curl -I http://<macstudio-lan-ip>:8771
curl http://<macstudio-lan-ip>:11435/api/tags
curl -I http://<macstudio-lan-ip>:8088
```

## CI Usage

GitHub Actions can still build and deploy automatically. These runtime bundles are also safe for manual recovery because target machines only need Docker, Docker Compose, the runtime folder, and the `.env` file.
