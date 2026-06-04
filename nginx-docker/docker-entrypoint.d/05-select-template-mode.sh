#!/bin/sh
set -eu

mode="${NGINX_TEMPLATE_MODE:-}"

if [ -z "$mode" ]; then
    case "${NGINX_TEMPLATE_DIR:-}" in
        *templates-http) mode="http" ;;
        *templates-dev-ssl) mode="dev-ssl" ;;
        *templates-ssl) mode="ssl" ;;
        *) mode="dev-ssl" ;;
    esac
fi

case "$mode" in
    http)
        template_dir="/opt/glimpse-nginx/templates-http"
        ;;
    dev-ssl)
        template_dir="/opt/glimpse-nginx/templates-dev-ssl"
        ;;
    ssl)
        template_dir="/opt/glimpse-nginx/templates-ssl"
        ;;
    *)
        echo "Unsupported NGINX_TEMPLATE_MODE: $mode" >&2
        echo "Use one of: http, dev-ssl, ssl" >&2
        exit 1
        ;;
esac

rm -rf /etc/nginx/templates
mkdir -p /etc/nginx/templates /etc/nginx/generated
cp "$template_dir"/*.template /etc/nginx/templates/
