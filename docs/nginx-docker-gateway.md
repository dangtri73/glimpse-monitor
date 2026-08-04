# Nginx Docker Gateway Usage

## Purpose

Use Docker Nginx on the dev server as the public gateway only.

Current target:

```txt
Internet -> dev server Docker Nginx -> Mac Studio service
```

The dev server owns public ports `80` and `443`. Application services stay on Mac Studio or another internal machine. For SSH and Mac Studio connection details, see `../../docs/connections.md`.

Use this gateway for HTTP services only:

```txt
task-dev.hanwhafintech.com      -> http://<macstudio-lan-ip>:3000
task-api-dev.hanwhafintech.com  -> http://<macstudio-lan-ip>:4000
task.hanwhafintech.com          -> http://<macstudio-lan-ip>:3001
task-api.hanwhafintech.com      -> http://<macstudio-lan-ip>:4001
embed.glimpse-go.site           -> http://<macstudio-lan-ip>:8089
rerank.glimpse-go.site          -> http://<macstudio-lan-ip>:8090
mlx.glimpse-go.site             -> http://<macstudio-lan-ip>:8088
```

Do not route Postgres, Kafka, ClickHouse, Redis, Qdrant, Prometheus, Grafana, Adminer, or Kafka UI through public Nginx. Use SSH tunnels for those private ports.

## Current Domains

```txt
task-dev.hanwhafintech.com
task-api-dev.hanwhafintech.com
task.hanwhafintech.com
task-api.hanwhafintech.com
embed.glimpse-go.site
rerank.glimpse-go.site
mlx.glimpse-go.site
```

The Mac Studio upstreams are:

```env
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
TASK_DEV_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3000
TASK_DEV_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4000
TASK_PROD_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3001
TASK_PROD_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4001
EMBED_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8089
RERANK_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8090
MLX_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8088
```

Change `MACSTUDIO_LAN_IP` in `/Users/tri/nginx-docker/.env` when the Mac Studio LAN IP changes, then run `./deploy.sh deploy`. The deploy script rewrites the task, embed, rerank, and MLX upstream URLs from that one value.

For GitHub Actions deploys, set the repository variable with the same value:

```txt
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

The examples below assume the current dev-server runtime directory:

```txt
/Users/tri/nginx-docker
```

## Template Modes

`nginx-docker` has two template modes:

```env
NGINX_TEMPLATE_MODE=http       # HTTP only, no certs required
NGINX_TEMPLATE_MODE=ssl        # HTTPS for all configured public service domains
```

Recommended current mode:

```env
NGINX_TEMPLATE_MODE=ssl
```

Use this with Cloudflare Origin Certificates for both zone groups:

```txt
hanwhafintech.com
*.hanwhafintech.com
glimpse-go.site
*.glimpse-go.site
```

The hanwha wildcard covers `task-dev.hanwhafintech.com`, `task-api-dev.hanwhafintech.com`, `task.hanwhafintech.com`, and `task-api.hanwhafintech.com`. The glimpse wildcard keeps `embed.glimpse-go.site`, `rerank.glimpse-go.site`, and `mlx.glimpse-go.site` working.

If you later use a two-label hostname such as `api.dev.hanwhafintech.com`, add `*.dev.hanwhafintech.com` to the Cloudflare Origin Certificate too. `*.hanwhafintech.com` does not cover that depth.

## Domain Edit Release

After adding, removing, or changing gateway domains, validate the synchronized nginx templates, runtime env, compose contract, and docs:

```bash
scripts/nginx-gateway-release.sh check
```

Build and push the nginx image:

```bash
DOCKER_PLATFORM=linux/arm64 scripts/nginx-gateway-release.sh build-push
```

Deploy from the dev server runtime directory:

```bash
cd /Users/tri/nginx-docker
./deploy.sh deploy
```

Or deploy remotely from the repo:

```bash
DEV_NGINX_HOST=tri@hanwhafintech.com scripts/nginx-gateway-release.sh deploy-remote
```

## Stop Homebrew Nginx

Run on the dev server:

```bash
brew services stop nginx
sudo nginx -s stop
```

Check that Docker can use ports `80` and `443`:

```bash
sudo lsof -nP -iTCP:80 -sTCP:LISTEN
sudo lsof -nP -iTCP:443 -sTCP:LISTEN
```

No output means the ports are free.

## Prepare The Environment

Run from the dev server:

```bash
cd /Users/tri/nginx-docker
cp .env.example .env
nano .env
```

Use this current `.env` baseline:

```env
TASK_DEV_DOMAIN=task-dev.hanwhafintech.com
TASK_DEV_API_DOMAIN=task-api-dev.hanwhafintech.com
TASK_PROD_DOMAIN=task.hanwhafintech.com
TASK_PROD_API_DOMAIN=task-api.hanwhafintech.com
EMBED_DOMAIN=embed.glimpse-go.site
RERANK_DOMAIN=rerank.glimpse-go.site
MLX_DOMAIN=mlx.glimpse-go.site

