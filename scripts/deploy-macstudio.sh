#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Pull Docker Hub images and run Glimpse Monitor on Mac Studio.

Usage:
  ./scripts/deploy-macstudio.sh <dashboard|ai-service|workers|all|stack>

Required shell env or ENV_FILE value:
  DOCKERHUB_NAMESPACE=dangtri73

Optional env:
  IMAGE_TAG=latest
  IMAGE_PREFIX=glimpse-monitor
  COMPOSE_FILE=infra/docker-compose.yml
  ENV_FILE=infra/.env

Modes:
  dashboard   Pull/run dashboard only.
  ai-service  Pull/run AI service only.
  workers     Pull/run gateway worker containers.
  all         Pull/run custom app images: dashboard, ai-service, workers.
  stack       Pull/run the full compose stack, including databases and Grafana.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

TARGET="${1:-all}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-infra/.env}"

resolve_path() {
  case "$1" in
    /*) echo "$1" ;;
    *) echo "$PROJECT_DIR/$1" ;;
  esac
}

env_value() {
  key="$1"
  file="$(resolve_path "$ENV_FILE")"
  if [ ! -f "$file" ]; then
    return 0
  fi
  sed -n "s/^$key=//p" "$file" | tail -n 1
}

NAMESPACE="${DOCKERHUB_NAMESPACE:-${DOCKER_NAMESPACE:-$(env_value DOCKERHUB_NAMESPACE)}}"
if [ -z "$NAMESPACE" ]; then
  echo "ERROR: set DOCKERHUB_NAMESPACE in the shell or $ENV_FILE" >&2
  exit 1
fi

IMAGE_PREFIX="${IMAGE_PREFIX:-$(env_value IMAGE_PREFIX)}"
IMAGE_PREFIX="${IMAGE_PREFIX:-glimpse-monitor}"
IMAGE_TAG="${IMAGE_TAG:-$(env_value IMAGE_TAG)}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

export DASHBOARD_IMAGE="$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
export AI_SERVICE_IMAGE="$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
export WORKERS_IMAGE="$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"

compose() {
  env_file="$(resolve_path "$ENV_FILE")"
  compose_file="$(resolve_path "$COMPOSE_FILE")"
  if [ -f "$env_file" ]; then
    docker compose --env-file "$env_file" -f "$compose_file" "$@"
  else
    docker compose -f "$compose_file" "$@"
  fi
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

SERVICES="$(services_for_target "$TARGET")" || {
  echo "ERROR: unknown target: $TARGET" >&2
  usage
  exit 1
}

echo "Deploy target: $TARGET"
echo "Dashboard image:  $DASHBOARD_IMAGE"
echo "AI service image: $AI_SERVICE_IMAGE"
echo "Workers image:    $WORKERS_IMAGE"

if [ "$TARGET" = "stack" ]; then
  compose pull
  compose up -d --no-build
else
  # shellcheck disable=SC2086
  compose pull $SERVICES
  # shellcheck disable=SC2086
  compose up -d --no-build $SERVICES
fi

compose ps
