#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Deploy the Glimpse Nginx gateway runtime.

Usage:
  ./deploy.sh deploy [image]
  ./deploy.sh status
  ./deploy.sh logs
  ./deploy.sh test
  ./deploy.sh reload
  ./deploy.sh restart
  ./deploy.sh stop
  ./deploy.sh certs <certs.sh args...>

Examples:
  ./deploy.sh deploy dangtri73/glimpse-nginx:latest
  NGINX_IMAGE=dangtri73/glimpse-nginx:abc1234 ./deploy.sh deploy
  ./deploy.sh certs list
  ./deploy.sh certs check cloudflare glimpse-go.site
EOF
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

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

deploy_nginx() {
  image="${1:-${NGINX_IMAGE:-}}"
  ensure_env

  if [ -n "$image" ]; then
    upsert_env NGINX_IMAGE "$image"
  fi

  chmod +x scripts/certs.sh
  compose pull nginx
  compose up -d --no-build nginx
  docker exec glimpse-nginx nginx -t
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
    docker exec glimpse-nginx nginx -t
    ;;
  reload)
    docker exec glimpse-nginx nginx -t
    docker exec glimpse-nginx nginx -s reload
    ;;
  restart)
    compose restart nginx
    docker exec glimpse-nginx nginx -t
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
