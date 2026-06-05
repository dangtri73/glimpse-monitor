# GitHub Actions Runner Commands

Useful commands for the Mac Studio self-hosted GitHub Actions runner.

Assumed runner directory:

```bash
cd ~/actions-runner
```

## Service Mode

Use service mode for normal operation. It keeps the runner alive after the terminal closes.

Check status:

```bash
./svc.sh status
```

Install service:

```bash
./svc.sh install
```

Start service:

```bash
./svc.sh start
```

Stop service:

```bash
./svc.sh stop
```

Restart service:

```bash
./svc.sh stop
./svc.sh start
./svc.sh status
```

If the service command asks for root permission, use `sudo` for the same command:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

Run the service as the same macOS user that can run Docker.

## Foreground Mode

Use foreground mode only for quick debugging:

```bash
./run.sh
```

Stop foreground mode:

```txt
Ctrl+C
```

Do not run `./run.sh` while the service is already running for the same runner registration.

## Runner Logs

Find runner logs:

```bash
find ~/Library/Logs -iname "*runner*" -type f
```

Follow runner logs:

```bash
tail -f ~/Library/Logs/actions.runner.dangtri73-glimpse-monitor.macstudio/*.log
```

If the exact path does not exist, use the file path returned by `find`.

GitHub has the best step-by-step job logs:

```txt
GitHub repo -> Actions -> workflow run -> build-and-deploy
```

## Docker Checks

Run these from the same Mac Studio user that runs the runner:

```bash
docker version
docker compose version
docker run --rm hello-world
```

Test Nginx image build:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/nginx-docker
docker pull nginx:1.27-alpine
docker build --pull --platform linux/arm64 -t glimpse-nginx-test .
docker run --rm \
  -e NGINX_TEMPLATE_MODE=http \
  -e DEFAULT_UPSTREAM=http://127.0.0.1:11435 \
  glimpse-nginx-test nginx -t
```

If Docker exits with code `130`, the Docker process was interrupted. Check Docker Desktop or Colima, then rerun the build.

If GitHub Actions fails with `/var/run/docker.sock: permission denied`, the runner service is using the wrong Docker socket. The workflows try these macOS sockets automatically:

```txt
~/.docker/run/docker.sock
~/.colima/default/docker.sock
/Users/admin/.docker/run/docker.sock
/Users/admin/.colima/default/docker.sock
```

To inspect the socket from the working terminal:

```bash
docker context inspect --format '{{ (index .Endpoints "docker").Host }}'
```

If auto-detection still fails, set this GitHub Actions repository variable to the socket path:

```txt
MACSTUDIO_DOCKER_SOCKET=/Users/admin/.docker/run/docker.sock
```

If `docker login` fails in GitHub Actions with this macOS Keychain error:

```txt
User interaction is not allowed. (-25308)
```

the runner service is trying to save credentials through the desktop credential helper. The workflows avoid that by writing Docker Hub auth into a temporary CI `DOCKER_CONFIG` instead of running `docker login`.

## Workflow Reruns

Manual app-service deploy:

```txt
GitHub repo -> Actions -> Build and deploy app services -> Run workflow
```

Choose one:

```txt
all
dashboard
ai-service
workers
```

Manual Nginx deploy:

```txt
GitHub repo -> Actions -> Build and deploy Nginx -> Run workflow
```

## Runtime Commands

Mac Studio does not need a manually maintained `glimpse-monitor` repo checkout for runtime. The GitHub runner checks out code under its `_work` directory for each job. Runtime files live in:

```txt
/Users/admin/glimpse-monitor-runtime
```

Recommended GitHub Actions repository variables for Mac Studio app services:

```txt
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
MACSTUDIO_RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime
MACSTUDIO_ENV_FILE=/Users/admin/glimpse-monitor-runtime/.env
```

`MACSTUDIO_ENV_FILE` is not a repo checkout path. It is the persistent Docker runtime env file on Mac Studio.

On Mac Studio:

```bash
cd /Users/admin/glimpse-monitor-runtime
docker compose --env-file .env -f docker-compose.yml ps
docker compose --env-file .env -f docker-compose.yml logs --tail=80 dashboard
```

On the dev server for Nginx:

```bash
cd /Users/tri/nginx-docker
docker compose ps
docker logs --tail=80 glimpse-nginx
docker exec glimpse-nginx nginx -t
```

This path should match the GitHub Actions variable:

```txt
DEV_NGINX_DOCKER_DIR=/Users/tri/nginx-docker
MACSTUDIO_LAN_IP=<macstudio-lan-ip>
```

If deploy fails with a permission error such as:

```txt
mkdir: /Users/vutri: Permission denied
```

the repository variable is still pointing to the Mac Studio checkout path. Change `DEV_NGINX_DOCKER_DIR` to the dev-server runtime path:

```txt
/Users/tri/nginx-docker
```
