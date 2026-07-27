FROM nginx:1.27-alpine

COPY docker-entrypoint.d/05-select-template-mode.sh /docker-entrypoint.d/05-select-template-mode.sh
COPY nginx/templates-http /opt/glimpse-nginx/templates-http
COPY nginx/templates-ssl /opt/glimpse-nginx/templates-ssl
COPY nginx/snippets /etc/nginx/snippets

RUN chmod +x /docker-entrypoint.d/05-select-template-mode.sh \
    && mkdir -p /etc/nginx/templates /etc/nginx/generated
