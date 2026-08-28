# Glimpse Nginx Gateway Domain File Map

## Source Templates

- `nginx-docker/nginx/templates-http/domains.conf.template`
  - HTTP-only mode. Every public domain route needs a `listen 80` server block.
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
task-dev.hanwhafintech.com      -> http://${MACSTUDIO_LAN_IP}:3000
task-api-dev.hanwhafintech.com  -> http://${MACSTUDIO_LAN_IP}:4000
task.hanwhafintech.com          -> http://${MACSTUDIO_LAN_IP}:3001
task-api.hanwhafintech.com      -> http://${MACSTUDIO_LAN_IP}:4001
report-st.hanwhafintech.com     -> http://${MACSTUDIO_LAN_IP}:3002
report-st-api.hanwhafintech.com -> http://${MACSTUDIO_LAN_IP}:3003
report.hanwhafintech.com        -> http://${MACSTUDIO_LAN_IP}:3005
report-api.hanwhafintech.com    -> http://${MACSTUDIO_LAN_IP}:3004
api-rag-runtime-st.hanwhafintech.com -> http://${MACSTUDIO_LAN_IP}:18000
h-q1.hanwhafintech.com          -> http://${MACSTUDIO_LAN_IP}:9000
h-assistant-playground.hanwhafintech.com -> http://${MACSTUDIO_LAN_IP}:18100
embed.glimpse-go.site           -> http://${MACSTUDIO_LAN_IP}:8089
rerank.glimpse-go.site          -> http://${MACSTUDIO_LAN_IP}:8090
mlx.glimpse-go.site             -> http://${MACSTUDIO_LAN_IP}:8088
mlx-classify.glimpse-go.site    -> http://${MACSTUDIO_LAN_IP}:8092
mlx-vlm.glimpse-go.site         -> http://${MACSTUDIO_LAN_IP}:8093
```

## Current HTTPS Certificate

Use two Cloudflare Origin Certificate directories:

```txt
certs/cloudflare/glimpse-go.site/fullchain.pem
certs/cloudflare/glimpse-go.site/privkey.pem
certs/cloudflare/hanwhafintech.com/fullchain.pem
certs/cloudflare/hanwhafintech.com/privkey.pem
```

The glimpse certificate must include:

```txt
glimpse-go.site
*.glimpse-go.site
```

The hanwha certificate must include:

```txt
hanwhafintech.com
*.hanwhafintech.com
```

`*.hanwhafintech.com` covers every one-label Hanwha host listed above, including `api-rag-runtime-st.hanwhafintech.com`. It does not cover two-label hosts such as `api.dev.hanwhafintech.com`.
