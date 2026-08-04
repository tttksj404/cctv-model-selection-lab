#!/usr/bin/env bash
set -Eeuo pipefail

expected_commit="${1:-}"
checkout_root="${2:-}"
deploy_env_file="${3:-}"
profile="${4:-}"
deploy_user="${5:-}"

if [[ -z "$expected_commit" || -z "$checkout_root" || -z "$deploy_env_file" ]]; then
    echo "Usage: $0 <expected-commit> <checkout-root> <deploy-env-file> {dev|master} [deploy-user]" >&2
    exit 2
fi

case "$profile" in
    dev|master) ;;
    *)
        echo "Usage: $0 <expected-commit> <checkout-root> <deploy-env-file> {dev|master} [deploy-user]" >&2
        exit 2
        ;;
esac

if [[ ! "$expected_commit" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]]; then
    echo "ERROR: expected deployment commit must be a full lowercase object ID." >&2
    exit 1
fi

checkout_root="$(cd "$checkout_root" && pwd -P)" || {
    echo "ERROR: deployment host checkout directory is unavailable." >&2
    exit 1
}

# The deployment host is Ubuntu. `EYESONU_DEPLOY_TEST_LOCAL_FIXTURE=1` is set
# only by the repository regression harness; Jenkins starts this runner with
# `env -i`, so a real SSH deployment cannot inherit it. The kernel fallback is
# for the Git for Windows local harness.
test_local_fixture="${EYESONU_DEPLOY_TEST_LOCAL_FIXTURE:-}"
case "$test_local_fixture" in
    ''|1) ;;
    *)
        echo "ERROR: EYESONU_DEPLOY_TEST_LOCAL_FIXTURE must be empty or 1." >&2
        exit 1
        ;;
esac

# Detect the local Git for Windows fixture from the kernel, not an environment
# variable that an SSH session could inherit.
host_kernel="$(/usr/bin/uname -s 2>/dev/null || uname -s)"
case "$host_kernel" in
    MINGW*|MSYS*|CYGWIN*)
        is_local_windows_fixture=true
        ;;
    *)
        is_local_windows_fixture=false
        ;;
esac

if [[ "$test_local_fixture" == 1 ]]; then
    is_local_fixture=true
else
    is_local_fixture="$is_local_windows_fixture"
fi

if [[ "$is_local_fixture" == true ]]; then
    runtime_path="$PATH"
    git_bin="$(type -P git || true)"
    msystem_value="${MSYSTEM:-}"
else
    runtime_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    git_bin="/usr/bin/git"
    msystem_value=""
fi

[[ -n "$git_bin" && -x "$git_bin" ]] || {
    echo "ERROR: required Git executable is unavailable." >&2
    exit 1
}

export PATH="$runtime_path"
command -v flock >/dev/null 2>&1 || {
    echo "ERROR: flock is required to serialize verified deployments." >&2
    exit 1
}

verify_remote_shell_security() {
    # This gate is evaluated on the Ubuntu deployment host. The regression
    # harness deliberately bypasses it through its explicit test-only flag.
    [[ "$is_local_fixture" == true ]] && return

    [[ "$deploy_user" == "eyesonu-deploy" ]] || {
        echo "ERROR: deployment SSH user must be the dedicated eyesonu-deploy account." >&2
        exit 1
    }
    local security_validator="/usr/local/sbin/eyesonu-verify-deployment-host-security"
    [[ -x "$security_validator" && -x /usr/bin/sudo ]] || {
        echo "ERROR: deployment host security validator is not installed." >&2
        exit 1
    }
    /usr/bin/sudo -n "$security_validator" "$deploy_user" "$deploy_env_file" || {
        echo "ERROR: deployment host security validator rejected the SSH execution boundary." >&2
        exit 1
    }
}

verify_remote_shell_security

if [[ "$is_local_fixture" == true ]]; then
    release_root="$(dirname "$checkout_root")/.eyesonu-deploy-releases"
    [[ ! -L "$release_root" ]] || {
        echo "ERROR: verified deployment release directory must not be a symlink." >&2
        exit 1
    }
    mkdir -p -- "$release_root"
    [[ -d "$release_root" && ! -L "$release_root" ]] || {
        echo "ERROR: verified deployment release directory must be a real directory." >&2
        exit 1
    }
    lock_file="$release_root/.deployment.lock"
    : > "$lock_file"
    exec 9>"$lock_file"
