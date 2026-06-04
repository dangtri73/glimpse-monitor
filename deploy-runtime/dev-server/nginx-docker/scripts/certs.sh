#!/usr/bin/env sh
set -eu

usage() {
  cat <<'EOF'
Manage Docker Nginx certificates on the dev server.

Usage:
  ./scripts/certs.sh list
  ./scripts/certs.sh install <cloudflare|letsencrypt> <domain> <fullchain.pem> <privkey.pem>
  ./scripts/certs.sh sync-letsencrypt <domain> [live-dir]
  ./scripts/certs.sh check <cloudflare|letsencrypt> <domain>
  ./scripts/certs.sh remove <cloudflare|letsencrypt> <domain>
  ./scripts/certs.sh reload

Examples:
  ./scripts/certs.sh install cloudflare glimpse-go.site /tmp/fullchain.pem /tmp/privkey.pem
  ./scripts/certs.sh sync-letsencrypt dev.api.hftvn.com
  ./scripts/certs.sh check cloudflare glimpse-go.site
  ./scripts/certs.sh remove cloudflare old.example.com
  ./scripts/certs.sh reload

Notes:
  - Certs stay on the dev server under ./certs and are ignored by Git.
  - Existing certs are backed up before install/remove.
  - reload runs nginx -t before nginx -s reload.
EOF
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/certs/backups"

timestamp() {
  date -u +%Y%m%dT%H%M%SZ
}

store_dir() {
  store="$1"
  domain="$2"
  case "$store" in
    cloudflare)
      echo "$PROJECT_DIR/certs/cloudflare/$domain"
      ;;
    letsencrypt)
      echo "$PROJECT_DIR/certs/letsencrypt/live/$domain"
      ;;
    *)
      echo "ERROR: unknown cert store: $store" >&2
      echo "Use one of: cloudflare, letsencrypt" >&2
      exit 1
      ;;
  esac
}

copy_source() {
  src="$1"
  dst="$2"
  if [ -r "$src" ]; then
    cp -L "$src" "$dst"
  else
    sudo cp -L "$src" "$dst"
    sudo chown "$(id -u):$(id -g)" "$dst"
  fi
}

validate_pair() {
  cert="$1"
  key="$2"

  openssl x509 -noout -in "$cert" >/dev/null
  openssl pkey -noout -in "$key" >/dev/null

  cert_hash="$(openssl x509 -noout -pubkey -in "$cert" | openssl sha256)"
  key_hash="$(openssl pkey -pubout -in "$key" | openssl sha256)"

  if [ "$cert_hash" != "$key_hash" ]; then
    echo "ERROR: certificate and private key do not match" >&2
    exit 1
  fi
}

backup_domain() {
  store="$1"
  domain="$2"
  dest="$(store_dir "$store" "$domain")"

  if [ ! -e "$dest/fullchain.pem" ] && [ ! -e "$dest/privkey.pem" ]; then
    return 0
  fi

  backup="$BACKUP_DIR/$store/$domain/$(timestamp)"
  mkdir -p "$backup"

  [ -e "$dest/fullchain.pem" ] && cp -L "$dest/fullchain.pem" "$backup/fullchain.pem"
  [ -e "$dest/privkey.pem" ] && cp -L "$dest/privkey.pem" "$backup/privkey.pem"

  echo "Backup written: $backup"
}

install_cert() {
  store="$1"
  domain="$2"
  cert_src="$3"
  key_src="$4"
  dest="$(store_dir "$store" "$domain")"

  if [ ! -e "$cert_src" ]; then
    echo "ERROR: certificate file not found: $cert_src" >&2
    exit 1
  fi

  if [ ! -e "$key_src" ]; then
    echo "ERROR: private key file not found: $key_src" >&2
    exit 1
  fi

  mkdir -p "$dest"
  tmp_cert="$dest/fullchain.pem.tmp.$$"
  tmp_key="$dest/privkey.pem.tmp.$$"

  copy_source "$cert_src" "$tmp_cert"
  copy_source "$key_src" "$tmp_key"
  chmod 644 "$tmp_cert"
  chmod 600 "$tmp_key"

  validate_pair "$tmp_cert" "$tmp_key"
  backup_domain "$store" "$domain"

  mv "$tmp_cert" "$dest/fullchain.pem"
  mv "$tmp_key" "$dest/privkey.pem"

  echo "Installed $store certificate for $domain"
  openssl x509 -noout -subject -issuer -dates -in "$dest/fullchain.pem"
}

sync_letsencrypt() {
  domain="$1"
  live_dir="${2:-/etc/letsencrypt/live/$domain}"
  install_cert letsencrypt "$domain" "$live_dir/fullchain.pem" "$live_dir/privkey.pem"
}

check_cert() {
  store="$1"
  domain="$2"
  dest="$(store_dir "$store" "$domain")"
  cert="$dest/fullchain.pem"
  key="$dest/privkey.pem"

  if [ ! -e "$cert" ] || [ ! -e "$key" ]; then
    echo "ERROR: missing fullchain.pem or privkey.pem in $dest" >&2
    exit 1
  fi

  validate_pair "$cert" "$key"
  echo "OK: $store certificate for $domain"
  openssl x509 -noout -subject -issuer -dates -in "$cert"
}

remove_cert() {
  store="$1"
  domain="$2"
  dest="$(store_dir "$store" "$domain")"

  if [ ! -d "$dest" ]; then
    echo "Nothing to remove: $dest"
    return 0
  fi

  backup_domain "$store" "$domain"
  rm -f "$dest/fullchain.pem" "$dest/privkey.pem"
  rmdir "$dest" 2>/dev/null || true
  echo "Removed $store certificate for $domain"
}

list_certs() {
  for store in cloudflare letsencrypt; do
    case "$store" in
      cloudflare) base="$PROJECT_DIR/certs/cloudflare" ;;
      letsencrypt) base="$PROJECT_DIR/certs/letsencrypt/live" ;;
    esac

    [ -d "$base" ] || continue

    find "$base" -mindepth 1 -maxdepth 1 -type d | sort | while IFS= read -r dir; do
      domain="$(basename "$dir")"
      cert="$dir/fullchain.pem"
      key="$dir/privkey.pem"

      if [ -e "$cert" ] && [ -e "$key" ]; then
        enddate="$(openssl x509 -noout -enddate -in "$cert" 2>/dev/null | sed 's/^notAfter=//')"
        echo "$store $domain expires: ${enddate:-unknown}"
      else
        echo "$store $domain incomplete"
      fi
    done
  done
}

reload_nginx() {
  docker exec glimpse-nginx nginx -t
  docker exec glimpse-nginx nginx -s reload
}

cmd="${1:-}"

case "$cmd" in
  -h|--help|"")
    usage
    ;;
  list)
    list_certs
    ;;
  install)
    [ "$#" -eq 5 ] || { usage >&2; exit 1; }
    install_cert "$2" "$3" "$4" "$5"
    ;;
  sync-letsencrypt)
    [ "$#" -eq 2 ] || [ "$#" -eq 3 ] || { usage >&2; exit 1; }
    sync_letsencrypt "$2" "${3:-}"
    ;;
  check)
    [ "$#" -eq 3 ] || { usage >&2; exit 1; }
    check_cert "$2" "$3"
    ;;
  remove)
    [ "$#" -eq 3 ] || { usage >&2; exit 1; }
    remove_cert "$2" "$3"
    ;;
  reload)
    reload_nginx
    ;;
  *)
    echo "ERROR: unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
