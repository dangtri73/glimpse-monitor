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
dashboard.glimpse-go.site  -> http://<macstudio-lan-ip>:3000
ai.glimpse-go.site         -> http://<macstudio-lan-ip>:8771
ollama.glimpse-go.site     -> http://<macstudio-lan-ip>:11435
mlx.glimpse-go.site        -> http://<macstudio-lan-ip>:8088
dev.api.hftvn.com          -> http://host.docker.internal:5000
```

Do not route Postgres, Kafka, ClickHouse, Redis, Qdrant, Prometheus, Grafana, Adminer, or Kafka UI through public Nginx. Use SSH tunnels for those private ports.

## Current Domains

```txt
dev.api.hftvn.com
glimpse-go.site
www.glimpse-go.site
```

The default upstream is:

```env
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
DEV_UPSTREAM=http://host.docker.internal:5000
DEFAULT_UPSTREAM=http://${MACSTUDIO_LAN_IP}:11435
DASHBOARD_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3000
AI_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8771
OLLAMA_UPSTREAM=http://${MACSTUDIO_LAN_IP}:11435
MLX_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8088
```

Change `MACSTUDIO_LAN_IP` in `/Users/tri/nginx-docker/.env` when the Mac Studio LAN IP changes, then run `./deploy.sh deploy`. The deploy script rewrites the upstream URLs from that one value.

For GitHub Actions deploys, set the repository variable with the same value:

```txt
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

The examples below assume the current dev-server runtime directory:

```txt
/Users/tri/nginx-docker
```

## Template Modes

`nginx-docker` has three template modes:

```env
NGINX_TEMPLATE_MODE=http       # HTTP only, no certs required
NGINX_TEMPLATE_MODE=dev-ssl    # dev.api HTTPS, glimpse HTTP
NGINX_TEMPLATE_MODE=ssl        # HTTPS for both domains
```

Recommended current mode:

```env
NGINX_TEMPLATE_MODE=dev-ssl
```

Use this while `dev.api.hftvn.com` has a Let's Encrypt certificate and `glimpse-go.site` does not have its Cloudflare Origin Certificate yet.

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
DEV_DOMAIN=dev.api.hftvn.com
GLIMPSE_DOMAIN=glimpse-go.site
GLIMPSE_WWW_DOMAIN=www.glimpse-go.site
DASHBOARD_DOMAIN=dashboard.glimpse-go.site
AI_DOMAIN=ai.glimpse-go.site
OLLAMA_DOMAIN=ollama.glimpse-go.site
MLX_DOMAIN=mlx.glimpse-go.site

NGINX_IMAGE=dangtri73/glimpse-nginx:latest
NGINX_TEMPLATE_MODE=dev-ssl

DEV_SSL_HOST_DIR=./certs/letsencrypt
DEV_SSL_CERTIFICATE=/etc/letsencrypt/live/dev.api.hftvn.com/fullchain.pem
DEV_SSL_CERTIFICATE_KEY=/etc/letsencrypt/live/dev.api.hftvn.com/privkey.pem

GLIMPSE_SSL_HOST_DIR=./certs/cloudflare
GLIMPSE_SSL_CERTIFICATE=/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem
GLIMPSE_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/glimpse-go.site/privkey.pem

MACSTUDIO_LAN_IP=<macstudio-lan-ip>
DEV_UPSTREAM=http://host.docker.internal:5000
DEFAULT_UPSTREAM=http://${MACSTUDIO_LAN_IP}:11435
DASHBOARD_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3000
AI_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8771
OLLAMA_UPSTREAM=http://${MACSTUDIO_LAN_IP}:11435
MLX_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8088
```

## Copy The Existing Dev API Certificate

The Let's Encrypt files under `/etc/letsencrypt/live/...` are symlinks. Use `cp -L` so Docker gets real files.

```bash
cd /Users/tri/nginx-docker
./scripts/certs.sh sync-letsencrypt dev.api.hftvn.com
./scripts/certs.sh check letsencrypt dev.api.hftvn.com
```

Check that files exist:

```bash
ls -la certs/letsencrypt/live/dev.api.hftvn.com/
wc -l certs/letsencrypt/live/dev.api.hftvn.com/fullchain.pem
wc -l certs/letsencrypt/live/dev.api.hftvn.com/privkey.pem
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
curl -I -H "Host: glimpse-go.site" http://127.0.0.1
curl -I -H "Host: www.glimpse-go.site" http://127.0.0.1
curl -k -I --resolve dev.api.hftvn.com:443:127.0.0.1 https://dev.api.hftvn.com
```

Expected:

- `glimpse-go.site` returns HTTP response while using `templates-dev-ssl`
- `dev.api.hftvn.com` redirects HTTP to HTTPS and serves HTTPS
- `502 Bad Gateway` means Nginx is running but the matching upstream, such as `DEV_UPSTREAM` or `DEFAULT_UPSTREAM`, is not reachable

From another machine:

```bash
curl -I http://glimpse-go.site
curl -I https://dev.api.hftvn.com
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

## Add HTTPS For Glimpse

Create a Cloudflare Origin Certificate for:

```txt
glimpse-go.site
*.glimpse-go.site
```

Save the certificate and private key temporarily on the dev server, then install them with the cert manager:

```bash
cd /Users/tri/nginx-docker

./scripts/certs.sh install cloudflare glimpse-go.site \
  /tmp/glimpse-go.site.fullchain.pem \
  /tmp/glimpse-go.site.privkey.pem
./scripts/certs.sh check cloudflare glimpse-go.site
```

Then edit `.env`:

```env
NGINX_TEMPLATE_MODE=ssl
```

Restart and test:

```bash
docker-compose down
docker-compose up -d
./scripts/certs.sh reload

curl -k -I --resolve glimpse-go.site:443:127.0.0.1 https://glimpse-go.site
curl -k -I --resolve www.glimpse-go.site:443:127.0.0.1 https://www.glimpse-go.site
```

Cloudflare DNS should use proxied `A` records:

```txt
A    @          <dev-server-public-ip>
A    www        <dev-server-public-ip>
A    dashboard  <dev-server-public-ip>
A    ai         <dev-server-public-ip>
A    ollama     <dev-server-public-ip>
```

Use Cloudflare SSL/TLS mode `Full (strict)` after the origin certificate is installed.

## Troubleshooting

Check what template is mounted:

```bash
docker inspect glimpse-nginx --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Check that Docker can see the dev API cert:

```bash
docker exec glimpse-nginx ls -la /etc/letsencrypt/live/dev.api.hftvn.com/
```

Check that Docker can see the glimpse cert after full SSL is enabled:

```bash
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
ssh -J tri@dev.hftvn.com -L 8123:127.0.0.1:8123 admin@<macstudio-lan-ip>
ssh -J tri@dev.hftvn.com -L 9000:127.0.0.1:9000 admin@<macstudio-lan-ip>
ssh -J tri@dev.hftvn.com -L 5433:127.0.0.1:5433 admin@<macstudio-lan-ip>
ssh -J tri@dev.hftvn.com -L 8082:127.0.0.1:8082 admin@<macstudio-lan-ip>
```

Then connect local tools to `localhost`:

```txt
ClickHouse HTTP: localhost:8123
ClickHouse TCP:  localhost:9000
Postgres:        localhost:5433
Kafka UI:        http://localhost:8082
```
