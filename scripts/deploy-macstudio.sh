#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Pull Docker Hub images and run Glimpse Monitor on Mac Studio.

Usage:
  ./scripts/deploy-macstudio.sh <dashboard|ai-service|workers|agent|all|stack>

Required shell env or ENV_FILE value for Docker image targets:
  DOCKERHUB_NAMESPACE=dangtri73

Optional env:
  IMAGE_TAG=latest
  IMAGE_PREFIX=glimpse-monitor
  COMPOSE_FILE=infra/docker-compose.yml
  ENV_FILE=infra/.env
  RUNTIME_DIR=/Users/admin/glimpse-monitor-runtime
  RUNTIME_SOURCE_DIR=deploy-runtime/macstudio/glimpse-monitor
  AGENT_SOURCE_DIR=agent

Modes:
  dashboard   Pull/run dashboard only.
  ai-service  Pull/run AI service only.
  workers     Pull/run gateway worker containers.
  agent       Copy/run the host monitor agent as a launchd service.
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

upsert_env_file() {
  key="$1"
  value="$2"
  file="$(resolve_path "$ENV_FILE")"

  [ -f "$file" ] || return 0

  if grep -q "^$key=" "$file"; then
    sed -i.bak "s|^$key=.*|$key=$value|" "$file"
    rm -f "$file.bak"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$file"
  fi
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

  AGENT_SOURCE_DIR="${AGENT_SOURCE_DIR:-$PROJECT_DIR/agent}"
  case "$AGENT_SOURCE_DIR" in
    /*) ;;
    *) AGENT_SOURCE_DIR="$PROJECT_DIR/$AGENT_SOURCE_DIR" ;;
  esac

  if [ -d "$AGENT_SOURCE_DIR" ]; then
    rm -rf "$RUNTIME_DIR/agent"
    mkdir -p "$RUNTIME_DIR/agent"
    cp -R "$AGENT_SOURCE_DIR"/. "$RUNTIME_DIR/agent"/
  elif [ "$TARGET" = "agent" ]; then
    echo "ERROR: agent source directory does not exist: $AGENT_SOURCE_DIR" >&2
    exit 1
  fi

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

target_needs_images() {
  case "$1" in
    agent) return 1 ;;
    *) return 0 ;;
  esac
}

NAMESPACE="${DOCKERHUB_NAMESPACE:-${DOCKER_NAMESPACE:-$(env_value DOCKERHUB_NAMESPACE)}}"
if target_needs_images "$TARGET" && [ -z "$NAMESPACE" ]; then
  echo "ERROR: set DOCKERHUB_NAMESPACE in the shell or $ENV_FILE" >&2
  exit 1
fi
NAMESPACE="${NAMESPACE:-dangtri73}"

IMAGE_PREFIX="${IMAGE_PREFIX:-$(env_value IMAGE_PREFIX)}"
IMAGE_PREFIX="${IMAGE_PREFIX:-glimpse-monitor}"
IMAGE_TAG="${IMAGE_TAG:-$(env_value IMAGE_TAG)}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if target_needs_images "$TARGET"; then
  case "$TARGET" in
    dashboard)
      export DASHBOARD_IMAGE="$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
      ;;
    ai-service)
      export AI_SERVICE_IMAGE="$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
      ;;
    workers)
      export WORKERS_IMAGE="$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
      ;;
    all|stack)
      export DASHBOARD_IMAGE="$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
      export AI_SERVICE_IMAGE="$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
      export WORKERS_IMAGE="$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
      ;;
  esac
fi

export_target_images() {
  export DOCKERHUB_NAMESPACE="$NAMESPACE"
  export IMAGE_PREFIX="$IMAGE_PREFIX"
  export IMAGE_TAG="$IMAGE_TAG"

  case "$TARGET" in
    dashboard)
      export DASHBOARD_IMAGE="$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
      ;;
    ai-service)
      export AI_SERVICE_IMAGE="$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
      ;;
    workers)
      export WORKERS_IMAGE="$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
      ;;
    all|stack)
      export DASHBOARD_IMAGE="$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
      export AI_SERVICE_IMAGE="$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
      export WORKERS_IMAGE="$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
      ;;
  esac
}

sync_target_env_file() {
  target_needs_images "$TARGET" || return 0

  upsert_env_file DOCKERHUB_NAMESPACE "$NAMESPACE"
  upsert_env_file IMAGE_PREFIX "$IMAGE_PREFIX"
  upsert_env_file IMAGE_TAG "$IMAGE_TAG"

  case "$TARGET" in
    dashboard)
      upsert_env_file DASHBOARD_IMAGE "$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
      ;;
    ai-service)
      upsert_env_file AI_SERVICE_IMAGE "$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
      ;;
    workers)
      upsert_env_file WORKERS_IMAGE "$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
      ;;
    all|stack)
      upsert_env_file DASHBOARD_IMAGE "$NAMESPACE/$IMAGE_PREFIX-dashboard:$IMAGE_TAG"
      upsert_env_file AI_SERVICE_IMAGE "$NAMESPACE/$IMAGE_PREFIX-ai-service:$IMAGE_TAG"
      upsert_env_file WORKERS_IMAGE "$NAMESPACE/$IMAGE_PREFIX-workers:$IMAGE_TAG"
      ;;
  esac
}

compose() {
  env_file="$(resolve_path "$ENV_FILE")"
  compose_file="$(resolve_path "$COMPOSE_FILE")"
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$env_file"
    set +a
  fi
  export_target_images
  if docker compose version >/dev/null 2>&1; then
    docker compose --env-file "$env_file" -f "$compose_file" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose --env-file "$env_file" -f "$compose_file" "$@"
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

if [ "$TARGET" = "agent" ]; then
  SERVICES=""
elif SERVICES="$(services_for_target "$TARGET")"; then
  :
else
  echo "ERROR: unknown target: $TARGET" >&2
  usage
  exit 1
fi

echo "Deploy target: $TARGET"
if [ -n "$RUNTIME_DIR" ]; then
  echo "Runtime dir:    $RUNTIME_DIR"
fi
echo "Compose file:   $(resolve_path "$COMPOSE_FILE")"
echo "Env file:       $(resolve_path "$ENV_FILE")"
if target_needs_images "$TARGET"; then
  [ -z "${DASHBOARD_IMAGE:-}" ] || echo "Dashboard image:  $DASHBOARD_IMAGE"
  [ -z "${AI_SERVICE_IMAGE:-}" ] || echo "AI service image: $AI_SERVICE_IMAGE"
  [ -z "${WORKERS_IMAGE:-}" ] || echo "Workers image:    $WORKERS_IMAGE"
fi

if [ "$TARGET" = "agent" ]; then
  [ -n "$RUNTIME_DIR" ] || { echo "ERROR: RUNTIME_DIR is required for agent deploy." >&2; exit 1; }
  "$RUNTIME_DIR/deploy.sh" agent
elif [ "$TARGET" = "stack" ]; then
  sync_target_env_file
  compose pull
  compose up -d --no-build
  if [ -n "$RUNTIME_DIR" ]; then
    "$RUNTIME_DIR/deploy.sh" agent
  fi
else
  sync_target_env_file
  # shellcheck disable=SC2086
  compose pull $SERVICES
  if [ "$TARGET" = "dashboard" ]; then
    compose up -d --no-build --no-deps dashboard
  else
    # shellcheck disable=SC2086
    compose up -d --no-build $SERVICES
  fi
  if [ "$TARGET" = "all" ] && [ -n "$RUNTIME_DIR" ]; then
    "$RUNTIME_DIR/deploy.sh" agent
  fi
fi

if [ "$TARGET" != "agent" ]; then
  compose ps
fi
