#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Deploy Glimpse Monitor runtime services on Mac Studio.

Usage:
  ./deploy.sh <stack|all|dashboard|ai-service|workers|agent>
  ./deploy.sh status
  ./deploy.sh agent-status
  ./deploy.sh logs [service|agent]
  ./deploy.sh restart <dashboard|ai-service|workers|agent>
  ./deploy.sh stop <dashboard|ai-service|workers|agent|all|stack>

Examples:
  ./deploy.sh stack
  IMAGE_TAG=abc1234 ./deploy.sh dashboard
  ./deploy.sh agent
  IMAGE_TAG=abc1234 ./deploy.sh all
  ./deploy.sh logs dashboard
  ./deploy.sh logs agent
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
    docker compose --env-file .env -f docker-compose.yml "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose --env-file .env -f docker-compose.yml "$@"
  else
    echo "ERROR: docker compose or docker-compose is required." >&2
    echo "PATH: $PATH" >&2
    exit 1
  fi
}

agent_label() {
  load_env
  echo "${GLIMPSE_AGENT_LAUNCHD_LABEL:-site.glimpse.monitor.agent}"
}

agent_dir() {
  load_env
  case "${GLIMPSE_AGENT_DIR:-$SCRIPT_DIR/agent}" in
    /*) echo "${GLIMPSE_AGENT_DIR:-$SCRIPT_DIR/agent}" ;;
    *) echo "$SCRIPT_DIR/${GLIMPSE_AGENT_DIR:-agent}" ;;
  esac
}

agent_log_dir() {
  load_env
  case "${GLIMPSE_AGENT_LOG_DIR:-$SCRIPT_DIR/logs/agent}" in
    /*) echo "${GLIMPSE_AGENT_LOG_DIR:-$SCRIPT_DIR/logs/agent}" ;;
    *) echo "$SCRIPT_DIR/${GLIMPSE_AGENT_LOG_DIR:-logs/agent}" ;;
  esac
}

agent_launch_target() {
  load_env
  if [ -n "${GLIMPSE_AGENT_LAUNCHD_DOMAIN:-}" ]; then
    echo "$GLIMPSE_AGENT_LAUNCHD_DOMAIN"
    return 0
  fi

  uid="$(id -u)"
  if launchctl print "gui/$uid" >/dev/null 2>&1; then
    echo "gui/$uid"
  else
    echo "user/$uid"
  fi
}

agent_source_exists() {
  [ -f "$(agent_dir)/server.py" ]
}

require_agent_source() {
  if ! agent_source_exists; then
    echo "ERROR: agent source is missing: $(agent_dir)/server.py" >&2
    echo "Deploy via scripts/deploy-macstudio.sh agent from a repo checkout so agent/ is copied into this runtime directory." >&2
    exit 1
  fi
}

agent_health_url() {
  load_env
  host="${GLIMPSE_AGENT_HOST:-127.0.0.1}"
  port="$(agent_port)"
  if [ "$host" = "0.0.0.0" ] || [ "$host" = "::" ]; then
    host="127.0.0.1"
  fi
  echo "http://$host:$port/health"
}

agent_port() {
  load_env
  echo "${GLIMPSE_AGENT_PORT:-8765}"
}

agent_bind_host() {
  load_env
  host="${GLIMPSE_AGENT_HOST:-127.0.0.1}"
  if [ "$host" = "::" ]; then
    echo "127.0.0.1"
  else
    echo "$host"
  fi
}

agent_launch_domains() {
  load_env
  uid="$(id -u)"
  if [ -n "${GLIMPSE_AGENT_LAUNCHD_DOMAIN:-}" ]; then
    echo "$GLIMPSE_AGENT_LAUNCHD_DOMAIN"
  fi
  echo "gui/$uid"
  echo "user/$uid"
}

generate_agent_plist() {
  load_env
  require_agent_source

  label="$(agent_label)"
  dir="$(agent_dir)"
  log_dir="$(agent_log_dir)"
  plist="$HOME/Library/LaunchAgents/$label.plist"
  python_bin="${AGENT_PYTHON:-/usr/bin/python3}"

  mkdir -p "$HOME/Library/LaunchAgents" "$log_dir"

  AGENT_LABEL="$label" \
    AGENT_DIR="$dir" \
    AGENT_LOG_DIR="$log_dir" \
    AGENT_PYTHON="$python_bin" \
    AGENT_PLIST="$plist" \
    "$python_bin" - <<'PY'
import os
import plistlib

label = os.environ["AGENT_LABEL"]
agent_dir = os.environ["AGENT_DIR"]
log_dir = os.environ["AGENT_LOG_DIR"]
python_bin = os.environ["AGENT_PYTHON"]
plist_path = os.environ["AGENT_PLIST"]

env_keys = [
    "PATH",
    "MACSTUDIO_LAN_IP",
    "GLIMPSE_AGENT_HOST",
    "GLIMPSE_AGENT_PORT",
    "GLIMPSE_AGENT_POLL_SECONDS",
    "GLIMPSE_AGENT_CORS_ORIGIN",
    "GLIMPSE_AGENT_LOG_REQUESTS",
    "GLIMPSE_AGENT_ENABLE_SERVICE_ACTIONS",
    "GLIMPSE_AGENT_ENABLE_NGINX_APPLY",
    "GLIMPSE_AGENT_ALLOW_UNVERIFIED_DOMAINS",
    "GLIMPSE_AGENT_ADMIN_TOKEN",
    "GLIMPSE_AGENT_CONFIG_PATH",
    "GLIMPSE_AGENT_DEVICE_ID",
]
env = {key: os.environ[key] for key in env_keys if os.environ.get(key)}
env.setdefault("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
env.setdefault("PYTHONUNBUFFERED", "1")

plist = {
    "Label": label,
    "ProgramArguments": [python_bin, "server.py"],
    "WorkingDirectory": agent_dir,
    "EnvironmentVariables": env,
    "RunAtLoad": True,
    "KeepAlive": True,
    "StandardOutPath": os.path.join(log_dir, "stdout.log"),
    "StandardErrorPath": os.path.join(log_dir, "stderr.log"),
}

with open(plist_path, "wb") as handle:
    plistlib.dump(plist, handle, sort_keys=True)
PY

  echo "$plist"
}

agent_tail_logs() {
  log_dir="$(agent_log_dir)"
  echo "--- agent stdout ---"
  if [ -f "$log_dir/stdout.log" ]; then
    tail -n 80 "$log_dir/stdout.log"
  else
    echo "No stdout log at $log_dir/stdout.log"
  fi

  echo "--- agent stderr ---"
  if [ -f "$log_dir/stderr.log" ]; then
    tail -n 80 "$log_dir/stderr.log"
  else
    echo "No stderr log at $log_dir/stderr.log"
  fi
}

agent_port_owners() {
  port="$(agent_port)"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
  else
    echo "lsof is not available; cannot inspect port $port" >&2
  fi
}

stop_agent_launchd_jobs() {
  label="$(agent_label)"
  for domain in $(agent_launch_domains | awk '!seen[$0]++'); do
    launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
  done
}

stop_replaceable_agent_port_owner() {
  load_env
  replace="${GLIMPSE_AGENT_REPLACE_PORT_OWNER:-true}"
  [ "$replace" = "true" ] || return 0

  port="$(agent_port)"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi

  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$pids" ] || return 0

  for pid in $pids; do
    command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    case "$command" in
      *python*server.py*|*Python*server.py*)
        echo "Stopping existing Python agent process on port $port: pid=$pid command=$command"
        kill "$pid" >/dev/null 2>&1 || true
        ;;
      *)
        echo "Port $port is owned by an unknown process; not stopping it automatically." >&2
        echo "pid=$pid command=$command" >&2
        return 1
        ;;
    esac
  done

  sleep 2
}

require_agent_port_available() {
  port="$(agent_port)"
  owners="$(agent_port_owners)"
  if [ -n "$owners" ]; then
    echo "ERROR: agent port $port is still in use." >&2
    echo "$owners" >&2
    echo "Stop the process above or set GLIMPSE_AGENT_PORT to a free port, then rerun deploy." >&2
    return 1
  fi
}

agent_port_bindable() {
  host="$(agent_bind_host)"
  port="$(agent_port)"
  "$AGENT_PYTHON" - "$host" "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((host, port))
PY
}

find_free_agent_port() {
  host="$(agent_bind_host)"
  start="$(agent_port)"
  "$AGENT_PYTHON" - "$host" "$start" <<'PY'
import socket
import sys

host = sys.argv[1]
start = int(sys.argv[2])
for port in range(start + 1, start + 101):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
    except OSError:
        continue
    print(port)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

prepare_agent_port() {
  load_env
  AGENT_PYTHON="${AGENT_PYTHON:-/usr/bin/python3}"
  export AGENT_PYTHON

  stop_agent_launchd_jobs
  stop_replaceable_agent_port_owner || true

  if agent_port_bindable; then
    return 0
  fi

  port="$(agent_port)"
  echo "Agent port $port is not bindable after stopping known Glimpse jobs." >&2
  echo "--- port owners ---" >&2
  agent_port_owners >&2

  if [ "${GLIMPSE_AGENT_AUTO_PORT_FALLBACK:-true}" != "true" ]; then
    echo "ERROR: set GLIMPSE_AGENT_AUTO_PORT_FALLBACK=true or free port $port." >&2
    return 1
  fi

  new_port="$(find_free_agent_port)" || {
    echo "ERROR: no free agent port found near $port." >&2
    return 1
  }

  echo "Using fallback agent port: $new_port"
  upsert_env GLIMPSE_AGENT_PORT "$new_port"
  upsert_env MONITOR_AGENT_URL "http://host.docker.internal:$new_port"
  AGENT_PORT_CHANGED=true
}

restart_dashboard_for_agent_url() {
  echo "Recreating dashboard so it uses current MONITOR_AGENT_URL..."

  container_id="$(compose ps -q dashboard 2>/dev/null || true)"
  if [ -z "$container_id" ]; then
    echo "Dashboard container is not present; skipping dashboard restart."
    return 0
  fi

  dashboard_image="$(docker inspect -f '{{.Config.Image}}' "$container_id" 2>/dev/null || true)"
  if [ -n "$dashboard_image" ]; then
    upsert_env DASHBOARD_IMAGE "$dashboard_image"
  fi

  compose up -d --no-build --no-deps --force-recreate dashboard
}

wait_for_agent_health() {
  url="$(agent_health_url)"
  attempts="${1:-30}"
  i=1

  while [ "$i" -le "$attempts" ]; do
    if curl -fsS --max-time 2 "$url" >/dev/null; then
      echo "Agent is healthy: $url"
      return 0
    fi
    echo "Waiting for agent health at $url ($i/$attempts)..." >&2
    sleep 1
    i=$((i + 1))
  done

  echo "ERROR: agent did not become healthy: $url" >&2
  echo "--- launchd status ---" >&2
  launchctl print "$(agent_launch_target)/$(agent_label)" >&2 || true
  echo "--- verbose health check ---" >&2
  curl -v --max-time 3 "$url" >&2 || true
  echo "--- port owners ---" >&2
  agent_port_owners >&2
  agent_tail_logs >&2
  return 1
}

deploy_agent() {
  AGENT_PORT_CHANGED=false
  prepare_agent_port

  plist="$(generate_agent_plist)"
  label="$(agent_label)"
  target="$(agent_launch_target)"

  echo "Agent launchd target: $target"
  echo "Agent launchd label:  $label"
  echo "Agent source dir:     $(agent_dir)"
  echo "Agent log dir:        $(agent_log_dir)"
  echo "Agent plist:          $plist"

  launchctl bootstrap "$target" "$plist"
  launchctl kickstart -k "$target/$label"

  wait_for_agent_health 30

  restart_dashboard_for_agent_url
}

deploy_agent_if_present() {
  if agent_source_exists; then
    deploy_agent
  else
    echo "Skipping agent deploy because $(agent_dir)/server.py is not present."
  fi
}

agent_status() {
  label="$(agent_label)"
  target="$(agent_launch_target)"
  launchctl print "$target/$label" || true
  echo
  curl -fsS "$(agent_health_url)" || true
  echo
}

agent_logs() {
  log_dir="$(agent_log_dir)"
  mkdir -p "$log_dir"
  touch "$log_dir/stdout.log" "$log_dir/stderr.log"
  tail -f "$log_dir/stdout.log" "$log_dir/stderr.log"
}

stop_agent() {
  stop_agent_launchd_jobs
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
  target="${1:-all}"
  load_env

  namespace="${DOCKERHUB_NAMESPACE:-dangtri73}"
  prefix="${IMAGE_PREFIX:-glimpse-monitor}"
  tag="${IMAGE_TAG:-latest}"

  upsert_env DOCKERHUB_NAMESPACE "$namespace"
  upsert_env IMAGE_PREFIX "$prefix"
  upsert_env IMAGE_TAG "$tag"

  case "$target" in
    dashboard)
      upsert_env DASHBOARD_IMAGE "$namespace/$prefix-dashboard:$tag"
      ;;
    ai-service)
      upsert_env AI_SERVICE_IMAGE "$namespace/$prefix-ai-service:$tag"
      ;;
    workers)
      upsert_env WORKERS_IMAGE "$namespace/$prefix-workers:$tag"
      ;;
    all|stack)
      upsert_env DASHBOARD_IMAGE "$namespace/$prefix-dashboard:$tag"
      upsert_env AI_SERVICE_IMAGE "$namespace/$prefix-ai-service:$tag"
      upsert_env WORKERS_IMAGE "$namespace/$prefix-workers:$tag"
      ;;
  esac
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

  if [ "$target" = "agent" ]; then
    echo "Deploy target: $target"
    echo "Runtime dir:    $SCRIPT_DIR"
    echo "Env file:       $SCRIPT_DIR/.env"
    deploy_agent
    return 0
  fi

  services="$(services_for_target "$target")" || {
    echo "ERROR: unknown deploy target: $target" >&2
    usage >&2
    exit 1
  }

  sync_image_env "$target"

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
    if [ "$target" = "dashboard" ]; then
      compose up -d --no-build --no-deps dashboard
    else
      # shellcheck disable=SC2086
      compose up -d --no-build $services
    fi
  fi

  if [ "$target" = "all" ] || [ "$target" = "stack" ]; then
    deploy_agent_if_present
  fi

  compose ps
}

cmd="${1:-all}"

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  stack|all|dashboard|ai-service|workers|agent)
    deploy_target "$cmd"
    ;;
  status|ps)
    compose ps
    echo
    agent_status
    ;;
  agent-status)
    agent_status
    ;;
  logs)
    if [ "${2:-}" = "agent" ]; then
      agent_logs
    elif [ -n "${2:-}" ]; then
      compose logs -f --tail="${TAIL:-200}" "$2"
    else
      compose logs -f --tail="${TAIL:-200}"
    fi
    ;;
  restart)
    target="${2:-}"
    [ -n "$target" ] || { usage >&2; exit 1; }
    if [ "$target" = "agent" ]; then
      deploy_agent
    else
      services="$(services_for_target "$target")" || { usage >&2; exit 1; }
      # shellcheck disable=SC2086
      compose restart $services
    fi
    ;;
  stop)
    target="${2:-all}"
    if [ "$target" = "agent" ]; then
      stop_agent
    else
      services="$(services_for_target "$target")" || { usage >&2; exit 1; }
      if [ "$target" = "stack" ]; then
        compose stop
      else
        # shellcheck disable=SC2086
        compose stop $services
      fi
    fi
    ;;
  *)
    echo "ERROR: unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
