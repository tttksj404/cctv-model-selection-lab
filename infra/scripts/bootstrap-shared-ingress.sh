#!/usr/bin/env bash
set -Eeuo pipefail

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
umask 077

runtime_root="${DEPLOY_RUNTIME_ROOT:-/var/lib/eyesonu-deploy/runtime}"
ingress_compose_file="${EYESONU_INGRESS_COMPOSE_FILE:-/etc/eyesonu/ingress/compose.yml}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "shared ingress bootstrap must run as root"
[[ -d "$runtime_root" && ! -L "$runtime_root" ]] \
    || fail "shared ingress runtime root is missing or unsafe: $runtime_root"
[[ -f "$ingress_compose_file" && ! -L "$ingress_compose_file" ]] \
    || fail "root-managed ingress Compose file is missing or unsafe: $ingress_compose_file"

for network in eyesonu-dev eyesonu-prod; do
    docker network inspect "$network" >/dev/null 2>&1 || docker network create "$network" >/dev/null
done

env -u COMPOSE_PROJECT_NAME DEPLOY_RUNTIME_ROOT="$runtime_root" \
    docker compose --project-name eyesonu-ingress -f "$ingress_compose_file" \
    up -d --wait --wait-timeout 180 nginx

container_id="$(docker compose --project-name eyesonu-ingress -f "$ingress_compose_file" ps -q nginx)"
[[ -n "$container_id" ]] || fail "root-managed shared Nginx did not create a container"
state="$(docker inspect --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container_id")"
[[ "$state" == "running|healthy" ]] || fail "root-managed shared Nginx is not healthy: $state"
docker exec "$container_id" nginx -t

echo "PASS: root-managed shared ingress is running and healthy"
