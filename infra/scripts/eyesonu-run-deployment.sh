#!/usr/bin/env bash
set -Eeuo pipefail

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
umask 077

expected_commit="${1:-}"
profile="${2:-}"
checkout_root="/home/ubuntu/jenkins-data/workspace/ssafy-a204-infra"
deploy_env_file="/etc/eyesonu/deploy.env"
deploy_user="eyesonu-deploy"
release_base="/var/lib/eyesonu-deploy"
trusted_git="/usr/bin/git"
runner=""

cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n "$runner" && -f "$runner" && ! -L "$runner" ]]; then
        rm -f -- "$runner"
    fi
    exit "$status"
}
trap cleanup EXIT

[[ "$(id -u)" -eq 0 ]] || {
    echo "ERROR: deployment broker must run as root." >&2
    exit 1
}
case "$profile" in
    dev|master) ;;
    *)
        echo "ERROR: deployment broker received an unsupported profile." >&2
        exit 2
        ;;
esac
[[ "$expected_commit" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || {
    echo "ERROR: deployment broker received an invalid commit ID." >&2
    exit 2
}
[[ -x "$trusted_git" && -d "$checkout_root" && ! -L "$checkout_root" ]] || {
    echo "ERROR: deployment broker checkout boundary is unavailable or unsafe." >&2
    exit 1
}
[[ -d "$checkout_root/.git" && ! -L "$checkout_root/.git" ]] || {
    echo "ERROR: deployment broker checkout is not a real Git checkout." >&2
    exit 1
}
checkout_owner="$(/usr/bin/stat -c '%U' "$checkout_root")"
checkout_permissions="$(/usr/bin/stat -c '%a' "$checkout_root")"
[[ "$checkout_owner" != "$deploy_user" && $((8#$checkout_permissions & 8#022)) -eq 0 ]] || {
    echo "ERROR: deployment broker checkout must not be writable by the deployment account or its groups." >&2
    exit 1
}
[[ -f "$deploy_env_file" && ! -L "$deploy_env_file" ]] || {
    echo "ERROR: deployment broker environment file is unavailable or unsafe." >&2
    exit 1
}
[[ "$(/usr/bin/stat -c '%U|%G|%a' "$deploy_env_file")" == "root|root|600" ]] || {
    echo "ERROR: deployment broker environment file must be root-owned with mode 0600." >&2
    exit 1
}
[[ -d "$release_base" && ! -L "$release_base" ]] || {
    echo "ERROR: deployment broker release base is unavailable or unsafe." >&2
    exit 1
}

canonical_ref="refs/remotes/origin/$profile"
canonical_commit="$(env -i \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/nonexistent \
    XDG_CONFIG_HOME=/nonexistent \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_COUNT=0 \
    GIT_ATTR_NOSYSTEM=1 \
    GIT_NO_REPLACE_OBJECTS=1 \
    "$trusted_git" --no-replace-objects \
    -c core.hooksPath=/dev/null \
    -c core.fsmonitor=false \
    -C "$checkout_root" rev-parse --verify "${canonical_ref}^{commit}")" || {
        echo "ERROR: deployment broker could not resolve the protected canonical ref." >&2
        exit 1
    }
[[ "$canonical_commit" == "$expected_commit" ]] || {
    echo "ERROR: deployment broker refuses a commit that is not the current protected $profile ref." >&2
    exit 1
}

runner="$(mktemp "$release_base/.root-runner.${profile}.XXXXXX")"
env -i \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/nonexistent \
    XDG_CONFIG_HOME=/nonexistent \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_COUNT=0 \
    GIT_ATTR_NOSYSTEM=1 \
    GIT_NO_REPLACE_OBJECTS=1 \
    "$trusted_git" --no-replace-objects \
    -c core.hooksPath=/dev/null \
    -c core.fsmonitor=false \
    -C "$checkout_root" show "$expected_commit:infra/scripts/run-verified-deployment.sh" > "$runner"
[[ -s "$runner" && ! -L "$runner" ]] || {
    echo "ERROR: deployment broker extracted an empty or unsafe trusted runner." >&2
    exit 1
}
chmod 0700 "$runner"

/usr/bin/env -i \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/root \
    LC_ALL=C \
    /bin/bash --noprofile --norc "$runner" \
    "$expected_commit" "$checkout_root" "$deploy_env_file" "$profile" "$deploy_user"