else
    # Production storage is provisioned by root beneath a non-writable parent.
    # Do not create or canonicalize it here: both would hide a hostile symlink.
    release_root="/var/lib/eyesonu-deploy/releases"
    lock_file="/var/lib/eyesonu-deploy/deployment.lock"
    [[ -d "$release_root" && ! -L "$release_root" ]] || {
        echo "ERROR: root-provisioned release directory is unavailable or unsafe." >&2
        exit 1
    }
    [[ -f "$lock_file" && ! -L "$lock_file" ]] || {
        echo "ERROR: root-provisioned deployment lock file is unavailable or unsafe." >&2
        exit 1
    }
    # The root-owned lock is opened read-only, which is sufficient for flock
    # and prevents truncation through a path replacement.
    exec 9<"$lock_file"
fi
active_release_file="$release_root/.active-release-$profile"
previous_release=""
previous_release_digest=""
if ! flock -n 9; then
    echo "ERROR: another verified deployment is already running for this checkout." >&2
    exit 1
fi

if [[ "$is_local_fixture" == true ]]; then
    runtime_root="$checkout_root/infra"
else
    runtime_root="/var/lib/eyesonu-deploy/runtime"
fi

# Do not honor an inherited TMPDIR at the host trust boundary. These
# directories live under the validated, non-symlinked release root instead.
empty_home=""
empty_hooks=""
empty_template=""
safe_git_config=""
pending_repository=""
pending_tree=""
active_release_temp=""

cleanup() {
    local status=$?
    local cleanup_failed=false

    trap - EXIT
    if [[ -n "$pending_repository" && "$pending_repository" == "$release_root"/.pending-git-* && -d "$pending_repository" && ! -L "$pending_repository" ]]; then
        if ! rm -rf -- "$pending_repository" && [[ -e "$pending_repository" || -L "$pending_repository" ]]; then
            echo "ERROR: could not remove temporary Git repository: $pending_repository" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$pending_repository" && ( -e "$pending_repository" || -L "$pending_repository" ) ]]; then
        echo "ERROR: temporary Git repository path became unsafe: $pending_repository" >&2
        cleanup_failed=true
    fi
    if [[ -n "$pending_tree" && "$pending_tree" == "$release_root"/.pending-* && -d "$pending_tree" && ! -L "$pending_tree" ]]; then
        if ! rm -rf -- "$pending_tree" && [[ -e "$pending_tree" || -L "$pending_tree" ]]; then
            echo "ERROR: could not remove temporary release tree: $pending_tree" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$pending_tree" && ( -e "$pending_tree" || -L "$pending_tree" ) ]]; then
        echo "ERROR: temporary release tree path became unsafe: $pending_tree" >&2
        cleanup_failed=true
    fi
    if [[ -n "$active_release_temp" && "$active_release_temp" == "$release_root"/.active-release-"$profile".* && -f "$active_release_temp" && ! -L "$active_release_temp" ]]; then
        if ! rm -f -- "$active_release_temp" && [[ -e "$active_release_temp" || -L "$active_release_temp" ]]; then
            echo "ERROR: could not remove temporary active-release marker: $active_release_temp" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$active_release_temp" && ( -e "$active_release_temp" || -L "$active_release_temp" ) ]]; then
        echo "ERROR: temporary active-release marker path became unsafe: $active_release_temp" >&2
        cleanup_failed=true
    fi
    if [[ -n "$safe_git_config" && "$safe_git_config" == "$release_root"/.git-home.*/gitconfig ]]; then
        if ! rm -f -- "$safe_git_config" && [[ -e "$safe_git_config" || -L "$safe_git_config" ]]; then
            echo "ERROR: could not remove temporary Git config: $safe_git_config" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$safe_git_config" && ( -e "$safe_git_config" || -L "$safe_git_config" ) ]]; then
        echo "ERROR: temporary Git config path became unsafe: $safe_git_config" >&2
        cleanup_failed=true
    fi
    if [[ -n "$empty_template" && "$empty_template" == "$release_root"/.git-template.* && -d "$empty_template" && ! -L "$empty_template" ]]; then
        if ! rmdir -- "$empty_template" && [[ -e "$empty_template" || -L "$empty_template" ]]; then
            echo "ERROR: temporary Git template directory was not empty: $empty_template" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$empty_template" && ( -e "$empty_template" || -L "$empty_template" ) ]]; then
        echo "ERROR: temporary Git template path became unsafe: $empty_template" >&2
        cleanup_failed=true
    fi
    if [[ -n "$empty_hooks" && "$empty_hooks" == "$release_root"/.git-hooks.* && -d "$empty_hooks" && ! -L "$empty_hooks" ]]; then
        if ! rmdir -- "$empty_hooks" && [[ -e "$empty_hooks" || -L "$empty_hooks" ]]; then
            echo "ERROR: temporary Git hooks directory was not empty: $empty_hooks" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$empty_hooks" && ( -e "$empty_hooks" || -L "$empty_hooks" ) ]]; then
        echo "ERROR: temporary Git hooks path became unsafe: $empty_hooks" >&2
        cleanup_failed=true
    fi
    if [[ -n "$empty_home" && "$empty_home" == "$release_root"/.git-home.* && -d "$empty_home" && ! -L "$empty_home" ]]; then
        if ! rmdir -- "$empty_home" && [[ -e "$empty_home" || -L "$empty_home" ]]; then
            echo "ERROR: temporary Git home directory was not empty: $empty_home" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$empty_home" && ( -e "$empty_home" || -L "$empty_home" ) ]]; then
        echo "ERROR: temporary Git home path became unsafe: $empty_home" >&2
        cleanup_failed=true
    fi
    if [[ "$cleanup_failed" == true ]]; then
        echo "ERROR: verified deployment temporary cleanup was incomplete." >&2
        [[ "$status" -ne 0 ]] || status=1
    fi
    exit "$status"
}
trap cleanup EXIT

