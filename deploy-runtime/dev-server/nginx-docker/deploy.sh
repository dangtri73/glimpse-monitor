#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Deploy the Glimpse Nginx gateway runtime.

Usage:
  ./deploy.sh deploy
  ./deploy.sh status
  ./deploy.sh logs
  ./deploy.sh test
  ./deploy.sh reload
  ./deploy.sh restart
  ./deploy.sh stop
  ./deploy.sh certs <certs.sh args...>

Examples:
  ./deploy.sh deploy
  ./deploy.sh certs list
  ./deploy.sh certs check cloudflare glimpse-go.site
  ./deploy.sh certs check cloudflare hanwhafintech.com
EOF
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

CANONICAL_NGINX_IMAGE="dangtri73/glimpse-nginx:latest"

export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ensure_env() {
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  fi
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "ERROR: docker compose or docker-compose is required." >&2
    echo "PATH: $PATH" >&2
    exit 1
  fi
}

nginx_test() {
  attempts="${1:-20}"
  i=1

  while [ "$i" -le "$attempts" ]; do
    if docker exec glimpse-nginx nginx -t; then
      return 0
    fi

    echo "Waiting for glimpse-nginx to accept docker exec ($i/$attempts)..." >&2
    sleep 2
    i=$((i + 1))
  done

  echo "ERROR: nginx config test failed after $attempts attempts." >&2
  compose ps nginx >&2 || true
  compose logs --tail=80 nginx >&2 || true
  docker logs --tail=80 glimpse-nginx >&2 || true
  return 1
}

normalize_image() {
  image="${1:-}"

  case "$image" in
    ""|latest|"$CANONICAL_NGINX_IMAGE")
      printf '%s\n' "$CANONICAL_NGINX_IMAGE"
      ;;
    *)
      echo "ERROR: Nginx deploy always uses $CANONICAL_NGINX_IMAGE, got: $image" >&2
      echo "Run: ./deploy.sh deploy" >&2
      exit 1
      ;;
  esac
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

remove_env() {
  key="$1"
  file=".env"

  if [ -f "$file" ] && grep -q "^$key=" "$file"; then
    sed -i.bak "/^$key=/d" "$file"
    rm -f "$file.bak"
  fi
}

env_value() {
  key="$1"
  file=".env"

  if [ ! -f "$file" ]; then
    return 0
  fi

  sed -n "s|^$key=||p" "$file" | tail -n 1
}

upsert_env_if_missing_or_legacy() {
  key="$1"
  value="$2"
  shift 2

  current="$(env_value "$key")"
  if [ -z "$current" ]; then
    upsert_env "$key" "$value"
    return 0
  fi

  for legacy_value in "$@"; do
    if [ "$current" = "$legacy_value" ]; then
      upsert_env "$key" "$value"
      return 0
    fi
  done
}

