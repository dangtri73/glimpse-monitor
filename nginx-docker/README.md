# Docker Nginx Gateway

Dockerized Nginx reverse proxy for the Glimpse dev server.

The Compose stack can run a Docker Hub image built from this repo:

```env
NGINX_IMAGE=dangtri73/glimpse-nginx:latest
```

For GitHub Actions, use the monorepo workflows in `../.github/workflows/`.

## What This Exposes

- `dev.api.hftvn.com`
- `glimpse-go.site`
- `www.glimpse-go.site`

All base domains proxy to `DEFAULT_UPSTREAM`. Use the mixed template while only `dev.api.hftvn.com` has a certificate, then switch to full SSL mode after `glimpse-go.site` certificates exist. On the dev server, set `MACSTUDIO_LAN_IP` to the Mac Studio LAN address reachable from the gateway.

The current dev-server runtime directory is:

```txt
/Users/tri/nginx-docker
```

## Before Starting

Stop Homebrew Nginx so Docker can bind ports `80` and `443`:

```bash
brew services stop nginx
sudo nginx -s stop
```

Check that the ports are free:

```bash
sudo lsof -i :80
sudo lsof -i :443
```

If either command prints an Nginx process, stop it before starting this stack.

## Start

Start Docker Nginx only:

```bash
cd /Users/tri/nginx-docker
cp .env.example .env
./scripts/certs.sh sync-letsencrypt dev.api.hftvn.com
./scripts/certs.sh check letsencrypt dev.api.hftvn.com
nano .env
docker-compose up -d
docker exec glimpse-nginx nginx -t
```

This stack defaults to `NGINX_TEMPLATE_MODE=dev-ssl`, which uses the existing `dev.api.hftvn.com` Let's Encrypt certificate and keeps `glimpse-go.site` on HTTP. If you have not copied the cert yet, temporarily set `NGINX_TEMPLATE_MODE=http` in `.env`.

Reload after config changes:

```bash
docker exec glimpse-nginx nginx -s reload
```

## Certificate Paths

Template modes:

```env
NGINX_TEMPLATE_MODE=http       # HTTP only, no certs required
NGINX_TEMPLATE_MODE=dev-ssl    # dev.api HTTPS, glimpse HTTP
NGINX_TEMPLATE_MODE=ssl        # HTTPS for both domains
```

Recommended current mode, since the `dev.api.hftvn.com` cert exists:

```env
NGINX_TEMPLATE_MODE=dev-ssl
```

For the dev server with Colima, keep a Docker-readable copy under this project instead of mounting host `/etc/letsencrypt` directly. The container still sees the cert at `/etc/letsencrypt/live/dev.api.hftvn.com/fullchain.pem`.

The Docker container mounts:

```txt
DEV_SSL_HOST_DIR       -> /etc/letsencrypt inside the container
GLIMPSE_SSL_HOST_DIR   -> /etc/ssl/cloudflare inside the container
```

Default `.env` values:

```env
DEV_DOMAIN=dev.api.hftvn.com
DEV_SSL_HOST_DIR=./certs/letsencrypt
DEV_SSL_CERTIFICATE=/etc/letsencrypt/live/dev.api.hftvn.com/fullchain.pem
DEV_SSL_CERTIFICATE_KEY=/etc/letsencrypt/live/dev.api.hftvn.com/privkey.pem

GLIMPSE_DOMAIN=glimpse-go.site
GLIMPSE_WWW_DOMAIN=www.glimpse-go.site
GLIMPSE_SSL_HOST_DIR=./certs/cloudflare
GLIMPSE_SSL_CERTIFICATE=/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem
GLIMPSE_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/glimpse-go.site/privkey.pem
```

If you run Docker on a Linux server instead of Colima, you can mount the system directory directly:

```env
DEV_SSL_HOST_DIR=/etc/letsencrypt
```

For `glimpse-go.site`, create a Cloudflare Origin Certificate for:

```txt
glimpse-go.site
*.glimpse-go.site
```

Save it temporarily on the dev server, then install it with:

```bash
./scripts/certs.sh install cloudflare glimpse-go.site \
  /tmp/glimpse-go.site.fullchain.pem \
  /tmp/glimpse-go.site.privkey.pem
./scripts/certs.sh check cloudflare glimpse-go.site
```

Then enable full SSL mode and restart:

```bash
nano .env
# set NGINX_TEMPLATE_MODE=ssl
docker-compose up -d
./scripts/certs.sh reload
```

## Member Domain Mappings

The monitor agent can generate member domain routes into:

```txt
nginx/generated/domain-maps.conf
```

This file is included by the Docker Nginx config. Live writes are disabled unless the agent is started with:

```env
GLIMPSE_AGENT_ENABLE_NGINX_APPLY=true
```

The command arrays live in `agent/config/devices.json` under `domainGateway.nginx`. Keep them as explicit arrays such as:

```json
["docker", "exec", "glimpse-nginx", "nginx", "-t"]
```

## Configure The Upstream

Edit `.env` on the dev server so `MACSTUDIO_LAN_IP` points to the Mac Studio service host:

```env
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

After changing `.env`, run the runtime deploy script. It rewrites `DEFAULT_UPSTREAM`, `DASHBOARD_UPSTREAM`, `AI_UPSTREAM`, and `OLLAMA_UPSTREAM` from `MACSTUDIO_LAN_IP`.

```bash
./deploy.sh deploy
docker exec glimpse-nginx nginx -t
```

## Cloudflare DNS

Point `glimpse-go.site` to the dev server public IP:

```txt
A    glimpse-go.site    115.73.213.75
A    www                115.73.213.75
```

Use orange-cloud proxied records and set Cloudflare SSL/TLS mode to `Full (strict)` when using the Cloudflare Origin Certificate mounted above.

If running in HTTP-only mode, use Cloudflare HTTP/Flexible only for temporary testing. Do not use `Full (strict)` until SSL mode and origin certificates are ready.

## Test Routing

From the dev server:

```bash
curl -I -H "Host: dev.api.hftvn.com" http://127.0.0.1
curl -I -H "Host: glimpse-go.site" http://127.0.0.1
```

After enabling `templates-dev-ssl`:

```bash
curl -k -I --resolve dev.api.hftvn.com:443:127.0.0.1 https://dev.api.hftvn.com
```

After enabling `templates-ssl`:

```bash
curl -k -I --resolve glimpse-go.site:443:127.0.0.1 https://glimpse-go.site
```

From your Mac:

```bash
curl -I https://dev.api.hftvn.com
curl -I http://glimpse-go.site
curl -I https://glimpse-go.site
```
