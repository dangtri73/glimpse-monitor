#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Validate, build, push, and deploy the Glimpse nginx gateway.

Usage:
  scripts/nginx-gateway-release.sh check
  scripts/nginx-gateway-release.sh build-push
  scripts/nginx-gateway-release.sh deploy-local
  scripts/nginx-gateway-release.sh deploy-remote
  scripts/nginx-gateway-release.sh all-local
  scripts/nginx-gateway-release.sh all-remote
  scripts/nginx-gateway-release.sh print

Environment:
  DOCKER_PLATFORM        Default: linux/arm64
  NGINX_IMAGE            Default: dangtri73/glimpse-nginx:latest
  DEV_NGINX_HOST         Required for deploy-remote/all-remote, e.g. tri@hanwhafintech.com
  DEV_NGINX_DOCKER_DIR   Default: /Users/tri/nginx-docker
EOF
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
NGINX_DIR="$PROJECT_DIR/nginx-docker"
RUNTIME_DIR="$PROJECT_DIR/deploy-runtime/dev-server/nginx-docker"

IMAGE="${NGINX_IMAGE:-dangtri73/glimpse-nginx:latest}"
PLATFORM="${DOCKER_PLATFORM:-linux/arm64}"
REMOTE_DIR="${DEV_NGINX_DOCKER_DIR:-/Users/tri/nginx-docker}"

has_docker_compose() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

check_compose_config() {
  if ! has_docker_compose; then
    echo "WARN: docker compose is unavailable; skipping compose config validation." >&2
    return 0
  fi

  (
    cd "$RUNTIME_DIR"
    set -a
    . ./.env.example
    set +a
    docker compose config --quiet
  )
}

check_gateway() {
  (
    cd "$NGINX_DIR"
    ./build.sh check
  )

  sh -n "$NGINX_DIR/build.sh"
  sh -n "$RUNTIME_DIR/deploy.sh"
  check_compose_config

  if command -v git >/dev/null 2>&1; then
    (
      cd "$PROJECT_DIR"
      git diff --check
    )
  fi
}

build_push() {
  (
    cd "$NGINX_DIR"
    DOCKER_PLATFORM="$PLATFORM" ./build.sh push "$IMAGE"
  )
}

deploy_local() {
  (
    cd "$RUNTIME_DIR"
    ./deploy.sh deploy "$IMAGE"
  )
}

deploy_remote() {
  if [ -z "${DEV_NGINX_HOST:-}" ]; then
    echo "ERROR: DEV_NGINX_HOST is required, e.g. DEV_NGINX_HOST=tri@hanwhafintech.com" >&2
    exit 1
  fi

  ssh "$DEV_NGINX_HOST" "cd '$REMOTE_DIR' && ./deploy.sh deploy '$IMAGE'"
}

print_commands() {
  cat <<EOF
# Validate locally
scripts/nginx-gateway-release.sh check

# Build and push nginx image
DOCKER_PLATFORM=$PLATFORM scripts/nginx-gateway-release.sh build-push

# Deploy from a shell on the dev server
cd $REMOTE_DIR
./deploy.sh deploy

# Or deploy remotely from this repo
DEV_NGINX_HOST=tri@hanwhafintech.com scripts/nginx-gateway-release.sh deploy-remote
EOF
}

cmd="${1:-check}"

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  check)
    check_gateway
    ;;
  build-push)
    build_push
    ;;
  deploy-local)
    deploy_local
    ;;
  deploy-remote)
    deploy_remote
    ;;
  all-local)
    check_gateway
    build_push
    deploy_local
    ;;
  all-remote)
    check_gateway
    build_push
    deploy_remote
    ;;
  print)
    print_commands
    ;;
  *)
    echo "ERROR: unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
