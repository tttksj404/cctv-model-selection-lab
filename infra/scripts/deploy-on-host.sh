#!/usr/bin/env bash
set -Eeuo pipefail

profile="${1:-}"
deploy_root="${DEPLOY_ROOT:-/home/ubuntu/jenkins-data/workspace/ssafy-a204-infra}"
deploy_env_file="${DEPLOY_ENV_FILE:-/etc/eyesonu/deploy.env}"
runtime_root="${DEPLOY_RUNTIME_ROOT:-$deploy_root/infra}"
compose_file="${DEPLOY_COMPOSE:-$deploy_root/infra/compose.deploy.yml}"
rollback_root="${DEPLOY_PREVIOUS_RELEASE:-}"
rollback_compose_file=""
rollback_only="${DEPLOY_ROLLBACK_ONLY:-}"
stop_only="${DEPLOY_STOP_ONLY:-}"
compose_profile_unsets=()
inactive_profile_overrides=()
test_local_fixture="${EYESONU_DEPLOY_TEST_LOCAL_FIXTURE:-}"

case "$profile" in
    dev|master) ;;
    *)
        echo "Usage: $0 {dev|master}" >&2
        exit 2
        ;;
esac

case "$test_local_fixture" in
    ''|1) ;;
    *)
        echo "ERROR: EYESONU_DEPLOY_TEST_LOCAL_FIXTURE must be empty or 1." >&2
        exit 1
        ;;
esac

case "$rollback_only" in
    ''|1) ;;
    *)
        echo "ERROR: DEPLOY_ROLLBACK_ONLY must be empty or 1." >&2
        exit 1
        ;;
esac

case "$stop_only" in
    ''|1) ;;
    *)
        echo "ERROR: DEPLOY_STOP_ONLY must be empty or 1." >&2
        exit 1
        ;;
esac

[[ "$rollback_only" != 1 || "$stop_only" != 1 ]] || {
    echo "ERROR: rollback-only and stop-only deployment modes are mutually exclusive." >&2
    exit 1
}

compose() {
    env -u COMPOSE_PROJECT_NAME "${compose_profile_unsets[@]}" "DEPLOY_RUNTIME_ROOT=$runtime_root" "${inactive_profile_overrides[@]}" docker compose \
        --env-file "$deploy_env_file" \
        -f "$compose_file" \
        "$@"
}

docker_engine() {
    env -u COMPOSE_PROJECT_NAME "DEPLOY_RUNTIME_ROOT=$runtime_root" docker "$@"
}

require_file() {
    local path="$1"

    if [[ ! -f "$path" ]]; then
        echo "ERROR: required file is missing: $path" >&2
        exit 1
    fi
}

require_secure_deploy_env_file() {
    local path="$1"
    local owner
    local group
    local permissions

    require_file "$path"
    [[ ! -L "$path" ]] || {
        echo "ERROR: deployment env file must not be a symlink: $path" >&2
        exit 1
    }

    # The repository regression harness uses temporary files. A real SSH
    # invocation begins with env -i and therefore cannot inherit this opt-in.
    [[ "$test_local_fixture" == 1 ]] && return

    owner="$(stat -c '%U' "$path")"
    group="$(stat -c '%G' "$path")"
    permissions="$(stat -c '%a' "$path")"
    [[ "$owner" == root && "$group" == eyesonu-deploy && "$permissions" == 640 ]] || {
        echo "ERROR: deployment env file must be root:eyesonu-deploy with mode 0640: $path" >&2
        exit 1
    }
}

require_directory() {
    local path="$1"

    if [[ ! -d "$path" || -L "$path" ]]; then
        echo "ERROR: required directory is missing or unsafe: $path" >&2
        exit 1
    fi
}

validate_runtime_root() {
    local nginx_config="$runtime_root/nginx/conf.d/default.conf"
    local nginx_ssl_parameters="$runtime_root/nginx/snippets/ssl-params.conf"

    require_directory "$runtime_root"
    runtime_root="$(cd "$runtime_root" && pwd -P)"
    nginx_config="$runtime_root/nginx/conf.d/default.conf"
    nginx_ssl_parameters="$runtime_root/nginx/snippets/ssl-params.conf"
    require_directory "$runtime_root/certbot/www"
    require_directory "$runtime_root/certbot/conf"
    require_directory "$runtime_root/nginx/conf.d"
    require_directory "$runtime_root/nginx/snippets"
    [[ -f "$nginx_config" && ! -L "$nginx_config" ]] || {
        echo "ERROR: shared Nginx configuration is missing or unsafe: $nginx_config" >&2
        exit 1
    }
    [[ -f "$nginx_ssl_parameters" && ! -L "$nginx_ssl_parameters" ]] || {
        echo "ERROR: shared Nginx SSL parameters are missing or unsafe: $nginx_ssl_parameters" >&2
        exit 1
    }
}

