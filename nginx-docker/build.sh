#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Build and validate the Glimpse Nginx gateway image.

This directory is only the Docker image build context. Runtime compose/env
files live in ../deploy-runtime/dev-server/nginx-docker.

Usage:
  ./build.sh trace
  ./build.sh check
  ./build.sh build [image]
  ./build.sh push

Examples:
  ./build.sh trace
  ./build.sh build
  ./build.sh push

Defaults:
  image: dangtri73/glimpse-nginx:latest

Environment overrides:
  DOCKER_PLATFORM=linux/arm64
EOF
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

FAILURES=0

log() {
  printf '%s\n' "$*"
}

fail() {
  FAILURES=$((FAILURES + 1))
  printf 'ERROR: %s\n' "$*" >&2
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

require_file() {
  path="$1"

  if [ -f "$path" ]; then
    printf '  %-40s %s\n' "$path" "ok"
  else
    printf '  %-40s %s\n' "$path" "missing"
    fail "required file is missing: $path"
  fi
}

require_dir() {
  path="$1"

  if [ -d "$path" ]; then
    printf '  %-40s %s\n' "$path" "ok"
  else
    printf '  %-40s %s\n' "$path" "missing"
    fail "required directory is missing: $path"
  fi
}

require_dockerfile_copy() {
  source="$1"

  if grep -Fq "COPY $source " Dockerfile; then
    printf '  %-40s %s\n' "COPY $source" "ok"
  else
    printf '  %-40s %s\n' "COPY $source" "missing"
    fail "Dockerfile does not copy required source: $source"
  fi
}

template_dir_for_mode() {
  mode="$1"

  case "$mode" in
    http) printf '%s\n' "nginx/templates-http" ;;
    ssl) printf '%s\n' "nginx/templates-ssl" ;;
    *) return 1 ;;
  esac
}

template_vars() {
  grep -Roh '\${[A-Za-z_][A-Za-z0-9_]*}' "$@" 2>/dev/null \
    | sed 's/^\${//; s/}$//' \
    | sort -u \
    | tr '\n' ' '
}

trace_build_context() {
  log "== Build Context =="
  require_file Dockerfile
  require_file docker-entrypoint.d/05-select-template-mode.sh
  require_dir nginx/templates-http
  require_dir nginx/templates-ssl
  require_dir nginx/snippets
  require_file nginx/snippets/ssl.conf
  require_file nginx/snippets/proxy-headers.conf
  require_file nginx/snippets/mlx-stream-proxy.conf
}

trace_dockerfile_contract() {
  log ""
  log "== Dockerfile Contract =="
  require_dockerfile_copy docker-entrypoint.d/05-select-template-mode.sh
  require_dockerfile_copy nginx/templates-http
  require_dockerfile_copy nginx/templates-ssl
  require_dockerfile_copy nginx/snippets
}

trace_template_contract() {
  log ""
  log "== Runtime Template Modes =="

  for mode in http ssl; do
    dir="$(template_dir_for_mode "$mode")"
    require_file "$dir/domains.conf.template"
    vars="$(template_vars "$dir")"
    printf '  %-40s %s\n' "$mode" "$vars"
  done

  for var in FRONT_DOMAIN BACK_DOMAIN EMBED_DOMAIN RERANK_DOMAIN MLX_DOMAIN; do
    if ! grep -Fq "\${$var}" nginx/templates-ssl/domains.conf.template; then
      fail "$var is not registered in nginx/templates-ssl/domains.conf.template"
    fi
  done

  for var in DASHBOARD_DOMAIN AI_DOMAIN OLLAMA_DOMAIN DASHBOARD_UPSTREAM AI_UPSTREAM OLLAMA_UPSTREAM DEV_DOMAIN DEV_UPSTREAM DEFAULT_UPSTREAM DEV_SSL_CERTIFICATE DEV_SSL_CERTIFICATE_KEY GLIMPSE_DOMAIN GLIMPSE_WWW_DOMAIN; do
    if grep -R -F "\${$var}" nginx/templates-http nginx/templates-ssl >/dev/null 2>&1; then
      fail "$var is still referenced by an nginx template"
    fi
  done

  log ""
  log "== Runtime Env Contract =="
  template_vars nginx/templates-http nginx/templates-ssl 2>/dev/null || true
  log ""
  log "Runtime values are supplied by ../deploy-runtime/dev-server/nginx-docker/.env and docker-compose.yml."
}

trace_config() {
  trace_build_context
  trace_dockerfile_contract
  trace_template_contract

  if [ "$FAILURES" -ne 0 ]; then
    log ""
    fail "$FAILURES validation issue(s) found."
    exit 1
  fi

  log ""
  log "Trace complete: build context is valid."
}

canonical_image() {
  printf '%s\n' "dangtri73/glimpse-nginx:latest"
}

default_image() {
  canonical_image
}

docker_build() {
  image="$1"

  if [ -n "${DOCKER_PLATFORM:-}" ]; then
    log "docker build --platform $DOCKER_PLATFORM -t $image ."
    docker build --platform "$DOCKER_PLATFORM" -t "$image" .
  else
    log "docker build -t $image ."
    docker build -t "$image" .
  fi
}

build_image() {
  image="$1"

  trace_config

  log ""
  log "== Build =="
  docker_build "$image"
  log "Built image: $image"
}

push_image() {
  image="$1"
  expected="$(canonical_image)"

  if [ "$image" != "$expected" ]; then
    fail "Nginx image pushes must use $expected, got: $image"
    exit 1
  fi

  build_image "$image"

  log ""
  log "== Push =="
  log "docker push $image"
  docker push "$image"
  log "Pushed image: $image"
}

cmd="${1:-build}"

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  trace|check)
    trace_config
    ;;
  build)
    build_image "${2:-$(default_image)}"
    ;;
  push|build-push)
    push_image "${2:-$(default_image)}"
    ;;
  *)
    build_image "$cmd"
    ;;
esac
