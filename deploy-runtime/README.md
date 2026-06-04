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
./deploy.sh dashboard
./deploy.sh ai-service
./deploy.sh workers
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

## CI Usage

GitHub Actions can still build and deploy automatically. These runtime bundles are also safe for manual recovery because target machines only need Docker, Docker Compose, the runtime folder, and the `.env` file.