prepare_compose_environment() {
    local inactive_prefix
    local variable_name

    case "$profile" in
        dev) inactive_prefix="MASTER_" ;;
        master) inactive_prefix="DEV_" ;;
    esac

    # Docker Compose gives values inherited from this shell precedence over
    # --env-file. Clear every deployment-profile variable first so the active
    # profile is sourced exclusively from the protected deploy env file.
    while IFS= read -r variable_name; do
        [[ -z "$variable_name" ]] && continue
        compose_profile_unsets+=("-u" "$variable_name")
    done < <(
        grep -oE '\$\{(DEV|MASTER)_[A-Z0-9_]+' "$compose_file" \
            | sed -E 's/^[$][{]//' \
            | sort -u
    )

    # Compose interpolates every service before profile selection. Supply
    # inert values only for required variables belonging to the inactive
    # profile; they are scoped to this Compose process and never persisted.
    while IFS= read -r variable_name; do
        [[ -z "$variable_name" ]] && continue
        inactive_profile_overrides+=("$variable_name=__inactive_profile_placeholder__")
    done < <(
        grep -oE "\\$\\{${inactive_prefix}[A-Z0-9_]+:\\?" "$compose_file" \
            | sed -E 's/^[$][{]//; s/:[?]$//' \
            | sort -u
    )
}

validate_rollback_release() {
    local release_parent
    local rollback_parent

    [[ -n "$rollback_root" ]] || return 0
    [[ -d "$rollback_root" && ! -L "$rollback_root" ]] || {
        echo "ERROR: rollback release directory is unavailable or unsafe." >&2
        exit 1
    }
    release_parent="$(cd "$deploy_root/.." && pwd -P)"
    rollback_parent="$(cd "$rollback_root/.." && pwd -P)"
    rollback_root="$(cd "$rollback_root" && pwd -P)"
    [[ "$rollback_parent" == "$release_parent" && "${rollback_root##*/}" == release-* && "$rollback_root" != "$deploy_root" ]] || {
        echo "ERROR: rollback release must be a sibling verified release." >&2
        exit 1
    }
    rollback_compose_file="$rollback_root/infra/compose.deploy.yml"
    [[ -f "$rollback_compose_file" && ! -L "$rollback_compose_file" ]] || {
        echo "ERROR: rollback release is missing a real Compose file." >&2
        exit 1
    }
}

ensure_shared_nginx() {
    local nginx_container_id
    local nginx_state

    if ! compose ps --status running --services | grep -Fxq nginx; then
        compose up -d --no-deps --wait --wait-timeout 180 nginx || exit $?
    fi
    nginx_container_id="$(compose ps -q nginx)" || exit $?
    [[ -n "$nginx_container_id" ]] || {
        echo "ERROR: shared Nginx has no Compose-managed container ID." >&2
        exit 1
    }
    nginx_state="$(docker_engine inspect --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$nginx_container_id")" || {
        echo "ERROR: could not inspect the shared Nginx container state." >&2
        exit 1
    }
    [[ "$nginx_state" == "running|healthy" ]] || {
        echo "ERROR: shared Nginx must be running and healthy, got: $nginx_state" >&2
        exit 1
    }
    verify_shared_nginx_mount "$nginx_container_id" "/etc/nginx/conf.d" "$runtime_root/nginx/conf.d"
    verify_shared_nginx_mount "$nginx_container_id" "/etc/nginx/snippets" "$runtime_root/nginx/snippets"
    verify_shared_nginx_mount "$nginx_container_id" "/var/www/certbot" "$runtime_root/certbot/www"
    verify_shared_nginx_mount "$nginx_container_id" "/etc/letsencrypt" "$runtime_root/certbot/conf"
    compose exec -T nginx nginx -t || exit $?
}

