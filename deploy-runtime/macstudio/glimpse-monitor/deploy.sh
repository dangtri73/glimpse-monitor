#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Deploy Glimpse Monitor app services from Docker Hub.

Usage:
  ./deploy.sh <stack|all|dashboard|ai-service|workers>
  ./deploy.sh status
  ./deploy.sh logs [service]
  ./deploy.sh restart <dashboard|ai-service|workers>
  ./deploy.sh stop <dashboard|ai-service|workers|all|stack>

Examples:
  ./deploy.sh stack
  IMAGE_TAG=abc1234 ./deploy.sh dashboard
  IMAGE_TAG=abc1234 ./deploy.sh all
  ./deploy.sh logs dashboard
EOF
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REQUESTED_DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-}"
REQUESTED_IMAGE_PREFIX="${IMAGE_PREFIX:-}"
REQUESTED_IMAGE_TAG="${IMAGE_TAG:-}"

ensure_env() {
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  fi
}

load_env() {
  ensure_env
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a

  [ -z "$REQUESTED_DOCKERHUB_NAMESPACE" ] || export DOCKERHUB_NAMESPACE="$REQUESTED_DOCKERHUB_NAMESPACE"
  [ -z "$REQUESTED_IMAGE_PREFIX" ] || export IMAGE_PREFIX="$REQUESTED_IMAGE_PREFIX"
  [ -z "$REQUESTED_IMAGE_TAG" ] || export IMAGE_TAG="$REQUESTED_IMAGE_TAG"
}

compose() {
  load_env
  if docker compose version >/dev/null 2>&1; then
    docker compose -f docker-compose.yml "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f docker-compose.yml "$@"
  else
    echo "ERROR: docker compose or docker-compose is required." >&2
    echo "PATH: $PATH" >&2
    exit 1
  fi
}

upsert_env() {
  key="$1"
  value="$2"
  file=".env"

  if grep -q "^$key=" "$file"; then
    sed -i.bak "s|^$key=.*|$key=$value|" "$file"
    rm -f "$file.bak"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$file"
  fi
}

sync_image_env() {
  load_env

  namespace="${DOCKERHUB_NAMESPACE:-dangtri73}"
  prefix="${IMAGE_PREFIX:-glimpse-monitor}"
  tag="${IMAGE_TAG:-latest}"

  upsert_env DOCKERHUB_NAMESPACE "$namespace"
  upsert_env IMAGE_PREFIX "$prefix"
  upsert_env IMAGE_TAG "$tag"
  upsert_env DASHBOARD_IMAGE "$namespace/$prefix-dashboard:$tag"
  upsert_env AI_SERVICE_IMAGE "$namespace/$prefix-ai-service:$tag"
  upsert_env WORKERS_IMAGE "$namespace/$prefix-workers:$tag"
}

services_for_target() {
  case "$1" in
    dashboard) echo "dashboard" ;;
    ai-service) echo "ai-service" ;;
    workers) echo "gateway-request-enricher gateway-analytics-writer" ;;
    all) echo "dashboard ai-service gateway-request-enricher gateway-analytics-writer" ;;
    stack) echo "" ;;
    *) return 1 ;;
  esac
}

deploy_target() {
  target="$1"
  services="$(services_for_target "$target")" || {
    echo "ERROR: unknown deploy target: $target" >&2
    usage >&2
    exit 1
  }

  sync_image_env

  echo "Deploy target: $target"
  echo "Runtime dir:    $SCRIPT_DIR"
  echo "Compose file:   $SCRIPT_DIR/docker-compose.yml"
  echo "Env file:       $SCRIPT_DIR/.env"

  if [ "$target" = "stack" ]; then
    compose pull
    compose up -d --no-build
  else
    # shellcheck disable=SC2086
    compose pull $services
    # shellcheck disable=SC2086
    compose up -d --no-build $services
  fi

  compose ps
}

cmd="${1:-all}"

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  stack|all|dashboard|ai-service|workers)
    deploy_target "$cmd"
    ;;
  status|ps)
    compose ps
    ;;
  logs)
    if [ -n "${2:-}" ]; then
      compose logs -f --tail="${TAIL:-200}" "$2"
    else
      compose logs -f --tail="${TAIL:-200}"
    fi
    ;;
  restart)
    target="${2:-}"
    [ -n "$target" ] || { usage >&2; exit 1; }
    services="$(services_for_target "$target")" || { usage >&2; exit 1; }
    # shellcheck disable=SC2086
    compose restart $services
    ;;
  stop)
    target="${2:-all}"
    services="$(services_for_target "$target")" || { usage >&2; exit 1; }
    if [ "$target" = "stack" ]; then
      compose stop
    else
      # shellcheck disable=SC2086
      compose stop $services
    fi
    ;;
  *)
    echo "ERROR: unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
