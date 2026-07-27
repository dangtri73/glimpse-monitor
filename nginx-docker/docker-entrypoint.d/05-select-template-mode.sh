#!/bin/sh
set -eu

mode="${NGINX_TEMPLATE_MODE:-}"

if [ -z "$mode" ]; then
    case "${NGINX_TEMPLATE_DIR:-}" in
        *templates-http) mode="http" ;;
        *templates-ssl) mode="ssl" ;;
        *) mode="ssl" ;;
    esac
fi

case "$mode" in
    http)
        template_dir="/opt/glimpse-nginx/templates-http"
        ;;
    ssl)
        template_dir="/opt/glimpse-nginx/templates-ssl"
        ;;
    *)
        echo "Unsupported NGINX_TEMPLATE_MODE: $mode" >&2
        echo "Use one of: http, ssl" >&2
        exit 1
        ;;
esac

rm -rf /etc/nginx/templates
mkdir -p /etc/nginx/templates /etc/nginx/generated
cp "$template_dir"/*.template /etc/nginx/templates/
