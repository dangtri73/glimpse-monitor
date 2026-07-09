# Nginx Certificate Management

Certificates are runtime state on the dev server. Do not put real certificates or private keys in Git, Docker images, or GitHub Actions secrets.

The Docker Nginx container mounts these host directories:

```txt
nginx-docker/certs/letsencrypt  -> /etc/letsencrypt
nginx-docker/certs/cloudflare   -> /etc/ssl/cloudflare
```

The expected file layout is:

```txt
nginx-docker/certs/
  letsencrypt/live/dev.api.hftvn.com/fullchain.pem
  letsencrypt/live/dev.api.hftvn.com/privkey.pem
  cloudflare/glimpse-go.site/fullchain.pem
  cloudflare/glimpse-go.site/privkey.pem
```

CI/CD pulls and restarts `dangtri73/glimpse-nginx:latest` without touching certs. The cert files remain on the dev server.

## Dev Server Runtime Directory

If the dev server still runs the old standalone directory:

```txt
/Users/tri/nginx-docker
```

you can keep using it as the runtime directory. In GitHub Actions, set:

```txt
DEV_NGINX_DOCKER_DIR=/Users/tri/nginx-docker
```

The Nginx GitHub Actions workflow copies `scripts/certs.sh` into this directory during deploy. To install it manually before the first deploy, run this from Mac Studio:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/nginx-docker
ssh -i ~/.ssh/id_ed25519_github_nginx_dev tri@192.168.1.113 "mkdir -p /Users/tri/nginx-docker/scripts"
scp -i ~/.ssh/id_ed25519_github_nginx_dev scripts/certs.sh tri@192.168.1.113:/Users/tri/nginx-docker/scripts/certs.sh
ssh -i ~/.ssh/id_ed25519_github_nginx_dev tri@192.168.1.113 "chmod +x /Users/tri/nginx-docker/scripts/certs.sh"
```

If you want the dev server to use the monorepo checkout instead, migrate certs:

```bash
mkdir -p /Users/tri/glimpse-monitor/nginx-docker/certs
rsync -a /Users/tri/nginx-docker/certs/ /Users/tri/glimpse-monitor/nginx-docker/certs/
```

Then set:

```txt
DEV_NGINX_DOCKER_DIR=/Users/tri/glimpse-monitor/nginx-docker
```

Choose one runtime directory and keep it stable. Do not let CI/CD point at one directory while certificates are stored in another.

## Manager Script

Run from the dev server:

```bash
cd /Users/tri/nginx-docker
./scripts/certs.sh --help
```

List installed certs:

```bash
./scripts/certs.sh list
```

Validate an installed cert/key pair:

```bash
./scripts/certs.sh check letsencrypt dev.api.hftvn.com
./scripts/certs.sh check cloudflare glimpse-go.site
```

Reload Nginx after certificate changes:

```bash
./scripts/certs.sh reload
```

`reload` runs `nginx -t` first and only then sends `nginx -s reload`.

## Add Or Update Cloudflare Origin Certificate

Create or renew the Cloudflare Origin Certificate in Cloudflare for:

```txt
glimpse-go.site
*.glimpse-go.site
```

Save the new cert and key temporarily on the dev server, for example:

```txt
/tmp/glimpse-go.site.fullchain.pem
/tmp/glimpse-go.site.privkey.pem
```

Install or update:

```bash
cd /Users/tri/nginx-docker
./scripts/certs.sh install cloudflare glimpse-go.site \
  /tmp/glimpse-go.site.fullchain.pem \
  /tmp/glimpse-go.site.privkey.pem
./scripts/certs.sh check cloudflare glimpse-go.site
./scripts/certs.sh reload
```

The script validates that the certificate and private key match. If a cert already exists, it is backed up under:

```txt
nginx-docker/certs/backups/cloudflare/glimpse-go.site/<timestamp>/
```

## Add Or Update Let's Encrypt Certificate Copy

If the host already has a Let's Encrypt certificate under `/etc/letsencrypt/live/<domain>`, copy it into the Docker-readable cert store:

```bash
cd /Users/tri/nginx-docker
./scripts/certs.sh sync-letsencrypt dev.api.hftvn.com
./scripts/certs.sh check letsencrypt dev.api.hftvn.com
./scripts/certs.sh reload
```

If source files require elevated read permission, the script will use `sudo cp`.

## Remove A Certificate

Remove only after the Nginx config no longer references that certificate path.

```bash
cd /Users/tri/nginx-docker
./scripts/certs.sh remove cloudflare old.example.com
./scripts/certs.sh reload
```

Removal backs up existing files first:

```txt
nginx-docker/certs/backups/<store>/<domain>/<timestamp>/
```

## Environment Mapping

Current `.env` values:

```env
DEV_SSL_HOST_DIR=./certs/letsencrypt
DEV_SSL_CERTIFICATE=/etc/letsencrypt/live/dev.api.hftvn.com/fullchain.pem
DEV_SSL_CERTIFICATE_KEY=/etc/letsencrypt/live/dev.api.hftvn.com/privkey.pem

GLIMPSE_SSL_HOST_DIR=./certs/cloudflare
GLIMPSE_SSL_CERTIFICATE=/etc/ssl/cloudflare/glimpse-go.site/fullchain.pem
GLIMPSE_SSL_CERTIFICATE_KEY=/etc/ssl/cloudflare/glimpse-go.site/privkey.pem
```

If you move a certificate to a different domain directory, update `.env`, recreate the container, and test:

```bash
docker compose up -d --no-build nginx
docker exec glimpse-nginx nginx -t
```
