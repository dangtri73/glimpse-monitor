#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Build and push one Glimpse Monitor service image to Docker Hub.

Usage:
  ./scripts/docker-build-push.sh <dashboard|ai-service|workers|all>

Required env:
  DOCKERHUB_NAMESPACE=dangtri73

Optional env:
  IMAGE_TAG=latest                    Image tag to push. Defaults to git short SHA, then timestamp.
  IMAGE_PREFIX=glimpse-monitor        Image repo prefix.
  DOCKER_PLATFORM=linux/arm64         Target platform for Mac Studio. Use linux/amd64 for x86 servers.
  PUSH_LATEST=true                    Also push :latest when IMAGE_TAG is not latest.

Examples:
  DOCKERHUB_NAMESPACE=dangtri73 IMAGE_TAG=local-latest ./scripts/docker-build-push.sh ai-service
  DOCKERHUB_NAMESPACE=dangtri73 IMAGE_TAG="$(git rev-parse --short HEAD)" ./scripts/docker-build-push.sh all
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

SERVICE="${1:-}"
if [ -z "$SERVICE" ]; then
  usage
  exit 1
fi

NAMESPACE="${DOCKERHUB_NAMESPACE:-${DOCKER_NAMESPACE:-}}"
if [ -z "$NAMESPACE" ]; then
  echo "ERROR: set DOCKERHUB_NAMESPACE, for example: DOCKERHUB_NAMESPACE=dangtri73" >&2
  exit 1
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
IMAGE_PREFIX="${IMAGE_PREFIX:-glimpse-monitor}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-linux/arm64}"
PUSH_LATEST="${PUSH_LATEST:-true}"

if [ -z "${IMAGE_TAG:-}" ]; then
  if command -v git >/dev/null 2>&1 && git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    IMAGE_TAG="$(git -C "$PROJECT_DIR" rev-parse --short HEAD)"
  else
    IMAGE_TAG="$(date -u +%Y%m%dT%H%M%SZ)"
  fi
fi

service_context() {
  case "$1" in
    dashboard) echo "dashboard" ;;
    ai-service) echo "ai-service" ;;
    workers) echo "workers" ;;
    *) return 1 ;;
  esac
}

build_one() {
  service="$1"
  context="$(service_context "$service")"
  image="$NAMESPACE/$IMAGE_PREFIX-$service"

  tags="-t $image:$IMAGE_TAG"
  if [ "$PUSH_LATEST" = "true" ] && [ "$IMAGE_TAG" != "latest" ]; then
    tags="$tags -t $image:latest"
  fi

  echo "Building $service -> $image:$IMAGE_TAG ($DOCKER_PLATFORM)"
  # shellcheck disable=SC2086
  docker build \
    --pull \
    --platform "$DOCKER_PLATFORM" \
    $tags \
    "$PROJECT_DIR/$context"

  docker push "$image:$IMAGE_TAG"
  if [ "$PUSH_LATEST" = "true" ] && [ "$IMAGE_TAG" != "latest" ]; then
    docker push "$image:latest"
  fi
}

case "$SERVICE" in
  all)
    build_one dashboard
    build_one ai-service
    build_one workers
    ;;
  dashboard|ai-service|workers)
    build_one "$SERVICE"
    ;;
  *)
    echo "ERROR: unknown service: $SERVICE" >&2
    usage
    exit 1
    ;;
esac
