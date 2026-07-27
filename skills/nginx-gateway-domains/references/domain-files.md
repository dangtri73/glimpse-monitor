# Glimpse Nginx Gateway Domain File Map

## Source Templates

- `nginx-docker/nginx/templates-http/domains.conf.template`
  - HTTP-only mode. Every public domain route needs a `listen 80` server block.
- `nginx-docker/nginx/templates-dev-ssl/domains.conf.template`
  - `DEV_DOMAIN` has HTTPS. `glimpse-go.site` subdomains are HTTP-only.
- `nginx-docker/nginx/templates-ssl/domains.conf.template`
  - Full HTTPS mode. Add subdomains to the port 80 redirect `server_name` list and add a matching `listen 443 ssl` server block.

## Runtime Config

- `deploy-runtime/dev-server/nginx-docker/.env.example`
  - Canonical runtime env baseline copied to `.env`.
- `deploy-runtime/dev-server/nginx-docker/docker-compose.yml`
  - Pass every template variable to the nginx container.
- `deploy-runtime/dev-server/nginx-docker/deploy.sh`
  - Derive Mac Studio upstreams from `MACSTUDIO_LAN_IP`.
  - Validate every required variable appears in `docker compose config`.
  - Remove stale deleted route variables from `.env`.

## Validation And Documentation

- `.github/workflows/nginx-docker.yml`
  - Docker image validation command must pass every template variable.
- `nginx-docker/build.sh`
  - Template contract guards belong here.
- `deploy-runtime/README.md`
- `docs/nginx-docker-gateway.md`
- `docs/github-actions-runner.md`
- `docs/dockerhub-deploy.md`

## Current Public Routes

```txt
front.glimpse-go.site  -> http://${MACSTUDIO_LAN_IP}:3000
back.glimpse-go.site   -> http://${MACSTUDIO_LAN_IP}:4000
embed.glimpse-go.site  -> http://${MACSTUDIO_LAN_IP}:8089
rerank.glimpse-go.site -> http://${MACSTUDIO_LAN_IP}:8090
mlx.glimpse-go.site    -> http://${MACSTUDIO_LAN_IP}:8088
dev.api.hftvn.com      -> http://host.docker.internal:5000
```
