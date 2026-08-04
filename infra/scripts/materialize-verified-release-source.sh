#!/usr/bin/env bash
set -Eeuo pipefail

profile="${1:-}"
event_commit="${2:-}"

case "$profile" in
    dev|master) ;;
    *)
        echo "Usage: $0 {dev|master} [event-commit]" >&2
        exit 2
        ;;
esac

if [[ -n "$event_commit" && ! "$event_commit" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]]; then
    echo "ERROR: event commit must be a full lowercase object ID." >&2
    exit 1
fi

checkout_root="$(pwd -P)"
release_dir="$checkout_root/.verified-release-source"
release_commit_file="$checkout_root/.verified-release-commit"

# A retained marker must never redirect the pipeline's post-materialization
# read to another path. Removing a symlink itself is safe; an unexpected
# directory fails closed below instead of being followed.
if [[ -e "$release_commit_file" || -L "$release_commit_file" ]]; then
    rm -f -- "$release_commit_file"
fi

# Jenkins production agents are Linux. This fallback lets the repository's
# Git Bash regression harness exercise the same no-checkout archive flow.
host_kernel="$(/usr/bin/uname -s 2>/dev/null || uname -s)"
case "$host_kernel" in
    MINGW*|MSYS*|CYGWIN*)
        runtime_path="$PATH"
        trusted_git="$(type -P git || true)"
        msystem_value="${MSYSTEM:-}"
        ;;
    *)
        runtime_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        trusted_git="/usr/bin/git"
        msystem_value=""
        ;;
esac

[[ -x "$trusted_git" ]] || {
    echo "ERROR: trusted Git executable is unavailable." >&2
    exit 1
}

empty_home=""
empty_hooks=""
empty_template=""
safe_git_config=""
pending_repository=""
pending_tree=""

cleanup() {
    local status=$?
    local cleanup_failed=false

    trap - EXIT
    if [[ -n "$pending_repository" && "$pending_repository" == "$checkout_root"/.verified-git-source.* && -d "$pending_repository" && ! -L "$pending_repository" ]]; then
        if ! rm -rf -- "$pending_repository" && [[ -e "$pending_repository" || -L "$pending_repository" ]]; then
            echo "ERROR: could not remove temporary verified source repository: $pending_repository" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$pending_repository" && ( -e "$pending_repository" || -L "$pending_repository" ) ]]; then
        echo "ERROR: temporary verified source repository path became unsafe: $pending_repository" >&2
        cleanup_failed=true
    fi
    if [[ -n "$pending_tree" && "$pending_tree" == "$checkout_root"/.verified-release-source.* && -d "$pending_tree" && ! -L "$pending_tree" ]]; then
        if ! rm -rf -- "$pending_tree" && [[ -e "$pending_tree" || -L "$pending_tree" ]]; then
            echo "ERROR: could not remove temporary verified source tree: $pending_tree" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$pending_tree" && ( -e "$pending_tree" || -L "$pending_tree" ) ]]; then
        echo "ERROR: temporary verified source tree path became unsafe: $pending_tree" >&2
        cleanup_failed=true
    fi
    if [[ -n "$safe_git_config" && "$safe_git_config" == "$checkout_root"/.verified-git-home.*/gitconfig ]]; then
        if ! rm -f -- "$safe_git_config" && [[ -e "$safe_git_config" || -L "$safe_git_config" ]]; then
            echo "ERROR: could not remove temporary verified-source Git config: $safe_git_config" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$safe_git_config" && ( -e "$safe_git_config" || -L "$safe_git_config" ) ]]; then
        echo "ERROR: temporary verified-source Git config path became unsafe: $safe_git_config" >&2
        cleanup_failed=true
    fi
    if [[ -n "$empty_template" && "$empty_template" == "$checkout_root"/.verified-git-template.* && -d "$empty_template" && ! -L "$empty_template" ]]; then
        if ! rmdir -- "$empty_template" && [[ -e "$empty_template" || -L "$empty_template" ]]; then
            echo "ERROR: temporary verified-source Git template directory was not empty: $empty_template" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$empty_template" && ( -e "$empty_template" || -L "$empty_template" ) ]]; then
        echo "ERROR: temporary verified-source Git template path became unsafe: $empty_template" >&2
        cleanup_failed=true
    fi
    if [[ -n "$empty_hooks" && "$empty_hooks" == "$checkout_root"/.verified-git-hooks.* && -d "$empty_hooks" && ! -L "$empty_hooks" ]]; then
        if ! rmdir -- "$empty_hooks" && [[ -e "$empty_hooks" || -L "$empty_hooks" ]]; then
            echo "ERROR: temporary verified-source Git hooks directory was not empty: $empty_hooks" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$empty_hooks" && ( -e "$empty_hooks" || -L "$empty_hooks" ) ]]; then
        echo "ERROR: temporary verified-source Git hooks path became unsafe: $empty_hooks" >&2
        cleanup_failed=true
    fi
    if [[ -n "$empty_home" && "$empty_home" == "$checkout_root"/.verified-git-home.* && -d "$empty_home" && ! -L "$empty_home" ]]; then
        if ! rmdir -- "$empty_home" && [[ -e "$empty_home" || -L "$empty_home" ]]; then
            echo "ERROR: temporary verified-source Git home directory was not empty: $empty_home" >&2
            cleanup_failed=true
        fi
    elif [[ -n "$empty_home" && ( -e "$empty_home" || -L "$empty_home" ) ]]; then
        echo "ERROR: temporary verified-source Git home path became unsafe: $empty_home" >&2
        cleanup_failed=true
    fi
    if [[ "$cleanup_failed" == true ]]; then
        echo "ERROR: verified source materialization temporary cleanup was incomplete." >&2
        [[ "$status" -ne 0 ]] || status=1
    fi
    exit "$status"
}
trap cleanup EXIT

