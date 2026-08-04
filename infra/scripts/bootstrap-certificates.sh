#!/usr/bin/env sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "Usage: sh infra/scripts/bootstrap-certificates.sh PRIMARY_DOMAIN EMAIL [ADDITIONAL_DOMAIN ...]" >&2
  exit 1
fi

primary_domain="$1"
email="$2"
shift 2

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
runtime_root="${DEPLOY_RUNTIME_ROOT:-$repo_root/infra}"
cert_dir="$runtime_root/certbot/conf"
webroot_dir="$runtime_root/certbot/www"

mkdir -p "$cert_dir" "$webroot_dir"

domains="-d $primary_domain"
for domain in "$@"; do
  domains="$domains -d $domain"
done

echo "Requesting certificate for: $primary_domain $*"
echo "The EC2 host port 80 must be available, and DNS must point to this EC2 instance."

# shellcheck disable=SC2086
docker run --rm \
  -p 80:80 \
  -v "$cert_dir:/etc/letsencrypt" \
  certbot/certbot:latest certonly \
  --standalone \
  --preferred-challenges http \
  --cert-name "$primary_domain" \
  --email "$email" \
  --agree-tos \
  --no-eff-email \
  $domains
