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
  RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime
  RUNTIME_SOURCE_DIR=deploy-runtime/macstudio/glimpse-monitor

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
COMPOSE_FILE_WAS_SET="${COMPOSE_FILE+x}"
ENV_FILE_WAS_SET="${ENV_FILE+x}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-infra/.env}"
RUNTIME_DIR="${RUNTIME_DIR:-}"

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

prepare_runtime_dir() {
  [ -n "$RUNTIME_DIR" ] || return 0

  case "$RUNTIME_DIR" in
    /*) ;;
    *) RUNTIME_DIR="$HOME/$RUNTIME_DIR" ;;
  esac

  RUNTIME_SOURCE_DIR="${RUNTIME_SOURCE_DIR:-$PROJECT_DIR/deploy-runtime/macstudio/glimpse-monitor}"
  case "$RUNTIME_SOURCE_DIR" in
    /*) ;;
    *) RUNTIME_SOURCE_DIR="$PROJECT_DIR/$RUNTIME_SOURCE_DIR" ;;
  esac

  if [ ! -d "$RUNTIME_SOURCE_DIR" ]; then
    echo "ERROR: runtime source directory does not exist: $RUNTIME_SOURCE_DIR" >&2
    exit 1
  fi

  mkdir -p "$RUNTIME_DIR"
  cp -R "$RUNTIME_SOURCE_DIR"/. "$RUNTIME_DIR"/

  if [ ! -f "$RUNTIME_DIR/.env" ]; then
    cp "$RUNTIME_DIR/.env.example" "$RUNTIME_DIR/.env"
    echo "Created runtime env file: $RUNTIME_DIR/.env"
  fi

  case "$ENV_FILE" in
    */glimpse-monitor/infra/.env)
      echo "Ignoring repo checkout env path for runtime deploy: $ENV_FILE"
      ENV_FILE="$RUNTIME_DIR/.env"
      ;;
  esac

  if [ -z "$COMPOSE_FILE_WAS_SET" ] || [ "$COMPOSE_FILE" = "infra/docker-compose.yml" ]; then
    COMPOSE_FILE="$RUNTIME_DIR/docker-compose.yml"
  fi

  if [ -z "$ENV_FILE_WAS_SET" ] || [ "$ENV_FILE" = "infra/.env" ]; then
    ENV_FILE="$RUNTIME_DIR/.env"
  fi

  export POSTGRES_INIT_SQL="${POSTGRES_INIT_SQL:-$RUNTIME_DIR/sql/monitor_schema.sql}"
}

prepare_runtime_dir

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
    set -a
    # shellcheck disable=SC1090
    . "$env_file"
    set +a
  fi
  export DOCKERHUB_NAMESPACE="$NAMESPACE"
  export IMAGE_PREFIX="$IMAGE_PREFIX"
  export IMAGE_TAG="$IMAGE_TAG"
  export DASHBOARD_IMAGE="$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
  export AI_SERVICE_IMAGE="$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
  export WORKERS_IMAGE="$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
  if docker compose version >/dev/null 2>&1; then
    docker compose -f "$compose_file" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "$compose_file" "$@"
  else
    echo "ERROR: docker compose or docker-compose is required." >&2
    echo "PATH: $PATH" >&2
    exit 1
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
if [ -n "$RUNTIME_DIR" ]; then
  echo "Runtime dir:    $RUNTIME_DIR"
fi
echo "Compose file:   $(resolve_path "$COMPOSE_FILE")"
echo "Env file:       $(resolve_path "$ENV_FILE")"
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