empty_home="$(mktemp -d "$release_root/.git-home.XXXXXX")"
empty_hooks="$(mktemp -d "$release_root/.git-hooks.XXXXXX")"
empty_template="$(mktemp -d "$release_root/.git-template.XXXXXX")"
safe_git_config="$empty_home/gitconfig"

# The deployment checkout is normally owned by the Jenkins service account
# while this runner executes as eyesonu-deploy. Keep system/global settings
# disabled, but permit this one canonical checkout through a private global
# configuration file. No other repository is marked safe.
printf '[safe]\n\tdirectory = %s\n' "$checkout_root" > "$safe_git_config"

git_environment=(
    "PATH=$runtime_path"
    "HOME=$empty_home"
    "XDG_CONFIG_HOME=$empty_home"
    "LC_ALL=C"
    "GIT_CONFIG_NOSYSTEM=1"
    "GIT_CONFIG_GLOBAL=$safe_git_config"
    "GIT_CONFIG_COUNT=0"
    "GIT_ATTR_NOSYSTEM=1"
    "GIT_NO_REPLACE_OBJECTS=1"
    "GIT_OPTIONAL_LOCKS=0"
)
archive_environment=(
    "PATH=$runtime_path"
    "HOME=$empty_home"
    "LC_ALL=C"
)
if [[ -n "$msystem_value" ]]; then
    git_environment+=("MSYSTEM=$msystem_value")
    archive_environment+=("MSYSTEM=$msystem_value")
fi

git_safely() {
    env -i "${git_environment[@]}" "$git_bin" \
        --no-replace-objects \
        -c core.hooksPath="$empty_hooks" \
        -c core.fsmonitor=false \
        -c core.autocrlf=false \
        -c core.attributesFile=/dev/null \
        "$@"
}

release_tree_digest() {
    local release_path="$1"

    [[ -d "$release_path" && ! -L "$release_path" ]] || {
        echo "ERROR: release digest target is unavailable or unsafe." >&2
        return 1
    }

    (
        cd "$release_path" || exit $?
        find . -xdev -mindepth 1 -print0 \
            | LC_ALL=C sort -z \
            | while IFS= read -r -d '' relative_path; do
                file_mode="$(stat -c '%a' -- "$relative_path")" || exit $?
                if [[ -L "$relative_path" ]]; then
                    printf 'L\0%s\0%s\0%s\0' "$file_mode" "$relative_path" "$(readlink -- "$relative_path")"
                elif [[ -f "$relative_path" ]]; then
                    printf 'F\0%s\0%s\0' "$file_mode" "$relative_path"
                    sha256sum < "$relative_path"
                    printf '\0'
                elif [[ -d "$relative_path" ]]; then
                    printf 'D\0%s\0%s\0' "$file_mode" "$relative_path"
                else
                    echo "ERROR: release digest found an unsupported filesystem entry: $relative_path" >&2
                    exit 1
                fi
            done \
            | sha256sum \
            | awk '{print $1}'
    )
}

