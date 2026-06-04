# GitHub Actions Runner On Mac Studio

Use this when GitHub Actions runs on the Mac Studio and deploys Docker Nginx to the dev server.

Target flow:

```txt
GitHub push
  -> Mac Studio self-hosted GitHub Actions runner
  -> build dangtri73/glimpse-nginx:<commit>
  -> push image to Docker Hub
  -> SSH to dev server
  -> docker compose pull nginx && docker compose up -d --no-build nginx
```

## 1. Install Docker On Mac Studio

Use Docker Desktop or Colima. Confirm the Docker CLI works:

```bash
docker version
docker compose version
docker run --rm hello-world
```

For Colima:

```bash
colima start
docker context use colima
docker version
```

## 2. Add A GitHub Self-Hosted Runner

In GitHub:

1. Open `dangtri73/glimpse-monitor`.
2. Go to `Settings > Actions > Runners`.
3. Click `New self-hosted runner`.
4. Choose `macOS`.
5. Choose `ARM64`.
6. Run the download and configure commands GitHub shows.

When `./config.sh` asks for labels, add:

```txt
macstudio
```

GitHub automatically adds the labels `self-hosted`, `macOS`, and `ARM64`. The Nginx workflow uses all four labels:

```yaml
runs-on: [self-hosted, macOS, ARM64, macstudio]
```

## 3. Start The Runner

For a foreground test:

```bash
./run.sh
```

For a background service:

```bash
./svc.sh install
./svc.sh start
./svc.sh status
```

If the service already exists:

```bash
./svc.sh stop
./svc.sh start
./svc.sh status
```

Run the service as the same macOS user that can run `docker version`. If GitHub's generated command uses `sudo`, confirm Docker is also available to that service user before relying on background runs.

## 4. Create The Deploy SSH Key

Create a dedicated key on Mac Studio:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_github_nginx_dev
```

Install the public key on the dev server:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_github_nginx_dev.pub admin@dev.hftvn.com
```

If `ssh-copy-id` is not available:

```bash
cat ~/.ssh/id_ed25519_github_nginx_dev.pub
ssh admin@dev.hftvn.com
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Test from Mac Studio:

```bash
ssh -i ~/.ssh/id_ed25519_github_nginx_dev admin@dev.hftvn.com \
  "cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/nginx-docker && docker compose ps"
```

## 5. Prepare The Dev Server Once

On the dev server:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/nginx-docker
git pull --ff-only
cp .env.example .env
nano .env
docker login
```

The first `git pull` is important because the dev server must have the updated `docker-compose.yml` that reads `NGINX_IMAGE`. Later deploys only update the image tag in `.env` and restart the compose service.

Use this baseline:

```env
NGINX_IMAGE=dangtri73/glimpse-nginx:latest
NGINX_TEMPLATE_MODE=dev-ssl
DEFAULT_UPSTREAM=http://192.168.1.3:11435
```

Keep the existing certificate setup from `README.md`. The workflow does not copy private certificates.

## 6. Add GitHub Repository Secrets And Variables

Create this Docker Hub repository before the first workflow run:

```txt
dangtri73/glimpse-nginx
```

In GitHub, go to `Settings > Secrets and variables > Actions`.

Repository secrets:

```txt
DOCKERHUB_USERNAME=dangtri73
DOCKERHUB_TOKEN=<dockerhub-access-token>
DEV_SSH_HOST=dev.hftvn.com
DEV_SSH_USER=admin
DEV_SSH_PRIVATE_KEY=<contents-of- ~/.ssh/id_ed25519_github_nginx_dev>
```

Repository variables:

```txt
DOCKERHUB_NAMESPACE=dangtri73
DEV_SSH_PORT=22
DEV_NGINX_DOCKER_DIR=/Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/nginx-docker
DOCKER_PLATFORM=linux/arm64
```

## 7. Run The Workflow

Push a change under `nginx-docker/**` to `main`, or run it manually from `Actions > Build and deploy Nginx > Run workflow`.

GitHub Actions will:

1. Build and validate the custom Nginx image.
2. Push `dangtri73/glimpse-nginx:<short-sha>` to Docker Hub.
3. Tag `dangtri73/glimpse-nginx:latest` on `main`.
4. SSH to the dev server.
5. Update `NGINX_IMAGE` in `.env`.
6. Pull and restart only the `nginx` compose service.
7. Run `docker exec glimpse-nginx nginx -t`.

For a Linux or Intel deploy target, set the repository variable:

```txt
DOCKER_PLATFORM=linux/amd64
```

## Monorepo Path Filter

The Nginx workflow lives at:

```txt
.github/workflows/nginx-docker.yml
```

It only runs automatically when these paths change:

```yaml
paths:
  - "nginx-docker/**"
  - ".github/workflows/nginx-docker.yml"
```

Other services should use their own workflow files with their own `paths` blocks.

The app service workflow lives at:

```txt
.github/workflows/app-services.yml
```

It watches:

```yaml
paths:
  - "dashboard/**"
  - "ai-service/**"
  - "workers/**"
  - "infra/**"
  - "scripts/**"
  - ".github/workflows/app-services.yml"
```

The app workflow deploys directly on Mac Studio. The Nginx workflow deploys to the dev server over SSH.