empty_home="$(mktemp -d "$checkout_root/.verified-git-home.XXXXXX")"
empty_hooks="$(mktemp -d "$checkout_root/.verified-git-hooks.XXXXXX")"
empty_template="$(mktemp -d "$checkout_root/.verified-git-template.XXXXXX")"
safe_git_config="$empty_home/gitconfig"

# Only this canonical Jenkins checkout is admitted when Git's ownership check
# applies. System/global settings remain disabled for every Git invocation.
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
    env -i "${git_environment[@]}" "$trusted_git" \
        --no-replace-objects \
        -c core.hooksPath="$empty_hooks" \
        -c core.fsmonitor=false \
        -c core.autocrlf=false \
        -c core.attributesFile=/dev/null \
        "$@"
}

release_commit="$(git_safely -C "$checkout_root" rev-parse --verify "refs/remotes/origin/$profile^{commit}")" || {
    echo "ERROR: protected Jenkins checkout is missing the canonical $profile ref." >&2
    exit 1
}
if [[ -n "$event_commit" && "$release_commit" != "$event_commit" ]]; then
    echo "ERROR: GitLab event SHA does not match the canonical release ref; retry the newer event." >&2
    exit 1
fi

pending_repository="$(mktemp -d "$checkout_root/.verified-git-source.XXXXXX")"
rmdir "$pending_repository"
git_safely clone --shared --no-checkout --template="$empty_template" \
    "$checkout_root" "$pending_repository" >/dev/null

pending_tree="$(mktemp -d "$checkout_root/.verified-release-source.XXXXXX")"
if ! git_safely -C "$pending_repository" archive --format=tar "$release_commit" \
    | env -i "${archive_environment[@]}" tar --no-same-owner --no-same-permissions -xf - -C "$pending_tree"; then
    echo "ERROR: could not materialize the verified Jenkins release source." >&2
    exit 1
fi
rm -rf -- "$pending_repository"
pending_repository=""
[[ ! -e "$pending_tree/.git" ]] || {
    echo "ERROR: verified Jenkins release source must not retain Git metadata." >&2
    exit 1
}

if [[ -e "$release_dir" || -L "$release_dir" ]]; then
    rm -rf -- "$release_dir"
fi
mv -T -- "$pending_tree" "$release_dir"
pending_tree=""
[[ ! -L "$release_commit_file" ]] || {
    echo "ERROR: verified Jenkins release commit marker must not be a symlink." >&2
    exit 1
}
printf '%s\n' "$release_commit" > "$release_commit_file"

echo "PASS: materialized verified $profile release source at $release_commit"