NGINX_IMAGE=dangtri73/glimpse-nginx:latest
NGINX_TEMPLATE_MODE=ssl

HANWHA_SSL_CERTIFICATE=/etc/ssl/cloudflare/hanwhafintech.com/fullchain.pem
HANWHA_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/hanwhafintech.com/privkey.pem

GLIMPSE_SSL_HOST_DIR=./certs/cloudflare
GLIMPSE_SSL_CERTIFICATE=/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem
GLIMPSE_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/glimpse-go.site/privkey.pem

MACSTUDIO_LAN_IP=<macstudio-lan-ip>
TASK_DEV_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3000
TASK_DEV_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4000
TASK_PROD_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3001
TASK_PROD_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4001
EMBED_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8089
RERANK_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8090
MLX_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8088
```

## Install The Cloudflare Origin Certificate

Create Cloudflare Origin Certificates for both zone groups:

```txt
hanwhafintech.com
*.hanwhafintech.com
glimpse-go.site
*.glimpse-go.site
```

Save the certificates and private keys temporarily on the dev server, then install them with the cert manager:

```bash
cd /Users/tri/nginx-docker

./scripts/certs.sh install cloudflare hanwhafintech.com \
  /tmp/hanwhafintech.com.fullchain.pem \
  /tmp/hanwhafintech.com.privkey.pem
./scripts/certs.sh check cloudflare hanwhafintech.com

./scripts/certs.sh install cloudflare glimpse-go.site \
  /tmp/glimpse-go.site.fullchain.pem \
  /tmp/glimpse-go.site.privkey.pem
./scripts/certs.sh check cloudflare glimpse-go.site
```

Check that files exist:

```bash
ls -la certs/cloudflare/hanwhafintech.com/
wc -l certs/cloudflare/hanwhafintech.com/fullchain.pem
wc -l certs/cloudflare/hanwhafintech.com/privkey.pem
ls -la certs/cloudflare/glimpse-go.site/
wc -l certs/cloudflare/glimpse-go.site/fullchain.pem
wc -l certs/cloudflare/glimpse-go.site/privkey.pem
```

## Start Docker Nginx

Use `docker-compose` on the dev server if Compose v2 is not available.

```bash
cd /Users/tri/nginx-docker
docker-compose down
docker-compose up -d
docker exec glimpse-nginx nginx -t
docker ps
```

If `nginx -t` passes, Nginx is running.

Reload after config changes:

```bash
docker exec glimpse-nginx nginx -s reload
```

View logs:

```bash
docker logs --tail=80 glimpse-nginx
```

## Test Current Routing

From the dev server:

```bash
curl -k -I --resolve task-dev.hanwhafintech.com:443:127.0.0.1 https://task-dev.hanwhafintech.com
curl -k -I --resolve task-api-dev.hanwhafintech.com:443:127.0.0.1 https://task-api-dev.hanwhafintech.com
curl -k -I --resolve task.hanwhafintech.com:443:127.0.0.1 https://task.hanwhafintech.com
curl -k -I --resolve task-api.hanwhafintech.com:443:127.0.0.1 https://task-api.hanwhafintech.com
curl -k -I --resolve embed.glimpse-go.site:443:127.0.0.1 https://embed.glimpse-go.site
curl -k -I --resolve rerank.glimpse-go.site:443:127.0.0.1 https://rerank.glimpse-go.site
curl -k -I --resolve mlx.glimpse-go.site:443:127.0.0.1 https://mlx.glimpse-go.site
```

Expected:

- HTTP requests redirect to HTTPS
- Known HTTPS hosts serve through the configured upstreams
- `502 Bad Gateway` means Nginx is running but the matching service upstream is not reachable

From another machine:

```bash
curl -I https://task-dev.hanwhafintech.com
curl -I https://task-api-dev.hanwhafintech.com/api/health
curl -I https://task.hanwhafintech.com
curl -I https://task-api.hanwhafintech.com/api/health
curl -I https://embed.glimpse-go.site
```

Unknown hosts should close the connection instead of falling through to the default upstream:

```bash
curl -i -H "Host: a.glimpse-go.site" http://127.0.0.1
```

Expected:

```txt
curl: (52) Empty reply from server
```

In a browser, this behaves like an unreachable site instead of showing a response from Ollama or another upstream.

## Long LLM Responses

Ollama chat requests can take longer than normal HTTP API calls, especially with larger models and `stream: false`.

Prefer streaming for manual tests:

```json
{
  "model": "deepseek-v2:16b",
  "messages": [
    {
      "role": "user",
      "content": "why is the sky blue?"
    }
  ],
  "stream": true
}
```

When `stream` is `false`, Ollama does not send the response until generation is complete. That can hit the client timeout before Nginx or Ollama fails. In Postman, set `Settings -> General -> Request timeout in ms` to `0` for no client timeout, or use a larger value such as `600000`.

The Nginx image is configured for long upstream responses:

```nginx
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
proxy_buffering off;
```

After changing Nginx timeout config, build and deploy the Nginx image again:

```bash
git add nginx-docker docs
git commit -m "Tune gateway timeouts for long chat responses"
git push origin main
```

If the hostname is proxied through Cloudflare and a non-streaming request takes more than Cloudflare's proxy read timeout, Nginx cannot fix that. Use `stream: true`, reduce the model/output size, use a DNS-only hostname for long-running private tests, or call the Mac Studio service through an SSH tunnel.

## Renew HTTPS Certificate

Create or renew the Cloudflare Origin Certificates for:

```txt
hanwhafintech.com
*.hanwhafintech.com
glimpse-go.site
*.glimpse-go.site
```

Save the certificate and private key temporarily on the dev server, then install them with the cert manager:

```bash
cd /Users/tri/nginx-docker