sync_macstudio_upstreams() {
  ensure_env

  macstudio_lan_ip="${MACSTUDIO_LAN_IP:-$(env_value MACSTUDIO_LAN_IP)}"
  if [ -z "$macstudio_lan_ip" ]; then
    echo "ERROR: MACSTUDIO_LAN_IP is required in .env or as an environment variable." >&2
    exit 1
  fi

  case "$macstudio_lan_ip" in
    *[!A-Za-z0-9_.-]*)
      echo "ERROR: MACSTUDIO_LAN_IP contains unsupported characters: $macstudio_lan_ip" >&2
      exit 1
      ;;
  esac

  upsert_env MACSTUDIO_LAN_IP "$macstudio_lan_ip"
  remove_env DASHBOARD_DOMAIN
  remove_env AI_DOMAIN
  remove_env OLLAMA_DOMAIN
  remove_env DASHBOARD_UPSTREAM
  remove_env AI_UPSTREAM
  remove_env OLLAMA_UPSTREAM
  remove_env DEV_DOMAIN
  remove_env DEV_UPSTREAM
  remove_env DEFAULT_UPSTREAM
  remove_env DEV_SSL_HOST_DIR
  remove_env DEV_SSL_CERTIFICATE
  remove_env DEV_SSL_CERTIFICATE_KEY
  remove_env GLIMPSE_DOMAIN
  remove_env GLIMPSE_WWW_DOMAIN
  remove_env FRONT_DOMAIN
  remove_env BACK_DOMAIN
  remove_env FRONT_UPSTREAM
  remove_env BACK_UPSTREAM

  upsert_env_if_missing_or_legacy TASK_DEV_DOMAIN "task-dev.hanwhafintech.com" \
    "front.glimpse-go.site"
  upsert_env_if_missing_or_legacy TASK_DEV_API_DOMAIN "task-api-dev.hanwhafintech.com" \
    "back.glimpse-go.site"
  upsert_env_if_missing_or_legacy TASK_PROD_DOMAIN "task.hanwhafintech.com"
  upsert_env_if_missing_or_legacy TASK_PROD_API_DOMAIN "task-api.hanwhafintech.com"
  upsert_env_if_missing_or_legacy EMBED_DOMAIN "embed.glimpse-go.site" \
    "embed.hanwhafintech.com"
  upsert_env_if_missing_or_legacy RERANK_DOMAIN "rerank.glimpse-go.site" \
    "rerank.hanwhafintech.com"
  upsert_env_if_missing_or_legacy MLX_DOMAIN "mlx.glimpse-go.site" \
    "mlx.hanwhafintech.com"
  upsert_env_if_missing_or_legacy NGINX_TEMPLATE_MODE "ssl" \
    "dev-ssl"
  upsert_env_if_missing_or_legacy HANWHA_SSL_CERTIFICATE "/etc/ssl/cloudflare/hanwhafintech.com/fullchain.pem"
  upsert_env_if_missing_or_legacy HANWHA_SSL_CERTIFICATE_KEY "/etc/ssl/cloudflare/hanwhafintech.com/privkey.pem"
  upsert_env_if_missing_or_legacy GLIMPSE_SSL_HOST_DIR "./certs/cloudflare" \
    "./certs/cloudflare"
  upsert_env_if_missing_or_legacy GLIMPSE_SSL_CERTIFICATE "/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem" \
    "/etc/ssl/cloudflare/hanwhafintech.com/fullchain.pem"
  upsert_env_if_missing_or_legacy GLIMPSE_SSL_CERTIFICATE_KEY "/etc/ssl/cloudflare/glimpse-go.site/privkey.pem" \
    "/etc/ssl/cloudflare/hanwhafintech.com/privkey.pem"

  upsert_env_if_missing_or_legacy TASK_DEV_UPSTREAM "http://$macstudio_lan_ip:3000" \
    "http://127.0.0.1:3000" \
    'http://${MACSTUDIO_LAN_IP}:3000'
  upsert_env_if_missing_or_legacy TASK_DEV_API_UPSTREAM "http://$macstudio_lan_ip:4000" \
    "http://127.0.0.1:4000" \
    'http://${MACSTUDIO_LAN_IP}:4000'
  upsert_env_if_missing_or_legacy TASK_PROD_UPSTREAM "http://$macstudio_lan_ip:3001" \
    "http://127.0.0.1:3001" \
    'http://${MACSTUDIO_LAN_IP}:3001'
  upsert_env_if_missing_or_legacy TASK_PROD_API_UPSTREAM "http://$macstudio_lan_ip:4001" \
    "http://127.0.0.1:4001" \
    'http://${MACSTUDIO_LAN_IP}:4001'
  upsert_env EMBED_UPSTREAM "${EMBED_UPSTREAM:-http://$macstudio_lan_ip:8089}"
  upsert_env RERANK_UPSTREAM "${RERANK_UPSTREAM:-http://$macstudio_lan_ip:8090}"
  upsert_env MLX_UPSTREAM "${MLX_UPSTREAM:-http://$macstudio_lan_ip:8088}"
}

validate_runtime_config() {
  config="$(compose config)"

  for key in \
    TASK_DEV_DOMAIN \
    TASK_DEV_API_DOMAIN \
    TASK_PROD_DOMAIN \
    TASK_PROD_API_DOMAIN \
    EMBED_DOMAIN \
    RERANK_DOMAIN \
    MLX_DOMAIN \
    HANWHA_SSL_CERTIFICATE \
    HANWHA_SSL_CERTIFICATE_KEY \
    GLIMPSE_SSL_CERTIFICATE \
    GLIMPSE_SSL_CERTIFICATE_KEY \
    TASK_DEV_UPSTREAM \
    TASK_DEV_API_UPSTREAM \
    TASK_PROD_UPSTREAM \
    TASK_PROD_API_UPSTREAM \
    EMBED_UPSTREAM \
    RERANK_UPSTREAM \
    MLX_UPSTREAM; do
    if ! printf '%s\n' "$config" | grep -q "$key:"; then
      echo "ERROR: docker-compose.yml does not pass $key to the nginx container." >&2
      echo "Sync deploy-runtime/dev-server/nginx-docker/docker-compose.yml to this runtime directory." >&2
      exit 1
    fi
  done
}

deploy_nginx() {
  image="$(normalize_image "${1:-${NGINX_IMAGE:-}}")"
  ensure_env
  sync_macstudio_upstreams

  upsert_env NGINX_IMAGE "$image"
  validate_runtime_config

  chmod +x scripts/certs.sh
  compose pull nginx
  compose up -d --no-build nginx
  nginx_test 20
}

cmd="${1:-deploy}"

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  deploy|up)
    deploy_nginx "${2:-}"
    ;;
  status|ps)
    compose ps
    ;;
  logs)
    compose logs -f --tail="${TAIL:-200}" nginx
    ;;
  test)
    nginx_test 1
    ;;
  reload)
    nginx_test 3
    docker exec glimpse-nginx nginx -s reload
    ;;
  restart)
    compose restart nginx
    nginx_test 20
    ;;
  stop)
    compose stop nginx
    ;;
  certs)
    shift
    chmod +x scripts/certs.sh
    exec ./scripts/certs.sh "$@"
    ;;
  *)
    echo "ERROR: unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
