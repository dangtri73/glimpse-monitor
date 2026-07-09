# Docker Nginx Gateway Image

This folder is the Docker image build context only. It contains the Nginx
templates, snippets, entrypoint selector, Dockerfile, and local build script.

Runtime compose/env files live here:

```txt
../deploy-runtime/dev-server/nginx-docker
```

## Build And Push

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/nginx-docker

./build.sh trace

./build.sh push
```

Optional platform override:

```bash
DOCKER_PLATFORM=linux/arm64 ./build.sh push
```

## Deploy

Deploy from the runtime bundle, not this build directory:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/deploy-runtime/dev-server/nginx-docker
./deploy.sh deploy dangtri73/glimpse-nginx:latest
```

The runtime bundle owns:

```txt
docker-compose.yml
.env.example
.env
deploy.sh
certs/
nginx/generated/
```

## Trace Scope

`./build.sh trace` validates only the build context:

- Dockerfile source paths
- Nginx template directories
- Nginx snippets
- runtime template variables required by each `NGINX_TEMPLATE_MODE`

It intentionally does not read `docker-compose.yml` or `.env` from this folder.
