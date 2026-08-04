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
checkout_root="/home/ubuntu/jenkins-data/workspace/ssafy-a204-infra"
forced_command_path="/usr/local/libexec/eyesonu-deploy-forced-command"
deployment_broker_path="/usr/local/libexec/eyesonu-run-deployment"
sudoers_file="/etc/sudoers.d/eyesonu-deploy"

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

require_root_managed_executable() {
    local path="$1"

    require_root_managed_runtime_file "$path"
    [[ -x "$path" ]] || fail "root-managed deployment executable is not executable: $path"
}

require_root_managed_certbot_live_link() {
    local certbot_root="$1"
    local path="$2"
    local relative_path
    local lineage
    local certificate_file
    local certificate_name
    local extra_path
    local resolved_target
    local target_suffix
    local expected_prefix
    local link_owner

    relative_path="${path#"$certbot_root/live/"}"
    [[ "$relative_path" != "$path" ]] || fail "certificate live link is outside the live directory: $path"
    IFS=/ read -r lineage certificate_file extra_path <<< "$relative_path"
    [[ -n "$lineage" && -n "$certificate_file" && -z "$extra_path" ]] \
        || fail "certificate live link must have exactly one lineage and one file name: $path"
    [[ "$lineage" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
        || fail "certificate live link has an unsafe lineage name: $path"
    case "$certificate_file" in
        cert.pem|chain.pem|fullchain.pem|privkey.pem) ;;
        *) fail "certificate live link has an unsupported certificate name: $path" ;;
    esac

    [[ -L "$path" ]] || fail "certificate live entry must be a symlink: $path"
    link_owner="$(/usr/bin/stat -c '%U' -- "$path")"
    [[ "$link_owner" == "root" ]] || fail "certificate live symlink must be root-owned: $path"
    resolved_target="$(/usr/bin/readlink -f -- "$path")" \
        || fail "certificate live symlink does not resolve: $path"
    certificate_name="${certificate_file%.pem}"
    expected_prefix="$certbot_root/archive/$lineage/$certificate_name"
    [[ "$resolved_target" == "$expected_prefix"* ]] \
        || fail "certificate live symlink escapes its lineage archive: $path"
    target_suffix="${resolved_target#"$expected_prefix"}"
    [[ "$target_suffix" =~ ^[0-9]+\.pem$ ]] \
        || fail "certificate live symlink must target a numbered archive PEM: $path"
    require_root_managed_runtime_file "$resolved_target"
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

require_root_managed_certbot_configuration_tree() {
    local root="$1"
    local path
    local find_pid

    while IFS= read -r -d '' path; do
        if [[ -L "$path" ]]; then
            require_root_managed_certbot_live_link "$root" "$path"
        elif [[ -d "$path" ]]; then
            require_root_managed_runtime_directory "$path"
        elif [[ -f "$path" ]]; then
            require_root_managed_runtime_file "$path"
        else
            fail "root-provisioned Certbot tree must contain only directories, regular files, or approved live links: $path"
        fi
    done < <(/usr/bin/find -P "$root" -xdev -print0)
    find_pid="$!"
    wait "$find_pid" || fail "could not enumerate root-provisioned Certbot configuration tree: $root"
}

[[ "$(/usr/bin/id -u)" -eq 0 ]] || fail "deployment host security validator must run as root"
[[ "$deploy_user" == "eyesonu-deploy" ]] || fail "security validator only accepts the dedicated eyesonu-deploy account"
[[ -x /usr/sbin/sshd && -x /usr/bin/getent && -x /usr/bin/stat && -x /usr/bin/dirname && -x /usr/bin/find && -x /usr/bin/readlink ]] \
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

[[ -d "$checkout_root" && ! -L "$checkout_root" && -d "$checkout_root/.git" && ! -L "$checkout_root/.git" ]] \
    || fail "trusted deployment checkout must be a real Git checkout"
checkout_owner="$(/usr/bin/stat -c '%U' "$checkout_root")"
[[ "$checkout_owner" != "$deploy_user" ]] \
    || fail "trusted deployment checkout must not be owned by the deployment account"
checkout_permissions="$(/usr/bin/stat -c '%a' "$checkout_root")"
(( (8#$checkout_permissions & 8#022) == 0 )) \
    || fail "trusted deployment checkout must not be group/world writable"

for protected_path in "$deploy_home" "$deploy_home/.ssh" "$deploy_home/.ssh/authorized_keys"; do
    [[ -e "$protected_path" && ! -L "$protected_path" ]] \
        || fail "required deployment SSH path is missing or symlinked: $protected_path"
    [[ "$(/usr/bin/stat -c '%U' "$protected_path")" == "root" ]] \
        || fail "deployment SSH path must be root-owned: $protected_path"
    permissions="$(/usr/bin/stat -c '%a' "$protected_path")"
    (( (8#$permissions & 8#022) == 0 )) \
        || fail "deployment SSH path must not be group/world writable: $protected_path"
done

require_root_managed_executable "$forced_command_path"
require_root_managed_executable "$deployment_broker_path"
[[ -f "$sudoers_file" && ! -L "$sudoers_file" ]] \
    || fail "deployment sudoers policy is missing or symlinked"
[[ "$(/usr/bin/stat -c '%U' "$sudoers_file")" == "root" && "$(/usr/bin/stat -c '%G' "$sudoers_file")" == "root" ]] \
    || fail "deployment sudoers policy must be root-owned"
[[ "$(/usr/bin/stat -c '%a' "$sudoers_file")" == 440 ]] \
    || fail "deployment sudoers policy must use mode 0440"
/usr/bin/grep -Eq '^restrict,command="/usr/local/libexec/eyesonu-deploy-forced-command"[[:space:]]+(ssh-|sk-)' "$deploy_home/.ssh/authorized_keys" \
    || fail "deployment SSH key must use the restricted forced command"
/usr/bin/grep -Fxq 'eyesonu-deploy ALL=(root) NOPASSWD: /usr/local/libexec/eyesonu-run-deployment *' "$sudoers_file" \
    || fail "deployment sudoers policy must permit only the validated deployment broker"
if /usr/bin/id -nG "$deploy_user" | /usr/bin/tr ' ' '\n' | /usr/bin/grep -Fxq docker; then
    fail "deployment account must not have direct Docker Engine group access"
fi

[[ "$deploy_env_file" == /* ]] || fail "deployment env file path must be absolute"
deploy_env_dir="$(/usr/bin/dirname "$deploy_env_file")"
[[ -d "$deploy_env_dir" && ! -L "$deploy_env_dir" ]] \
    || fail "deployment env directory must be a real directory"
[[ "$(/usr/bin/stat -c '%U' "$deploy_env_dir")" == "root" ]] \
    || fail "deployment env directory must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$deploy_env_dir")" == "root" ]] \
    || fail "deployment env directory must be root-group-owned"
deploy_env_directory_permissions="$(/usr/bin/stat -c '%a' "$deploy_env_dir")"
[[ "$deploy_env_directory_permissions" == 700 ]] \
    || fail "deployment env directory must use mode 0700"
[[ -f "$deploy_env_file" && ! -L "$deploy_env_file" ]] \
    || fail "deployment env file must be a real file"
[[ "$(/usr/bin/stat -c '%U' "$deploy_env_file")" == "root" ]] \
    || fail "deployment env file must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$deploy_env_file")" == "root" ]] \
    || fail "deployment env file must be root-group-owned"
deploy_env_permissions="$(/usr/bin/stat -c '%a' "$deploy_env_file")"
[[ "$deploy_env_permissions" == 600 ]] \
    || fail "deployment env file must use mode 0600"

[[ -d "$release_base" && ! -L "$release_base" ]] \
    || fail "root-provisioned release base must be a real directory"
[[ "$(/usr/bin/stat -c '%U' "$release_base")" == "root" ]] \
    || fail "release base must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$release_base")" == "root" ]] \
    || fail "release base must be root-owned with root group and mode 0750"
release_base_permissions="$(/usr/bin/stat -c '%a' "$release_base")"
[[ "$release_base_permissions" == 750 ]] \
    || fail "release base must be root-owned with root group and mode 0750"

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
require_root_managed_certbot_configuration_tree "$runtime_root/certbot/conf"
require_root_managed_runtime_tree "$nginx_runtime_root/conf.d"
require_root_managed_runtime_tree "$nginx_runtime_root/snippets"

[[ -d "$release_root" && ! -L "$release_root" ]] \
    || fail "root-provisioned release directory must be a real directory"
[[ "$(/usr/bin/stat -c '%U' "$release_root")" == "root" ]] \
    || fail "release directory must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$release_root")" == "root" ]] \
    || fail "release directory must be root-owned with root group and mode 0750"
release_permissions="$(/usr/bin/stat -c '%a' "$release_root")"
[[ "$release_permissions" == 750 ]] \
    || fail "release directory must be root-owned with root group and mode 0750"

[[ -f "$lock_file" && ! -L "$lock_file" ]] \
    || fail "root-provisioned deployment lock must be a real file"
[[ "$(/usr/bin/stat -c '%U' "$lock_file")" == "root" ]] \
    || fail "deployment lock must be root-owned"
[[ "$(/usr/bin/stat -c '%G' "$lock_file")" == "root" ]] \
    || fail "deployment lock must be root-group-owned"
lock_permissions="$(/usr/bin/stat -c '%a' "$lock_file")"
[[ "$lock_permissions" == 640 ]] \
    || fail "deployment lock must use mode 0640"

sshd_settings="$(/usr/sbin/sshd -T -C "user=$deploy_user,host=localhost,addr=127.0.0.1" 2>/dev/null)" \
    || fail "could not read effective sshd settings"
/usr/bin/grep -Fxq 'permituserenvironment no' <<< "$sshd_settings" \
    || fail "sshd must set PermitUserEnvironment no for the deployment user"
/usr/bin/grep -Fxq 'permituserrc no' <<< "$sshd_settings" \
    || fail "sshd must set PermitUserRC no for the deployment user"

echo "PASS: deployment SSH execution boundary is hardened for $deploy_user"
