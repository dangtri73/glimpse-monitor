# Nginx Docker Gateway Usage

## Purpose

Use Docker Nginx on the dev server as the public gateway only.

Current target:

```txt
Internet -> dev server Docker Nginx -> Mac Studio service
```

The dev server owns public ports `80` and `443`. Application services stay on Mac Studio or another internal machine. For SSH and Mac Studio connection details, see `../../docs/connections.md`.

## Current Domains

```txt
dev.api.hftvn.com
glimpse-go.site
www.glimpse-go.site
```

The default upstream is:

```env
DEFAULT_UPSTREAM=http://192.168.1.3:11435
```

Change `DEFAULT_UPSTREAM` in `glimpse-monitor/nginx-docker/.env` when the gateway should proxy to a different Mac Studio service.

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

NGINX_IMAGE=dangtri73/glimpse-nginx:latest
NGINX_TEMPLATE_MODE=dev-ssl

DEV_SSL_HOST_DIR=./certs/letsencrypt
DEV_SSL_CERTIFICATE=/etc/letsencrypt/live/dev.api.hftvn.com/fullchain.pem
DEV_SSL_CERTIFICATE_KEY=/etc/letsencrypt/live/dev.api.hftvn.com/privkey.pem

GLIMPSE_SSL_HOST_DIR=./certs/cloudflare
GLIMPSE_SSL_CERTIFICATE=/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem
GLIMPSE_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/glimpse-go.site/privkey.pem

DEFAULT_UPSTREAM=http://192.168.1.3:11435
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
- `502 Bad Gateway` means Nginx is running but `DEFAULT_UPSTREAM` is not reachable

From another machine:

```bash
curl -I http://glimpse-go.site
curl -I https://dev.api.hftvn.com
```

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
A    @      <dev-server-public-ip>
A    www    <dev-server-public-ip>
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