verify_shared_nginx_mount() {
    local nginx_container_id="$1"
    local destination="$2"
    local expected_source="$3"
    local format
    local actual_source

    format="{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Source}}{{end}}{{end}}"
    actual_source="$(docker_engine inspect --format "$format" "$nginx_container_id")" || {
        echo "ERROR: could not inspect shared Nginx mount: $destination" >&2
        exit 1
    }
    [[ "$actual_source" == "$expected_source" ]] || {
        echo "ERROR: shared Nginx mount mismatch for $destination; expected $expected_source, got ${actual_source:-<missing>}." >&2
        exit 1
    }
}

run_release() {
    local target_root="$1"
    local target_compose_file="$2"
    local remove_legacy_containers="$3"

    (
        compose_file="$target_compose_file"
        compose_profile_unsets=()
        inactive_profile_overrides=()
        require_file "$compose_file"
        [[ ! -L "$compose_file" ]] || {
            echo "ERROR: Compose file must not be a symlink: $compose_file" >&2
            exit 1
        }
        prepare_compose_environment
        compose config >/dev/null || exit $?

        cd "$target_root" || exit $?
        if [[ "$remove_legacy_containers" == 1 ]]; then
            sh infra/scripts/cleanup-legacy-containers.sh || exit $?
        fi
        compose --profile "$profile" up -d --build --wait --wait-timeout 180 \
            "backend-$profile" "admin-$profile" "reporter-$profile" || exit $?
        ensure_shared_nginx
        compose ps || exit $?
    )
}

stop_release() {
    local target_root="$1"
    local target_compose_file="$2"
    local profile_service_list
    local service_name
    local -a profile_services=()

    (
        compose_file="$target_compose_file"
        compose_profile_unsets=()
        inactive_profile_overrides=()
        require_file "$compose_file"
        [[ ! -L "$compose_file" ]] || {
            echo "ERROR: Compose file must not be a symlink: $compose_file" >&2
            exit 1
        }
        prepare_compose_environment
        compose config >/dev/null || exit $?
        profile_service_list="$(compose --profile "$profile" config --services)" || exit $?
        while IFS= read -r service_name; do
            [[ -z "$service_name" || "$service_name" == nginx ]] && continue
            profile_services+=("$service_name")
        done <<< "$profile_service_list"
        ((${#profile_services[@]} > 0)) || {
            echo "ERROR: stop-only deployment could not identify profile services." >&2
            exit 1
        }

        cd "$target_root" || exit $?
        compose --profile "$profile" stop \
            "${profile_services[@]}" || exit $?
        compose ps || exit $?
    )
}

require_secure_deploy_env_file "$deploy_env_file"
require_file "$compose_file"
[[ ! -L "$compose_file" ]] || {
    echo "ERROR: Compose file must not be a symlink: $compose_file" >&2
    exit 1
}
validate_runtime_root
validate_rollback_release

if [[ "$stop_only" == 1 ]]; then
    [[ -z "$rollback_root" ]] || {
        echo "ERROR: stop-only deployment must not receive a rollback release." >&2
        exit 1
    }
    if stop_release "$deploy_root" "$compose_file"; then
        echo "WARN: stop-only deployment completed; the unmarked release remains inactive." >&2
        exit 0
    fi
    echo "ERROR: stop-only deployment failed; operator intervention is required." >&2
    exit 1
fi

if [[ "$rollback_only" == 1 ]]; then
    [[ -n "$rollback_root" ]] || {
        echo "ERROR: rollback-only deployment requires a previously active verified release." >&2
        exit 1
    }
    candidate_cleanup_succeeded=true
    if ! stop_release "$deploy_root" "$compose_file"; then
        echo "ERROR: rollback-only deployment could not fully stop the failed candidate profile." >&2
        candidate_cleanup_succeeded=false
    fi
    if run_release "$rollback_root" "$rollback_compose_file" 0; then
        if [[ "$candidate_cleanup_succeeded" != true ]]; then
            echo "ERROR: previous release restarted, but failed candidate cleanup requires operator intervention." >&2
            exit 1
        fi
        echo "WARN: rollback-only deployment completed; active marker was left unchanged." >&2
        exit 0
    fi
    echo "ERROR: rollback-only deployment failed; operator intervention is required." >&2
    exit 1
fi

if ! run_release "$deploy_root" "$compose_file" 1; then
    echo "ERROR: verified release deployment failed." >&2
    exit 1
fi
