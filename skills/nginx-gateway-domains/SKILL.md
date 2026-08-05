---
name: nginx-gateway-domains
description: Manage Glimpse nginx Docker gateway domain routes. Use when adding, removing, renaming, or changing public subdomains, upstream ports, nginx template modes, Cloudflare HTTPS behavior, or the build/push/deploy workflow touching nginx-docker, deploy-runtime/dev-server/nginx-docker, docs, or .github/workflows/nginx-docker.yml.
---

# Nginx Gateway Domains

## Core Workflow

Before editing, inspect `git status --short` and preserve unrelated worktree changes. This repo often has unrelated runtime or service changes pending; do not revert them.

Read `references/domain-files.md` when changing routes. It lists every file that must stay synchronized.

For each route change:

1. Update both nginx templates:
   - `nginx-docker/nginx/templates-http/domains.conf.template`
   - `nginx-docker/nginx/templates-ssl/domains.conf.template`
2. Update dev-server runtime config:
   - `deploy-runtime/dev-server/nginx-docker/.env.example`
   - `deploy-runtime/dev-server/nginx-docker/docker-compose.yml`
   - `deploy-runtime/dev-server/nginx-docker/deploy.sh`
3. Update validation and docs:
   - `.github/workflows/nginx-docker.yml`
   - `nginx-docker/build.sh`
   - `deploy-runtime/README.md`
   - `docs/nginx-docker-gateway.md`
   - `docs/github-actions-runner.md`
   - `docs/dockerhub-deploy.md`
4. Run `scripts/nginx-gateway-release.sh check`.
5. Give build/push/deploy commands from `scripts/nginx-gateway-release.sh`.

## Route Rules

Use explicit variables per public service:

```env
TASK_DEV_DOMAIN=task-dev.hanwhafintech.com
TASK_DEV_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3000
TASK_DEV_API_DOMAIN=task-api-dev.hanwhafintech.com
TASK_DEV_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4000
TASK_PROD_DOMAIN=task.hanwhafintech.com
TASK_PROD_UPSTREAM=http://${MACSTUDIO_LAN_IP}:3001
TASK_PROD_API_DOMAIN=task-api.hanwhafintech.com
TASK_PROD_API_UPSTREAM=http://${MACSTUDIO_LAN_IP}:4001
MLX_CLASSIFY_DOMAIN=mlx-classify.glimpse-go.site
MLX_CLASSIFY_UPSTREAM=http://${MACSTUDIO_LAN_IP}:8092
```

For Mac Studio services, derive upstreams in `deploy.sh` from `MACSTUDIO_LAN_IP`. For services running directly on the dev Mac mini host, use `http://host.docker.internal:<port>` and keep the compose `extra_hosts` mapping.

When removing a route, remove both `*_DOMAIN` and `*_UPSTREAM` from templates, compose, `.env.example`, CI, and docs. Add `remove_env OLD_DOMAIN` and `remove_env OLD_UPSTREAM` in `deploy.sh` so old runtime `.env` files are cleaned on deploy.

For normal HTTP services, include:

```nginx
include /etc/nginx/snippets/proxy-headers.conf;
```

Use `mlx-stream-proxy.conf` only for the existing MLX streaming route unless there is a specific streaming requirement.

## HTTPS Modes

Use `NGINX_TEMPLATE_MODE=ssl` when public domains must work over HTTPS through Cloudflare. The current runtime uses two Cloudflare cert directories:

```txt
certs/cloudflare/glimpse-go.site/fullchain.pem
certs/cloudflare/glimpse-go.site/privkey.pem
certs/cloudflare/hanwhafintech.com/fullchain.pem
certs/cloudflare/hanwhafintech.com/privkey.pem
```

Use `GLIMPSE_SSL_CERTIFICATE` for `glimpse-go.site` routes. Use `HANWHA_SSL_CERTIFICATE` for one-label `hanwhafintech.com` subdomains such as `task-dev`, `task-api-dev`, `task`, and `task-api`.

Cloudflare should normally use `Full (strict)` once the origin certificate is installed.

## Validation And Release

Run:

```bash
scripts/nginx-gateway-release.sh check
```

Build and push the nginx image:

```bash
DOCKER_PLATFORM=linux/arm64 scripts/nginx-gateway-release.sh build-push
```

Deploy on a dev server shell:

```bash
cd /Users/tri/nginx-docker
./deploy.sh deploy
```

Deploy remotely through SSH:

```bash
DEV_NGINX_HOST=tri@hanwhafintech.com scripts/nginx-gateway-release.sh deploy-remote
```

Build, push, and deploy remotely:

```bash
DEV_NGINX_HOST=tri@hanwhafintech.com scripts/nginx-gateway-release.sh all-remote
```