read_active_release() {
    local active_release
    local active_release_digest
    local current_release_digest
    local -a active_marker_lines=()

    if [[ ! -e "$active_release_file" && ! -L "$active_release_file" ]]; then
        return 0
    fi
    [[ -f "$active_release_file" && ! -L "$active_release_file" ]] || {
        echo "ERROR: active release marker is unavailable or unsafe." >&2
        return 1
    }
    mapfile -t active_marker_lines < "$active_release_file"
    [[ "${#active_marker_lines[@]}" -eq 2 ]] || {
        echo "ERROR: active release marker must contain exactly a release path and digest." >&2
        return 1
    }
    active_release="${active_marker_lines[0]}"
    active_release_digest="${active_marker_lines[1]}"
    [[ "$active_release_digest" =~ ^[0-9a-f]{64}$ ]] || {
        echo "ERROR: active release marker digest is invalid." >&2
        return 1
    }
    [[ "$active_release" == "$release_root"/release-* && -d "$active_release" && ! -L "$active_release" ]] || {
        echo "ERROR: active release marker does not reference a verified release directory." >&2
        return 1
    }
    [[ -f "$active_release/infra/compose.deploy.yml" && ! -L "$active_release/infra/compose.deploy.yml" ]] || {
        echo "ERROR: active release marker references an incomplete release." >&2
        return 1
    }
    current_release_digest="$(release_tree_digest "$active_release")" || {
        echo "ERROR: could not verify active release content before rollback." >&2
        return 1
    }
    [[ "$current_release_digest" == "$active_release_digest" ]] || {
        echo "ERROR: active release content digest no longer matches its verified marker." >&2
        return 1
    }
    printf '%s\t%s\n' "$active_release" "$active_release_digest"
}

load_previous_release() {
    local active_release_metadata

    active_release_metadata="$(read_active_release)" || return 1
    if [[ -z "$active_release_metadata" ]]; then
        previous_release=""
        previous_release_digest=""
        return 0
    fi
    IFS=$'\t' read -r previous_release previous_release_digest <<< "$active_release_metadata"
    [[ -n "$previous_release" && "$previous_release_digest" =~ ^[0-9a-f]{64}$ ]] || {
        echo "ERROR: verified active release metadata is malformed." >&2
        return 1
    }
}

verify_previous_release_is_still_active() {
    local active_release_metadata

    [[ -n "$previous_release" && -n "$previous_release_digest" ]] || return 1
    if ! active_release_metadata="$(read_active_release)"; then
        echo "ERROR: active release marker changed or became invalid before rollback; refusing to restore an unverified release." >&2
        return 1
    fi
    [[ "$active_release_metadata" == "$previous_release"$'\t'"$previous_release_digest" ]] || {
        echo "ERROR: active release marker changed or became invalid before rollback; refusing to restore an unverified release." >&2
        return 1
    }
}

preflight_active_marker_write() {
    [[ ! -L "$active_release_file" ]] || {
        echo "ERROR: active release marker path must not be a symlink." >&2
        return 1
    }
    active_release_temp="$(mktemp "$release_root/.active-release-$profile.preflight.XXXXXX")" || return 1
    if ! rm -f -- "$active_release_temp"; then
        echo "ERROR: active release marker path is not safely writable." >&2
        return 1
    fi
    active_release_temp=""
}

publish_active_release() {
    local release_digest

    release_digest="$(release_tree_digest "$deployment_tree")" || return 1
    active_release_temp="$(mktemp "$release_root/.active-release-$profile.XXXXXX")" || return 1
    printf '%s\n%s\n' "$deployment_tree" "$release_digest" > "$active_release_temp" || return 1
    chmod 0660 "$active_release_temp" || return 1
    mv -T -- "$active_release_temp" "$active_release_file" || return 1
    active_release_temp=""
}

rollback_after_marker_publication_failure() {
    verify_previous_release_is_still_active || return 1

    env -u BASH_ENV -u ENV \
        DEPLOY_ROOT="$deployment_tree" \
        DEPLOY_PREVIOUS_RELEASE="$previous_release" \
        DEPLOY_ROLLBACK_ONLY=1 \
        DEPLOY_ENV_FILE="$deploy_env_file" \
        DEPLOY_RUNTIME_ROOT="$runtime_root" \
        DEPLOY_COMPOSE="$deployment_tree/infra/compose.deploy.yml" \
        bash "$deploy_script" "$profile"
}