./scripts/certs.sh install cloudflare hanwhafintech.com \
  /tmp/hanwhafintech.com.fullchain.pem \
  /tmp/hanwhafintech.com.privkey.pem
./scripts/certs.sh check cloudflare hanwhafintech.com

./scripts/certs.sh install cloudflare glimpse-go.site \
  /tmp/glimpse-go.site.fullchain.pem \
  /tmp/glimpse-go.site.privkey.pem
./scripts/certs.sh check cloudflare glimpse-go.site
```

Make sure `.env` uses full SSL:

```env
NGINX_TEMPLATE_MODE=ssl
```

Restart and test:

```bash
docker compose down
docker compose up -d
./scripts/certs.sh reload

curl -k -I --resolve task-dev.hanwhafintech.com:443:127.0.0.1 https://task-dev.hanwhafintech.com
curl -k -I --resolve task-api-dev.hanwhafintech.com:443:127.0.0.1 https://task-api-dev.hanwhafintech.com
curl -k -I --resolve task.hanwhafintech.com:443:127.0.0.1 https://task.hanwhafintech.com
curl -k -I --resolve task-api.hanwhafintech.com:443:127.0.0.1 https://task-api.hanwhafintech.com
curl -k -I --resolve embed.glimpse-go.site:443:127.0.0.1 https://embed.glimpse-go.site
curl -k -I --resolve rerank.glimpse-go.site:443:127.0.0.1 https://rerank.glimpse-go.site
curl -k -I --resolve mlx.glimpse-go.site:443:127.0.0.1 https://mlx.glimpse-go.site
```

Cloudflare DNS should use proxied `A` records.

In the `hanwhafintech.com` zone:

```txt
A    task-dev       <dev-server-public-ip>
A    task-api-dev   <dev-server-public-ip>
A    task           <dev-server-public-ip>
A    task-api       <dev-server-public-ip>
```

In the `glimpse-go.site` zone:

```txt
A    embed      <dev-server-public-ip>
A    rerank     <dev-server-public-ip>
A    mlx        <dev-server-public-ip>
```

Use Cloudflare SSL/TLS mode `Full (strict)` after the origin certificate is installed.

## Troubleshooting

Check what template is mounted:

```bash
docker inspect glimpse-nginx --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Check that Docker can see the Cloudflare Origin cert:

```bash
docker exec glimpse-nginx ls -la /etc/ssl/cloudflare/hanwhafintech.com/
docker exec glimpse-nginx ls -la /etc/ssl/cloudflare/glimpse-go.site/
```

If Docker cannot connect to Colima:

```bash
colima start
docker ps
```

If image pull fails with `docker-credential-desktop`, remove the broken credential helper from `~/.docker/config.json`, then retry:

```bash
docker-compose up -d
```

For certificate add, update, remove, and backup operations, see `docs/nginx-cert-management.md`.

## Private Service Access

From the same LAN, tunnel directly to Mac Studio:

```bash
ssh -L 8123:127.0.0.1:8123 admin@<macstudio-lan-ip>
ssh -L 9000:127.0.0.1:9000 admin@<macstudio-lan-ip>
ssh -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
ssh -L 8082:127.0.0.1:8082 admin@<macstudio-lan-ip>
```

From outside the LAN, use the dev server as a jump host:

```bash
ssh -J tri@hanwhafintech.com -L 8123:127.0.0.1:8123 admin@<macstudio-lan-ip>
ssh -J tri@hanwhafintech.com -L 9000:127.0.0.1:9000 admin@<macstudio-lan-ip>
ssh -J tri@hanwhafintech.com -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
ssh -J tri@hanwhafintech.com -L 8082:127.0.0.1:8082 admin@<macstudio-lan-ip>
```

Then connect local tools to `localhost`:

```txt
ClickHouse HTTP: localhost:8123
ClickHouse TCP:  localhost:9000
Postgres:        localhost:5433
Kafka UI:        http://localhost:8082
```
