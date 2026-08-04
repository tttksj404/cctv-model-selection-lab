#!/bin/bash
set -Eeuo pipefail

export PATH=/usr/sbin:/usr/bin:/sbin:/bin

deploy_user="${1:-}"
deploy_env_file="${2:-}"
validator_path="${BASH_SOURCE[0]}"
release_base="/var/lib/eyesonu-deploy"
release_root="$release_base/releases"
lock_file="$release_base/deployment.lock"
runtime_root="$release_base/runtime"
nginx_runtime_root="$runtime_root/nginx"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

require_root_managed_runtime_directory() {
    local path="$1"
    local permissions

    [[ -d "$path" && ! -L "$path" ]] \
        || fail "root-provisioned runtime directory is missing or symlinked: $path"
    [[ "$(/usr/bin/stat -c '%U' "$path")" == "root" ]] \
        || fail "root-provisioned runtime directory must be root-owned: $path"
    permissions="$(/usr/bin/stat -c '%a' "$path")"
    (( (8#$permissions & 8#022) == 0 )) \
        || fail "root-provisioned runtime directory must not be group/world writable: $path"
}

require_root_managed_runtime_file() {
    local path="$1"
    local permissions

    [[ -f "$path" && ! -L "$path" ]] \
        || fail "root-provisioned runtime file is missing or symlinked: $path"
    [[ "$(/usr/bin/stat -c '%U' "$path")" == "root" ]] \
        || fail "root-provisioned runtime file must be root-owned: $path"
    permissions="$(/usr/bin/stat -c '%a' "$path")"
    (( (8#$permissions & 8#022) == 0 )) \
        || fail "root-provisioned runtime file must not be group/world writable: $path"
}

require_root_managed_runtime_tree() {
    local root="$1"
    local path
    local find_pid

    while IFS= read -r -d '' path; do
        if [[ -d "$path" ]]; then
            require_root_managed_runtime_directory "$path"
        elif [[ -f "$path" ]]; then
            require_root_managed_runtime_file "$path"
        else
            fail "root-provisioned runtime tree must contain only real files and directories: $path"
        fi
    done < <(/usr/bin/find -P "$root" -xdev -print0)
    find_pid="$!"
    wait "$find_pid" || fail "could not enumerate root-provisioned runtime tree: $root"
}

[[ "$(/usr/bin/id -u)" -eq 0 ]] || fail "deployment host security validator must run as root"
[[ "$deploy_user" == "eyesonu-deploy" ]] || fail "security validator only accepts the dedicated eyesonu-deploy account"
[[ -x /usr/sbin/sshd && -x /usr/bin/getent && -x /usr/bin/stat && -x /usr/bin/dirname && -x /usr/bin/find ]] \
    || fail "required host security utilities are unavailable"
[[ -f "$validator_path" && ! -L "$validator_path" ]] \
    || fail "deployment host security validator must be a real file"
[[ "$(/usr/bin/stat -c '%U' "$validator_path")" == "root" ]] \
    || fail "deployment host security validator must be root-owned"
validator_permissions="$(/usr/bin/stat -c '%a' "$validator_path")"
(( (8#$validator_permissions & 8#022) == 0 )) \
    || fail "deployment host security validator must not be group/world writable"

account_entry="$(/usr/bin/getent passwd "$deploy_user")"
[[ -n "$account_entry" ]] || fail "dedicated deployment account is missing"
IFS=: read -r _ _ _ _ _ deploy_home deploy_shell <<< "$account_entry"
[[ "$deploy_shell" == "/bin/sh" ]] \
    || fail "dedicated deployment account must use /bin/sh"
[[ "$deploy_home" == /* && -d "$deploy_home" && ! -L "$deploy_home" ]] \
    || fail "dedicated deployment home must be a real absolute directory"

for protected_path in "$deploy_home" "$deploy_home/.ssh" "$deploy_home/.ssh/authorized_keys"; do
    [[ -e "$protected_path" && ! -L "$protected_path" ]] \
        || fail "required deployment SSH path is missing or symlinked: $protected_path"
    [[ "$(/usr/bin/stat -c '%U' "$protected_path")" == "root" ]] \
        || fail "deployment SSH path must be root-owned: $protected_path"
    permissions="$(/usr/bin/stat -c '%a' "$protected_path")"
    (( (8#$permissions & 8#022) == 0 )) \
        || fail "deployment SSH path must not be group/world writable: $protected_path"
done

[[ "$deploy_env_file" == /* ]] || fail "deployment env file path must be absolute"
deploy_env_dir="$(/usr/bin/dirname "$deploy_env_file")"
[[ -d "$deploy_env_dir" && ! -L "$deploy_env_dir" ]] \
    || fail "deployment env directory must be a real directory"
[[ "$(/usr/bin/stat -c '%U' "$deploy_env_dir")" == "root" ]] \
    || fail "deployment env directory must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$deploy_env_dir")" == "$deploy_user" ]] \
    || fail "deployment env directory must be group-owned by the deployment account"
deploy_env_directory_permissions="$(/usr/bin/stat -c '%a' "$deploy_env_dir")"
[[ "$deploy_env_directory_permissions" == 750 ]] \
    || fail "deployment env directory must use mode 0750"
[[ -f "$deploy_env_file" && ! -L "$deploy_env_file" ]] \
    || fail "deployment env file must be a real file"
[[ "$(/usr/bin/stat -c '%U' "$deploy_env_file")" == "root" ]] \
    || fail "deployment env file must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$deploy_env_file")" == "$deploy_user" ]] \
    || fail "deployment env file must be group-owned by the deployment account"
deploy_env_permissions="$(/usr/bin/stat -c '%a' "$deploy_env_file")"
[[ "$deploy_env_permissions" == 640 ]] \
    || fail "deployment env file must use mode 0640"

[[ -d "$release_base" && ! -L "$release_base" ]] \
    || fail "root-provisioned release base must be a real directory"
[[ "$(/usr/bin/stat -c '%U' "$release_base")" == "root" ]] \
    || fail "release base must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$release_base")" == "$deploy_user" ]] \
    || fail "release base must be group-owned by the deployment account"
release_base_permissions="$(/usr/bin/stat -c '%a' "$release_base")"
(( (8#$release_base_permissions & 8#022) == 0 )) \
    || fail "release base must not be group/world writable"
(( (8#$release_base_permissions & 8#0050) == 8#0050 )) \
    || fail "release base must grant the deployment group read and execute access"

for runtime_directory in \
    "$runtime_root" \
    "$runtime_root/certbot" \
    "$runtime_root/certbot/www" \
    "$runtime_root/certbot/conf" \
    "$nginx_runtime_root" \
    "$nginx_runtime_root/conf.d" \
    "$nginx_runtime_root/snippets"; do
    require_root_managed_runtime_directory "$runtime_directory"
done
require_root_managed_runtime_file "$nginx_runtime_root/conf.d/default.conf"
require_root_managed_runtime_file "$nginx_runtime_root/snippets/ssl-params.conf"
require_root_managed_runtime_tree "$runtime_root/certbot/www"
require_root_managed_runtime_tree "$runtime_root/certbot/conf"
require_root_managed_runtime_tree "$nginx_runtime_root/conf.d"
require_root_managed_runtime_tree "$nginx_runtime_root/snippets"

[[ -d "$release_root" && ! -L "$release_root" ]] \
    || fail "root-provisioned release directory must be a real directory"
[[ "$(/usr/bin/stat -c '%U' "$release_root")" == "root" ]] \
    || fail "release directory must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$release_root")" == "$deploy_user" ]] \
    || fail "release directory must be group-owned by the deployment account"
release_permissions="$(/usr/bin/stat -c '%a' "$release_root")"
(( (8#$release_permissions & 8#0007) == 0 )) \
    || fail "release directory must not grant permissions to others"
(( (8#$release_permissions & 8#0070) == 8#0070 )) \
    || fail "release directory must grant the deployment group rwx access"

[[ -f "$lock_file" && ! -L "$lock_file" ]] \
    || fail "root-provisioned deployment lock must be a real file"
[[ "$(/usr/bin/stat -c '%U' "$lock_file")" == "root" ]] \
    || fail "deployment lock must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$lock_file")" == "$deploy_user" ]] \
    || fail "deployment lock must be group-owned by the deployment account"
lock_permissions="$(/usr/bin/stat -c '%a' "$lock_file")"
(( (8#$lock_permissions & 8#0022) == 0 )) \
    || fail "deployment lock must not be group/world writable"

sshd_settings="$(/usr/sbin/sshd -T -C "user=$deploy_user,host=localhost,addr=127.0.0.1" 2>/dev/null)" \
    || fail "could not read effective sshd settings"
/usr/bin/grep -Fxq 'permituserenvironment no' <<< "$sshd_settings" \
    || fail "sshd must set PermitUserEnvironment no for the deployment user"
/usr/bin/grep -Fxq 'permituserrc no' <<< "$sshd_settings" \
    || fail "sshd must set PermitUserRC no for the deployment user"

echo "PASS: deployment SSH execution boundary is hardened for $deploy_user"