stop_candidate_profile() {
    env -u BASH_ENV -u ENV \
        DEPLOY_ROOT="$deployment_tree" \
        DEPLOY_STOP_ONLY=1 \
        DEPLOY_ENV_FILE="$deploy_env_file" \
        DEPLOY_RUNTIME_ROOT="$runtime_root" \
        DEPLOY_COMPOSE="$deployment_tree/infra/compose.deploy.yml" \
        bash "$deploy_script" "$profile"
}

deploy_verified_release() {
    env -u BASH_ENV -u ENV \
        DEPLOY_ROOT="$deployment_tree" \
        DEPLOY_ENV_FILE="$deploy_env_file" \
        DEPLOY_RUNTIME_ROOT="$runtime_root" \
        DEPLOY_COMPOSE="$deployment_tree/infra/compose.deploy.yml" \
        bash "$deploy_script" "$profile"
}

source_commit="$(git_safely -C "$checkout_root" rev-parse --verify "${expected_commit}^{commit}")" || {
    echo "ERROR: expected deployment commit is unavailable in the host object database." >&2
    exit 1
}
if [[ "$source_commit" != "$expected_commit" ]]; then
    echo "ERROR: host object database did not resolve the Jenkins build commit exactly." >&2
    exit 1
fi

# Materialize an isolated temporary repository first. This keeps source
# checkout metadata such as info/attributes, indexes, and hooks outside the
# trusted archive path before a fresh Git-free release tree is published.
pending_repository="$(mktemp -d "$release_root/.pending-git-${expected_commit}.XXXXXX")"
rmdir "$pending_repository"
git_safely clone --shared --no-checkout --template="$empty_template" \
    "$checkout_root" "$pending_repository" >/dev/null

# A previous bind-mounted release can remain intact for running containers, but
# its files and metadata can never influence a later deployment.
pending_tree="$(mktemp -d "$release_root/.pending-${expected_commit}.XXXXXX")"
if ! git_safely -C "$pending_repository" archive --format=tar "$expected_commit" \
    | env -i "${archive_environment[@]}" tar --no-same-owner --no-same-permissions -xf - -C "$pending_tree"; then
    echo "ERROR: could not materialize the verified deployment release." >&2
    exit 1
fi
rm -rf -- "$pending_repository"
pending_repository=""
[[ ! -e "$pending_tree/.git" ]] || {
    echo "ERROR: verified deployment release must not retain Git metadata." >&2
    exit 1
}

release_name="${pending_tree##*/}"
deployment_tree="$release_root/release-${release_name#.pending-}"
mv -T -- "$pending_tree" "$deployment_tree"
pending_tree=""
load_previous_release || {
    echo "ERROR: could not load the previously active verified release." >&2
    exit 1
}

deploy_script="$deployment_tree/infra/scripts/deploy-on-host.sh"
if [[ ! -f "$deploy_script" || -L "$deploy_script" ]]; then
    echo "ERROR: deploy script is missing from the verified deployment tree." >&2
    exit 1
fi

preflight_active_marker_write || {
    echo "ERROR: active release marker cannot be updated safely; deployment was not started." >&2
    exit 1
}

if ! deploy_verified_release; then
    echo "ERROR: verified release deployment failed." >&2
    if ! stop_candidate_profile; then
        echo "ERROR: failed candidate cleanup also failed; operator intervention is required." >&2
        exit 1
    fi
    if [[ -n "$previous_release" ]]; then
        if rollback_after_marker_publication_failure; then
            echo "WARN: rollback completed; the new release was not marked active." >&2
        else
            echo "ERROR: rollback also failed after candidate cleanup; operator intervention is required." >&2
        fi
    else
        echo "WARN: unmarked first-release services were stopped after deployment failed." >&2
    fi
    exit 1
fi
if ! publish_active_release; then
    echo "ERROR: verified release started, but its active marker could not be published." >&2
    if ! stop_candidate_profile; then
        echo "ERROR: failed candidate cleanup also failed after active-marker publication failure; operator intervention is required." >&2
        exit 1
    fi
    if [[ -n "$previous_release" ]]; then
        if rollback_after_marker_publication_failure; then
            echo "WARN: rollback completed after active-marker publication failed." >&2
        else
            echo "ERROR: rollback also failed after active-marker publication failure and candidate cleanup; operator intervention is required." >&2
        fi
    else
        echo "WARN: unmarked first-release services were stopped after active-marker publication failed." >&2
    fi
    exit 1
fi
