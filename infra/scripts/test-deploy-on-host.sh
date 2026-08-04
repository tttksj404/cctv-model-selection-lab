#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
deploy_script="$repo_root/infra/scripts/deploy-on-host.sh"
verified_runner_script="$repo_root/infra/scripts/run-verified-deployment.sh"
source_materializer_script="$repo_root/infra/scripts/materialize-verified-release-source.sh"
host_security_validator_script="$repo_root/infra/scripts/verify-deployment-host-security.sh"
jenkinsfile="$repo_root/infra/Jenkinsfile"
compose_file="$repo_root/infra/compose.deploy.yml"
ingress_compose_file="$repo_root/infra/compose.ingress.yml"
example_env_file="$repo_root/infra/.env.deploy.example"
backend_dockerfile="$repo_root/apps/backend-api/eyesonu/Dockerfile"
backend_dockerignore="$repo_root/apps/backend-api/eyesonu/.dockerignore"
certificate_bootstrap_script="$repo_root/infra/scripts/bootstrap-certificates.sh"
ingress_bootstrap_script="$repo_root/infra/scripts/bootstrap-shared-ingress.sh"
forced_command_script="$repo_root/infra/scripts/eyesonu-deploy-forced-command.sh"
deployment_broker_script="$repo_root/infra/scripts/eyesonu-run-deployment.sh"
release_policy_file="$repo_root/infra/release-policy.env"
deployment_documentation="$repo_root/infra/DEPLOYMENT.md"

# The production SSH command starts the runner with env -i, so this opt-in
# cannot cross the real deployment boundary. It lets this test exercise the
# same fake-tool failure paths on both Git Bash and Linux Jenkins agents.
export EYESONU_DEPLOY_TEST_LOCAL_FIXTURE=1

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker is required to validate Compose interpolation"
command -v git >/dev/null 2>&1 || fail "git is required to validate deployment checkout guards"
git check-ignore -q --no-index 'infra/certbot/conf/accounts/acme-v02.api.letsencrypt.org/metadata.json' \
    || fail "certificate runtime state must stay out of version control"
[[ -f "$verified_runner_script" ]] || fail "verified deployment runner script is missing"
[[ -f "$source_materializer_script" ]] || fail "verified Jenkins source materializer script is missing"
[[ -f "$host_security_validator_script" ]] || fail "deployment host security validator script is missing"
[[ -f "$backend_dockerfile" && -f "$backend_dockerignore" ]] || fail "backend Docker build files are missing"
[[ -f "$certificate_bootstrap_script" && -f "$ingress_bootstrap_script" && -f "$forced_command_script" && -f "$deployment_broker_script" && -f "$release_policy_file" && -f "$deployment_documentation" ]] \
    || fail "deployment bootstrap files are missing"
grep -Fq 'FROM maven:3.9.11-eclipse-temurin-21-alpine AS build' "$backend_dockerfile" \
    || fail "backend image must build from tracked Maven source"
grep -Fq 'COPY pom.xml ./' "$backend_dockerfile" \
    || fail "backend build must include the Maven project descriptor"
grep -Fq 'COPY src ./src' "$backend_dockerfile" \
    || fail "backend build must include tracked application sources"
grep -Fq 'COPY --from=build --chown=app:app /tmp/app.jar app.jar' "$backend_dockerfile" \
    || fail "runtime image must copy the artifact from the source-build stage"
grep -Fq 'ENTRYPOINT ["java", "-jar", "app.jar"]' "$backend_dockerfile" \
    || fail "backend runtime image must retain its Java application entrypoint"
if grep -Eq '^[[:space:]]*COPY[[:space:]].*target/' "$backend_dockerfile"; then
    fail "backend runtime image must not depend on an ignored target directory"
fi
grep -Fq '!pom.xml' "$backend_dockerignore" \
    || fail "backend Docker context must include pom.xml"
grep -Fq '!src/**' "$backend_dockerignore" \
    || fail "backend Docker context must include application sources"
backend_jenkins_stage="$(sed -n "/stage('Backend build and test')/,/stage('Frontend build and test')/p" "$jenkinsfile")"
printf '%s\n' "$backend_jenkins_stage" | grep -Fq 'docker build --tag "$IMAGE" .' \
    || fail "Jenkins must build the backend image from the checked-out source"
grep -Fq 'env -u COMPOSE_PROJECT_NAME "${compose_profile_unsets[@]}" "DEPLOY_RUNTIME_ROOT=$runtime_root" "IMAGE_TAG=$deploy_image_tag" "${inactive_profile_overrides[@]}" docker compose' "$deploy_script" \
    || fail "profile environment isolation must be scoped to the Docker Compose process"
grep -Fq -- '--project-name eyesonu-deploy' "$deploy_script" \
    || fail "profile deployment must pin the Compose project name instead of trusting an env file override"
grep -Fq '${DEPLOY_RUNTIME_ROOT:?Set DEPLOY_RUNTIME_ROOT for shared Nginx runtime}/nginx/conf.d:/etc/nginx/conf.d:ro' "$ingress_compose_file" \
    || fail "root-managed shared Nginx configuration must be mounted from the stable host runtime"
if grep -Eq '^  nginx:' "$compose_file"; then
    fail "profile deployment Compose file must not own the shared ingress service"
fi
grep -Fq 'name: eyesonu-ingress' "$ingress_compose_file" \
    || fail "shared ingress must use its own root-managed Compose stack"
grep -Fq 'external: true' "$ingress_compose_file" \
    || fail "shared ingress must attach to pre-created profile networks"
grep -Fq 'ensure_shared_nginx()' "$deploy_script" \
    || fail "profile deployment must coordinate the shared Nginx service explicitly"
grep -Fq 'shared Nginx must be running and healthy' "$deploy_script" \
    || fail "profile deployment must reject an unhealthy shared Nginx"
grep -Fq 'verify_shared_nginx_mount "$nginx_container_id"' "$deploy_script" \
    || fail "profile deployment must verify shared Nginx runtime mounts"
grep -Fq 'root-managed shared Nginx is not running; profile deployment must not create ingress' "$deploy_script" \
    || fail "profile deployment must refuse to create shared ingress"
grep -Fq 'verify_shared_nginx_networks' "$deploy_script" \
    || fail "profile deployment must verify shared ingress network attachment"
grep -Fq 'verify_shared_nginx_ports' "$deploy_script" \
    || fail "profile deployment must verify shared ingress port bindings"
grep -Fq 'verify_shared_nginx_upstreams' "$deploy_script" \
    || fail "profile deployment must verify selected profile upstream reachability"
grep -Fq 'up -d --no-build --pull never --wait --wait-timeout 180' "$deploy_script" \
    || fail "profile deployment must use already verified local image artifacts without rebuilding"
grep -Fq 'load_release_image_manifest' "$deploy_script" \
    || fail "profile deployment must load the immutable release image manifest"
grep -Fq 'DEPLOY_STOP_ONLY' "$deploy_script" \
    || fail "deployment must support stopping an unmarked first-release candidate"
grep -Fq 'profile_service_list="$(compose --profile "$profile" config --services)"' "$deploy_script" \
    || fail "stop-only deployment must discover every enabled profile service"
grep -Fq '"${profile_services[@]}"' "$deploy_script" \
    || fail "stop-only deployment must stop every discovered profile service"
if grep -Fq 'nginx -s reload' "$deploy_script"; then
    fail "profile deployment must not reload the shared Nginx configuration from a candidate release"
fi
grep -Fq 'runtime_root="${DEPLOY_RUNTIME_ROOT:-$repo_root/infra}"' "$certificate_bootstrap_script" \
    || fail "certificate bootstrap must write only to the selected shared runtime root"
grep -Fq '/var/lib/eyesonu-deploy/runtime/nginx/conf.d/default.conf' "$deployment_documentation" \
    || fail "deployment documentation must provision the stable shared Nginx configuration"
grep -Fq 'expand/contract' "$deployment_documentation" \
    || fail "deployment documentation must require compatible database migration rollback policy"
grep -Fq 'AUTO_ROLLBACK_SCHEMA_COMPATIBLE=0' "$deployment_documentation" \
    || fail "deployment documentation must explain the fail-closed default for schema-incompatible rollback"
grep -Fq 'root-owned broker' "$deployment_documentation" \
    || fail "deployment documentation must describe the restricted SSH broker boundary"
if grep -Fq 'SSH 표준입력으로 한 번만 전달' "$deployment_documentation" || grep -Fq '공유 Nginx는 없을 때만 시작' "$deployment_documentation"; then
    fail "deployment documentation must not retain stale streamed-runner or profile-managed ingress instructions"
fi
if grep -Fq 'Resolve branch' "$deployment_documentation"; then
    fail "deployment documentation must describe the pre-agent authorization gate by its current name"
fi
grep -Fq 'compose_profile_unsets+=("-u" "$variable_name")' "$deploy_script" \
    || fail "deployment profile variables must be removed from the inherited shell environment"
grep -Fq 'require_secure_deploy_env_file "$deploy_env_file"' "$deploy_script" \
    || fail "deployment must validate the protected env file contract before Compose interpolation"
grep -Fq 'deployment env file must not be a symlink' "$deploy_script" \
    || fail "deployment must reject a symlinked env file"
grep -Fq 'root:root with mode 0600' "$deploy_script" \
    || fail "deployment must keep env secrets readable only by the root deployment broker outside the test fixture"
grep -Fq 'env.gitlabBranch' "$jenkinsfile" \
    || fail "Jenkins must read the GitLab push branch before checkout"
grep -Fq "eventType != 'PUSH'" "$jenkinsfile" \
    || fail "Jenkins must reject non-push deployment events"
grep -Fq 'GitLab PUSH event commit must be a full lowercase object ID' "$jenkinsfile" \
    || fail "Jenkins must require a full push event commit"
grep -Fq "stage('Build immutable deployment images')" "$jenkinsfile" \
    || fail "Jenkins must build immutable deployment image artifacts"
grep -Fq 'docker tag "eyesonu/backend-dev:$release_tag" "eyesonu/backend-master:$release_tag"' "$jenkinsfile" \
    || fail "Jenkins must retain profile-specific immutable backend image tags"
grep -Fq '"eyesonu-deploy '\''$DEPLOY_PROFILE'\'' '\''$GIT_COMMIT'\''"' "$jenkinsfile" \
    || fail "Jenkins must invoke only the restricted deployment SSH protocol"
if grep -Fq 'trusted_runner=' "$jenkinsfile" || grep -Fq '< "$trusted_runner"' "$jenkinsfile"; then
    fail "Jenkins must not stream executable shell source through the deployment SSH key"
fi
if grep -Fq 'DEPLOY_HOST_ROOT' "$jenkinsfile" || grep -Fq 'DEPLOY_HOST_ENV_FILE' "$jenkinsfile"; then
    fail "Jenkins must not expose host filesystem paths as deploy-time parameters"
fi
if grep -Fq "tokenize('/').last()" "$jenkinsfile" \
    || grep -Fq 'resolve-deployment-profile.sh' "$jenkinsfile"; then
    fail "Jenkins must not authorize deployment through a checked-out branch resolver or suffix"
fi
grep -Fq 'def deployProfilesByReference = [' "$jenkinsfile" \
    || fail "Jenkins must use the protected deployment job's explicit branch allowlist"
grep -Fq 'agent none' "$jenkinsfile" \
    || fail "Jenkins must not allocate a default privileged agent before event authorization"
if grep -Fq 'agent any' "$jenkinsfile"; then
    fail "Jenkins must not allow this protected job to run on an arbitrary agent"
fi
grep -Fq "stage('Authorize deployment event')" "$jenkinsfile" \
    || fail "Jenkins must have a controller-side deployment-event authorization stage"
grep -Fq "stage('Verified build and deployment')" "$jenkinsfile" \
    || fail "Jenkins must group privileged work behind the authorization stage"
grep -Fq "label 'eyesonu-trusted-deploy'" "$jenkinsfile" \
    || fail "Jenkins must use the dedicated trusted deployment agent label"
authorization_stage_line="$(grep -n -m1 "stage('Authorize deployment event')" "$jenkinsfile" | cut -d: -f1)"
checkout_stage_line="$(grep -n -m1 "stage('Checkout protected pipeline')" "$jenkinsfile" | cut -d: -f1)"
[[ -n "$authorization_stage_line" && -n "$checkout_stage_line" && "$authorization_stage_line" -lt "$checkout_stage_line" ]] \
    || fail "Jenkins must authorize the event before allocating the protected checkout stage"
for allowed_reference in \
    "'dev': 'dev'" \
    "'master': 'master'" \
    "'origin/dev': 'dev'" \
    "'origin/master': 'master'" \
    "'refs/heads/dev': 'dev'" \
    "'refs/heads/master': 'master'" \
    "'refs/remotes/origin/dev': 'dev'" \
    "'refs/remotes/origin/master': 'master'"; do
    grep -Fq "$allowed_reference" "$jenkinsfile" \
        || fail "Jenkins deployment branch allowlist is missing $allowed_reference"
done
if grep -Fq "'*/dev'" "$jenkinsfile" || grep -Fq "'*/master'" "$jenkinsfile"; then
    fail "Jenkins deployment branch allowlist must not accept wildcard branch patterns"
fi
grep -Fq 'def checkoutState = checkout scm' "$jenkinsfile" \
    || fail "Jenkins must capture the protected pipeline checkout result before resolving a release"
grep -Fq 'env.PIPELINE_SOURCE_COMMIT = pipelineSourceCommit' "$jenkinsfile" \
    || fail "Jenkins must preserve the protected pipeline commit separately from the release commit"
grep -Fq 'Protected pipeline source commit is not a full lowercase object ID' "$jenkinsfile" \
    || fail "Jenkins must reject an unverified protected pipeline commit"
grep -Fq '"$pipeline_commit:infra/scripts/materialize-verified-release-source.sh"' "$jenkinsfile" \
    || fail "Jenkins must extract the materializer blob from the protected pipeline commit"
grep -Fq '/bin/bash --noprofile --norc "$trusted_materializer"' "$jenkinsfile" \
    || fail "Jenkins must run only the trusted temporary materializer copy"
if grep -Fq '/bin/bash --noprofile --norc infra/scripts/materialize-verified-release-source.sh' "$jenkinsfile"; then
    fail "Jenkins must not execute a materializer directly from the mutable workspace"
fi
grep -Fq 'HOME="$PWD"' "$jenkinsfile" \
    || fail "Jenkins must provide only the checked-out workspace as the materializer home directory"
if grep -Fq 'git worktree add' "$jenkinsfile" \
    || grep -Fq 'git fetch --no-tags origin' "$jenkinsfile"; then
    fail "Jenkins must not checkout an unisolated release worktree or fetch through mutable checkout state"
fi
grep -Fq 'release_commit="$(git_safely -C "$checkout_root" rev-parse --verify "refs/remotes/origin/$profile^{commit}")"' "$source_materializer_script" \
    || fail "source materializer must resolve the full commit for the canonical release ref"
grep -Fq '"$release_commit" != "$event_commit"' "$source_materializer_script" \
    || fail "source materializer must reject an event SHA that does not match the canonical release ref"
grep -Fq 'git_safely clone --shared --no-checkout --template="$empty_template"' "$source_materializer_script" \
    || fail "source materializer must create an isolated no-checkout repository"
grep -Fq 'git_safely -C "$pending_repository" archive --format=tar "$release_commit"' "$source_materializer_script" \
    || fail "source materializer must archive the selected release commit from the isolated repository"
grep -Fq '[[ ! -e "$pending_tree/.git" ]]' "$source_materializer_script" \
    || fail "source materializer must publish a Git-free release source tree"
grep -Fq 'rm -f -- "$release_commit_file"' "$source_materializer_script" \
    || fail "source materializer must remove a retained release commit marker before publishing"
grep -Fq '[[ ! -L "$release_commit_file" ]]' "$source_materializer_script" \
    || fail "source materializer must reject a redirected release commit marker"
grep -Fq 'env.GIT_COMMIT = releaseCommit' "$jenkinsfile" \
    || fail "Jenkins must use the isolated release SHA for runner extraction and deployment"
grep -Fq 'dir(env.BUILD_SOURCE_DIR)' "$jenkinsfile" \
    || fail "Jenkins must validate the resolved release source tree"
grep -Fq 'dir("${env.BUILD_SOURCE_DIR}/apps/backend-api/eyesonu")' "$jenkinsfile" \
    || fail "Jenkins must build the resolved release source tree"
[[ "$(grep -Ec '^[[:space:]]*ssh -o StrictHostKeyChecking=yes' "$jenkinsfile")" -eq 1 ]] \
    || fail "Jenkins must verify and deploy in one SSH session"
grep -Fq 'flock -n 9' "$verified_runner_script" \
    || fail "verified deployment runner must hold a non-blocking deployment lock"
grep -Fq 'archive --format=tar "$expected_commit"' "$verified_runner_script" \
    || fail "verified deployment runner must materialize a release directly from the immutable commit tree"
grep -Fq 'env -i "${git_environment[@]}" "$git_bin"' "$verified_runner_script" \
    || fail "verified deployment runner must isolate every Git command from inherited configuration"
grep -Fq "printf '[safe]\\n\\tdirectory = %s\\n' \"\$checkout_root\" > \"\$safe_git_config\"" "$verified_runner_script" \
    || fail "verified deployment runner must allow only the canonical cross-user checkout"
grep -Fq '"GIT_CONFIG_GLOBAL=$safe_git_config"' "$verified_runner_script" \
    || fail "verified deployment runner must use the private safe-directory Git configuration"
grep -Fq 'GIT_CONFIG_COUNT=0' "$verified_runner_script" \
    || fail "verified deployment runner must discard inherited Git command-scope configuration"
grep -Fq -- '--no-replace-objects' "$verified_runner_script" \
    || fail "verified deployment runner must ignore replace refs at the trusted-commit boundary"
grep -Fq 'mktemp -d "$release_root/.pending-${expected_commit}.XXXXXX"' "$verified_runner_script" \
    || fail "verified deployment runner must build releases in a private pending directory"
grep -Fq 'mv -T -- "$pending_tree" "$deployment_tree"' "$verified_runner_script" \
    || fail "verified deployment runner must atomically publish a complete release"
grep -Fq 'active_release_file="$release_root/.active-release-$profile"' "$verified_runner_script" \
    || fail "verified deployment runner must track a separate active release for each deployment profile"
grep -Fq 'load_previous_release' "$verified_runner_script" \
    || fail "verified deployment runner must load the last active release with its digest"
grep -Fq 'verify_previous_release_is_still_active' "$verified_runner_script" \
    || fail "verified deployment runner must revalidate the active release immediately before rollback"
grep -Fq 'preflight_active_marker_write' "$verified_runner_script" \
    || fail "verified deployment runner must verify marker writability before service mutation"
grep -Fq 'publish_active_release' "$verified_runner_script" \
    || fail "verified deployment runner must advance the active release marker only after deployment succeeds"
grep -Fq 'chmod 0640 "$active_release_temp"' "$verified_runner_script" \
    || fail "active release markers must not be group-writable after the root broker took ownership"
grep -Fq 'release_tree_digest()' "$verified_runner_script" \
    || fail "verified deployment runner must verify retained release content before rollback"
grep -Fq 'active release content digest no longer matches its verified marker' "$verified_runner_script" \
    || fail "verified deployment runner must reject a modified retained release"
grep -Fq 'rollback_after_marker_publication_failure' "$verified_runner_script" \
    || fail "verified deployment runner must recover if active-marker publication fails"
grep -Fq 'DEPLOY_ROLLBACK_ONLY=1' "$verified_runner_script" \
    || fail "verified deployment runner must request an explicit rollback after marker publication failure"
grep -Fq 'DEPLOY_PREVIOUS_RELEASE="$previous_release"' "$verified_runner_script" \
    || fail "verified deployment runner must provide the previous release to the deploy script"
runner_cleanup_line="$(grep -n -m1 '^trap cleanup EXIT$' "$verified_runner_script" | cut -d: -f1)"
runner_first_temp_line="$(grep -n -m1 '^empty_home="$(mktemp -d' "$verified_runner_script" | cut -d: -f1)"
[[ -n "$runner_cleanup_line" && -n "$runner_first_temp_line" && "$runner_cleanup_line" -lt "$runner_first_temp_line" ]] \
    || fail "verified deployment runner must register cleanup before its first temporary directory"
materializer_cleanup_line="$(grep -n -m1 '^trap cleanup EXIT$' "$source_materializer_script" | cut -d: -f1)"
materializer_first_temp_line="$(grep -n -m1 '^empty_home="$(mktemp -d' "$source_materializer_script" | cut -d: -f1)"
[[ -n "$materializer_cleanup_line" && -n "$materializer_first_temp_line" && "$materializer_cleanup_line" -lt "$materializer_first_temp_line" ]] \
    || fail "source materializer must register cleanup before its first temporary directory"
jenkins_cleanup_line="$(grep -n -m1 'trap cleanup_trusted_bootstrap EXIT' "$jenkinsfile" | cut -d: -f1)"
jenkins_first_temp_line="$(grep -n -m1 'trusted_home="$(mktemp -d)"' "$jenkinsfile" | cut -d: -f1)"
[[ -n "$jenkins_cleanup_line" && -n "$jenkins_first_temp_line" && "$jenkins_cleanup_line" -lt "$jenkins_first_temp_line" ]] \
    || fail "Jenkins must register trusted-bootstrap cleanup before creating its temporary home"
grep -Fq '"$release_root"/.git-home.*/gitconfig' "$verified_runner_script" \
    || fail "verified deployment runner must clean the exact Git-home mktemp path pattern"
grep -Fq '"$checkout_root"/.verified-git-home.*/gitconfig' "$source_materializer_script" \
    || fail "source materializer must clean the exact Git-home mktemp path pattern"
grep -Fq '[[ ! -e "$pending_tree/.git" ]]' "$verified_runner_script" \
    || fail "verified deployment runner must publish Git-free releases"
grep -Fq 'runtime_root="/var/lib/eyesonu-deploy/runtime"' "$verified_runner_script" \
    || fail "verified deployment runner must use root-provisioned host runtime state in production"
grep -Fq 'DEPLOY_COMPOSE="$deployment_tree/infra/compose.deploy.yml"' "$verified_runner_script" \
    || fail "verified deployment runner must not inherit an arbitrary Compose path"
grep -Fq 'GIT_CONFIG_COUNT=0' "$jenkinsfile" \
    || fail "Jenkins must isolate protected materializer extraction from inherited Git configuration"
grep -Fq 'GIT_NO_REPLACE_OBJECTS=1' "$jenkinsfile" \
    || fail "Jenkins must ignore replace refs while extracting the protected materializer"
grep -Fq 'core.attributesFile=/dev/null' "$jenkinsfile" \
    || fail "Jenkins must ignore checkout attributes while extracting the protected materializer"
grep -Fq 'GIT_COMMIT must be a full lowercase object ID' "$jenkinsfile" \
    || fail "Jenkins must validate the commit before it becomes part of the restricted remote protocol"
grep -Fq 'DEPLOY_PROFILE must be dev or master' "$jenkinsfile" \
    || fail "Jenkins must validate the deployment profile before it becomes part of the remote command"
grep -Fq 'eyesonu-deploy' "$forced_command_script" \
    || fail "deployment forced command must accept only the deployment protocol"
grep -Fq 'SSH_ORIGINAL_COMMAND' "$forced_command_script" \
    || fail "deployment forced command must validate the original SSH command"
grep -Fq '/usr/bin/sudo -n /usr/local/libexec/eyesonu-run-deployment' "$forced_command_script" \
    || fail "deployment forced command must enter the root-owned deployment broker only"
grep -Fq 'export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' "$forced_command_script" \
    || fail "deployment forced command must pin a trusted executable path"
grep -Fq 'umask 077' "$forced_command_script" \
    || fail "deployment forced command must not create permissive transient files"
grep -Fq 'canonical_ref="refs/remotes/origin/$profile"' "$deployment_broker_script" \
    || fail "deployment broker must bind a requested commit to the canonical protected profile ref"
grep -Fq '"$canonical_commit" == "$expected_commit"' "$deployment_broker_script" \
    || fail "deployment broker must reject commits outside the current protected profile ref"
grep -Fq 'show "$expected_commit:infra/scripts/run-verified-deployment.sh" > "$runner"' "$deployment_broker_script" \
    || fail "deployment broker must extract the runner from the canonical immutable commit"
grep -Fq 'export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' "$deployment_broker_script" \
    || fail "deployment broker must pin a trusted executable path"
grep -Fq 'umask 077' "$deployment_broker_script" \
    || fail "deployment broker must not create permissive transient files"
if grep -Fq 'EYESONU_DEPLOY_TEST_LOCAL_FIXTURE' "$jenkinsfile"; then
    fail "Jenkins must never pass the local regression opt-in across SSH"
fi
grep -Fq "DEPLOY_SSH_USER = 'eyesonu-deploy'" "$jenkinsfile" \
    || fail "Jenkins must use the dedicated deployment SSH account"
grep -Fq 'DEPLOY_SSH_USER must be the dedicated eyesonu-deploy account' "$jenkinsfile" \
    || fail "Jenkins must reject a non-dedicated deployment SSH account"
grep -Fq 'security_validator="/usr/local/sbin/eyesonu-verify-deployment-host-security"' "$verified_runner_script" \
    || fail "verified runner must use the root-owned host security validator"
grep -Fq 'verified deployment runner must be root through the deployment broker' "$verified_runner_script" \
    || fail "verified runner must refuse a direct non-root host invocation"
grep -Fq '"$security_validator" "$deploy_user" "$deploy_env_file"' "$verified_runner_script" \
    || fail "verified runner must invoke the host validator directly after entering the root broker"
if grep -Fq '[[ -n "$msystem_value" ]] && return' "$verified_runner_script"; then
    fail "host security gate must not be bypassable through an inherited MSYSTEM value"
fi
grep -Fq 'host_kernel="$(/usr/bin/uname -s' "$verified_runner_script" \
    || fail "verified runner must detect the local Windows fixture from the kernel"
grep -Fq 'release_root="/var/lib/eyesonu-deploy/releases"' "$verified_runner_script" \
    || fail "production release storage must use the root-provisioned location"
grep -Fq 'lock_file="/var/lib/eyesonu-deploy/deployment.lock"' "$verified_runner_script" \
    || fail "production locking must use the root-provisioned lock file"
grep -Fq 'exec 9<"$lock_file"' "$verified_runner_script" \
    || fail "production locking must avoid truncating the lock path"
grep -Fq 'PermitUserEnvironment no' "$host_security_validator_script" \
    || fail "host security validator must require PermitUserEnvironment no"
grep -Fq 'PermitUserRC no' "$host_security_validator_script" \
    || fail "host security validator must require PermitUserRC no"
grep -Fq '"$deploy_shell" == "/bin/sh"' "$host_security_validator_script" \
    || fail "host security validator must require a non-Bash deployment shell"
grep -Fq '"$(/usr/bin/id -u)" -eq 0' "$host_security_validator_script" \
    || fail "host security validator must require root execution"
grep -Fq 'release_root="$release_base/releases"' "$host_security_validator_script" \
    || fail "host security validator must validate the root-provisioned release root"
grep -Fq 'runtime_root="$release_base/runtime"' "$host_security_validator_script" \
    || fail "host security validator must validate the root-provisioned shared runtime"
grep -Fq 'require_root_managed_runtime_directory' "$host_security_validator_script" \
    || fail "host security validator must reject writable or redirected shared runtime directories"
grep -Fq 'require_root_managed_runtime_tree()' "$host_security_validator_script" \
    || fail "host security validator must validate every shared Nginx runtime entry"
grep -Fq '/usr/bin/find -P "$root" -xdev -print0' "$host_security_validator_script" \
    || fail "host security validator must enumerate runtime trees without following links"
grep -Fq 'require_root_managed_runtime_tree "$runtime_root/certbot/www"' "$host_security_validator_script" \
    || fail "host security validator must validate the mounted certificate webroot tree"
grep -Fq 'require_root_managed_certbot_configuration_tree "$runtime_root/certbot/conf"' "$host_security_validator_script" \
    || fail "host security validator must validate the mounted certificate configuration tree with Certbot live-link rules"
grep -Fq 'require_root_managed_certbot_live_link' "$host_security_validator_script" \
    || fail "host security validator must permit only safely resolved Certbot lineage links"
grep -Fq 'certificate live symlink escapes its lineage archive' "$host_security_validator_script" \
    || fail "host security validator must reject Certbot live links that escape the matching archive"
grep -Fq 'deployment account must not have direct Docker Engine group access' "$host_security_validator_script" \
    || fail "host security validator must reject direct Docker Engine access for the SSH account"
grep -Fq 'deployment SSH key must use the restricted forced command' "$host_security_validator_script" \
    || fail "host security validator must require a restricted forced command"
grep -Fq 'require_root_managed_runtime_tree "$nginx_runtime_root/conf.d"' "$host_security_validator_script" \
    || fail "host security validator must validate the mounted Nginx configuration tree"
grep -Fq 'require_root_managed_runtime_tree "$nginx_runtime_root/snippets"' "$host_security_validator_script" \
    || fail "host security validator must validate the mounted Nginx snippet tree"
grep -Fq 'require_root_managed_runtime_file "$nginx_runtime_root/conf.d/default.conf"' "$host_security_validator_script" \
    || fail "host security validator must validate the stable Nginx configuration file"
grep -Fq 'require_root_managed_runtime_file "$nginx_runtime_root/snippets/ssl-params.conf"' "$host_security_validator_script" \
    || fail "host security validator must validate the stable Nginx SSL-parameter file"
grep -Fq 'lock_file="$release_base/deployment.lock"' "$host_security_validator_script" \
    || fail "host security validator must validate the root-provisioned lock"
grep -Fq 'release base must be root-owned with root group and mode 0750' "$host_security_validator_script" \
    || fail "host security validator must lock the release base to root after introducing the root deployment broker"
grep -Fq 'release directory must be root-owned with root group and mode 0750' "$host_security_validator_script" \
    || fail "host security validator must prevent the SSH account from modifying retained releases"
grep -Fq 'deployment lock must use mode 0640' "$host_security_validator_script" \
    || fail "host security validator must keep the deployment lock root-managed"
grep -Fq 'trusted deployment checkout must not be group/world writable' "$host_security_validator_script" \
    || fail "host security validator must reject a writable deployment checkout"
grep -Fq 'deployment env file path must be absolute' "$host_security_validator_script" \
    || fail "host security validator must require an absolute deployment env file path"
grep -Fq 'deployment env directory must use mode 0700' "$host_security_validator_script" \
    || fail "host security validator must validate the deployment env directory permissions"
grep -Fq 'deployment env file must use mode 0600' "$host_security_validator_script" \
    || fail "host security validator must validate the deployment env file permissions"
grep -Fq 'deployment broker environment file must be root-owned with mode 0600' "$deployment_broker_script" \
    || fail "deployment broker must independently enforce its root-only env boundary"
grep -Fq 'deployment broker checkout must not be writable by the deployment account or its groups' "$deployment_broker_script" \
    || fail "deployment broker must independently enforce its trusted checkout boundary"
grep -Fq 'run_release "$rollback_root" "$rollback_compose_file" 0' "$deploy_script" \
    || fail "rollback-only mode must restart the previously verified release"
grep -Fq 'rollback_only="${DEPLOY_ROLLBACK_ONLY:-}"' "$deploy_script" \
    || fail "deployment must support an explicit marker-publication rollback mode"
grep -Fq 'stop_release "$deploy_root" "$compose_file"' "$deploy_script" \
    || fail "rollback-only mode must stop every failed-candidate profile service before restoring a previous release"
grep -Fq '[[ -n "$rollback_root" ]] || return 0' "$deploy_script" \
    || fail "deployment must treat the first release as a valid no-rollback state"
grep -Fq 'compose --profile "$profile" up -d --no-build --pull never --wait --wait-timeout 180' "$deploy_script" \
    || fail "deployment must wait for health checks using immutable local images before it can mark a release active"
grep -Fq '|| exit $?' "$deploy_script" \
    || fail "rollback flow must propagate a failed Compose action even when called from a conditional"

real_docker="$(command -v docker)"
real_tar="$(command -v tar)"
real_mv="$(command -v mv)"
real_rmdir="$(command -v rmdir)"
real_mktemp="$(command -v mktemp)"
export REAL_MV
export REAL_RMDIR
export REAL_MKTEMP
temp_root="$(mktemp -d)"
trap 'rm -rf -- "$temp_root"' EXIT

fake_bin="$temp_root/bin"
captured_env_path_file="$temp_root/captured-env-path"
captured_project_name_file="$temp_root/captured-project-name"
placeholder_calls_file="$temp_root/placeholder-calls"
compose_commands_file="$temp_root/compose-commands"
docker_engine_commands_file="$temp_root/docker-engine-commands"
docker_config_log_file="$temp_root/docker-compose-config.log"
missing_master_env_file="$temp_root/missing-master.env"
missing_master_no_newline_env_file="$temp_root/missing-master-no-newline.env"
empty_master_env_file="$temp_root/empty-master.env"
missing_dev_env_file="$temp_root/missing-dev.env"
dev_only_env_file="$temp_root/dev-only.env"
master_only_env_file="$temp_root/master-only.env"
runtime_root="$temp_root/runtime"
mkdir -p "$fake_bin"
mkdir -p "$runtime_root/certbot/www" "$runtime_root/certbot/conf" \
    "$runtime_root/nginx/conf.d" "$runtime_root/nginx/snippets"
printf 'events {}\nhttp { server { listen 80; } }\n' > "$runtime_root/nginx/conf.d/default.conf"
printf 'ssl_protocols TLSv1.2 TLSv1.3;\n' > "$runtime_root/nginx/snippets/ssl-params.conf"

awk '!/^MASTER_AI_WORKER_API_KEY=/' "$example_env_file" > "$missing_master_env_file"
awk '{ if ($0 ~ /^MASTER_AI_WORKER_API_KEY=/) print "MASTER_AI_WORKER_API_KEY="; else print }' "$example_env_file" > "$empty_master_env_file"
awk '!/^DEV_AI_WORKER_API_KEY=/' "$example_env_file" > "$missing_dev_env_file"
awk '!/^MASTER_/' "$example_env_file" > "$dev_only_env_file"
awk '!/^DEV_/' "$example_env_file" > "$master_only_env_file"
awk 'NR > 1 { printf "\n" } { printf "%s", $0 }' "$missing_master_env_file" > "$missing_master_no_newline_env_file"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf '%s\n' 'if [[ "${1:-}" != "compose" && -n "${DEPLOY_TEST_DOCKER_ENGINE_COMMANDS:-}" ]]; then'
    printf '%s\n' '    printf "%s\\n" "$*" >> "$DEPLOY_TEST_DOCKER_ENGINE_COMMANDS"'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ "${1:-}" == "ps" ]]; then'
    printf '%s\n' '    [[ "${DEPLOY_TEST_NGINX_MISSING:-}" != "1" ]] && printf "fake-nginx-container-id\\n"'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ "${1:-}" == "exec" ]]; then'
    printf '%s\n' '    if [[ "${DEPLOY_TEST_NGINX_UPSTREAM_FAIL:-}" == "1" && " $* " == *" wget "* ]]; then exit 94; fi'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ "${1:-}" == "image" && "${2:-}" == "inspect" ]]; then'
    printf '%s\n' '    image_ref="${!#}"'
    printf '%s\n' '    printf "sha256:%s\\n" "$(printf "%s" "$image_ref" | sha256sum | cut -d " " -f1)"'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ "${1:-}" == "inspect" ]]; then'
    printf '%s\n' '    args=("$@")'
    printf '%s\n' '    format=""'
    printf '%s\n' '    for ((index = 0; index < ${#args[@]}; index++)); do'
    printf '%s\n' '        if [[ "${args[$index]}" == "--format" ]]; then'
    printf '%s\n' '            format="${args[$((index + 1))]}"'
    printf '%s\n' '        fi'
    printf '%s\n' '    done'
    printf '%s\n' '    if [[ "$format" == *".State.Status"* ]]; then'
    printf '%s\n' '        printf "%s\n" "${DEPLOY_TEST_NGINX_STATE:-running|healthy}"'
    printf '%s\n' '        exit 0'
    printf '%s\n' '    fi'
    printf '%s\n' '    case "$format" in'
    printf '%s\n' '        *".NetworkSettings.Networks"*) printf "eyesonu-dev eyesonu-prod \\n" ;;'
    printf '%s\n' '        *".HostConfig.PortBindings"*) printf "{\\\"80/tcp\\\":[{\\\"HostIp\\\":\\\"\\\",\\\"HostPort\\\":\\\"80\\\"}],\\\"443/tcp\\\":[{\\\"HostIp\\\":\\\"\\\",\\\"HostPort\\\":\\\"443\\\"}]}\\n" ;;'
    printf '%s\n' '        *"/etc/nginx/conf.d"*) source="$DEPLOY_RUNTIME_ROOT/nginx/conf.d"; [[ "${DEPLOY_TEST_NGINX_MOUNT_MISMATCH:-}" == "1" ]] && source="$DEPLOY_RUNTIME_ROOT/unexpected"; printf "bind|false|%s|/etc/nginx/conf.d\\n" "$source" ;;'
    printf '%s\n' '        *"/etc/nginx/snippets"*) source="$DEPLOY_RUNTIME_ROOT/nginx/snippets"; printf "bind|false|%s|/etc/nginx/snippets\\n" "$source" ;;'
    printf '%s\n' '        *"/var/www/certbot"*) source="$DEPLOY_RUNTIME_ROOT/certbot/www"; printf "bind|false|%s|/var/www/certbot\\n" "$source" ;;'
    printf '%s\n' '        *"/etc/letsencrypt"*) source="$DEPLOY_RUNTIME_ROOT/certbot/conf"; printf "bind|false|%s|/etc/letsencrypt\\n" "$source" ;;'
    printf '%s\n' '        *) printf "fake docker inspect format unsupported: %s\n" "$format" >&2; exit 92 ;;'
    printf '%s\n' '    esac'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ "${1:-}" != "compose" ]]; then'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'shift'
    printf '%s\n' 'args=("$@")'
    printf '%s\n' 'if [[ -v COMPOSE_PROJECT_NAME ]]; then'
    printf '%s\n' '    printf "set\\n" >> "$DEPLOY_TEST_CAPTURED_PROJECT_NAME"'
    printf '%s\n' 'else'
    printf '%s\n' '    printf "unset\\n" >> "$DEPLOY_TEST_CAPTURED_PROJECT_NAME"'
    printf '%s\n' 'fi'
    printf '%s\n' 'env_file=""'
    printf '%s\n' 'compose_file=""'
    printf '%s\n' 'project_name=""'
    printf '%s\n' 'for ((index = 0; index < ${#args[@]}; index++)); do'
    printf '%s\n' '    if [[ "${args[$index]}" == "--project-name" ]]; then'
    printf '%s\n' '        project_name="${args[$((index + 1))]}"'
    printf '%s\n' '    fi'
    printf '%s\n' '    if [[ "${args[$index]}" == "--env-file" ]]; then'
    printf '%s\n' '        env_file="${args[$((index + 1))]}"'
    printf '%s\n' '    fi'
    printf '%s\n' '    if [[ "${args[$index]}" == "-f" ]]; then'
    printf '%s\n' '        compose_file="${args[$((index + 1))]}"'
    printf '%s\n' '    fi'
    printf '%s\n' 'done'
    printf '%s\n' '[[ "$project_name" == "eyesonu-deploy" ]] || { printf "fake docker project-name mismatch: %s\\n" "$project_name" >&2; exit 91; }'
    printf '%s\n' '[[ -n "$env_file" && "$env_file" == "$DEPLOY_TEST_EXPECTED_ENV_FILE" ]] || { printf "fake docker env-file mismatch: expected=%s actual=%s\\n" "$DEPLOY_TEST_EXPECTED_ENV_FILE" "$env_file" >&2; exit 91; }'
    printf '%s\n' 'printf "%s\n" "$env_file" >> "$DEPLOY_TEST_CAPTURED_ENV_PATH"'
    printf '%s\n' 'printf "%q " "${args[@]}" >> "$DEPLOY_TEST_COMPOSE_COMMANDS"'
    printf '%s\n' 'printf "\n" >> "$DEPLOY_TEST_COMPOSE_COMMANDS"'
    printf '%s\n' 'if [[ -n "${DEPLOY_TEST_EXPECTED_PLACEHOLDER:-}" ]]; then'
    printf '%s\n' '    case "$DEPLOY_TEST_EXPECTED_PLACEHOLDER" in'
    printf '%s\n' '        MASTER_AI_WORKER_API_KEY) placeholder_value="${MASTER_AI_WORKER_API_KEY:-}" ;;'
    printf '%s\n' '        DEV_AI_WORKER_API_KEY) placeholder_value="${DEV_AI_WORKER_API_KEY:-}" ;;'
    printf '%s\n' '        *) exit 92 ;;'
    printf '%s\n' '    esac'
    printf '%s\n' '    if [[ "$placeholder_value" == "__inactive_profile_placeholder__" ]]; then'
    printf '%s\n' '        printf "yes\n" >> "$DEPLOY_TEST_PLACEHOLDER_CALLS"'
    printf '%s\n' '    else'
    printf '%s\n' '        printf "no\n" >> "$DEPLOY_TEST_PLACEHOLDER_CALLS"'
    printf '%s\n' '    fi'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ " ${args[*]} " == *" config --services "* ]]; then'
    printf '%s\n' '    config_log="${DEPLOY_TEST_DOCKER_CONFIG_LOG:?}"'
    printf '%s\n' '    if ! "$REAL_DOCKER" compose "${args[@]}" > "$config_log" 2>&1; then'
    printf '%s\n' '        tail -n 40 "$config_log" >&2'
    printf '%s\n' '        exit 93'
    printf '%s\n' '    fi'
    printf '%s\n' '    cat "$config_log"'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ " ${args[*]} " == *" config "* ]]; then'
    printf '%s\n' '    config_log="${DEPLOY_TEST_DOCKER_CONFIG_LOG:?}"'
    printf '%s\n' '    if ! "$REAL_DOCKER" compose "${args[@]}" > "$config_log" 2>&1; then'
    printf '%s\n' '        tail -n 40 "$config_log" >&2'
    printf '%s\n' '        exit 93'
    printf '%s\n' '    fi'
    printf '%s\n' '    config_name="$(sed -n "1p" "$config_log")"'
    printf '%s\n' '    [[ "$config_name" == "name: eyesonu-deploy" ]] || { printf "fake docker config name mismatch: %s\\n" "$config_name" >&2; exit 93; }'
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' 'if [[ -n "${DEPLOY_TEST_FAIL_COMPOSE_FILE:-}" && "$compose_file" == "$DEPLOY_TEST_FAIL_COMPOSE_FILE" && " ${args[*]} " == *" up "* ]]; then'
    printf '%s\n' '    printf "fake docker induced current-release failure: %s\\n" "$compose_file" >&2'
    printf '%s\n' '    exit 94'
    printf '%s\n' 'fi'
    printf '%s\n' 'exit 0'
} > "$fake_bin/docker"
chmod +x "$fake_bin/docker"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf '%s\n' 'last_argument="${!#}"'
    printf '%s\n' 'if [[ "${DEPLOY_TEST_FAIL_ACTIVE_MARKER:-}" == "1" && "$last_argument" == */.active-release-* ]]; then'
    printf '%s\n' '    printf "fake mv induced active-marker publication failure: %s\\n" "$last_argument" >&2'
    printf '%s\n' '    exit 95'
    printf '%s\n' 'fi'
    printf '%s\n' 'exec "${REAL_MV:-/usr/bin/mv}" "$@"'
} > "$fake_bin/mv"
chmod +x "$fake_bin/mv"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf '%s\n' 'last_argument="${!#}"'
    printf '%s\n' 'if [[ "${DEPLOY_TEST_RMDIR_FAIL:-}" == "1" && "$last_argument" == */.git-home.* ]]; then'
    printf '%s\n' '    printf "fake rmdir induced cleanup failure: %s\\n" "$last_argument" >&2'
    printf '%s\n' '    exit 96'
    printf '%s\n' 'fi'
    printf '%s\n' 'exec "${REAL_RMDIR:-/usr/bin/rmdir}" "$@"'
} > "$fake_bin/rmdir"
chmod +x "$fake_bin/rmdir"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf '%s\n' 'last_argument="${!#}"'
    printf '%s\n' 'if [[ "${DEPLOY_TEST_MARKER_PREFLIGHT_FAIL:-}" == "1" && "$last_argument" == */.active-release-*.preflight.XXXXXX ]]; then'
    printf '%s\n' '    printf "fake mktemp induced active-marker preflight failure: %s\\n" "$last_argument" >&2'
    printf '%s\n' '    exit 97'
    printf '%s\n' 'fi'
    printf '%s\n' 'exec "${REAL_MKTEMP:-/usr/bin/mktemp}" "$@"'
} > "$fake_bin/mktemp"
chmod +x "$fake_bin/mktemp"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'if [[ "${DEPLOY_TEST_FLOCK_FAIL:-}" == "1" ]]; then'
    printf '%s\n' '    exit 1'
    printf '%s\n' 'fi'
    printf '%s\n' 'exit 0'
} > "$fake_bin/flock"
chmod +x "$fake_bin/flock"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf '%s\n' 'test -n "${DEPLOY_TEST_FILTER_MARKER:-}"'
    printf '%s\n' 'printf "ran\\n" > "$DEPLOY_TEST_FILTER_MARKER"'
    printf '%s\n' 'cat'
} > "$fake_bin/evil-smudge"
chmod +x "$fake_bin/evil-smudge"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf '%s\n' 'if [[ -e "$(dirname "$0")/tar.fail" ]]; then'
    printf '%s\n' '    printf "invoked\\n" > "$(dirname "$0")/tar.failure-invoked"'
    printf '%s\n' '    cat >/dev/null'
    printf '%s\n' '    exit 77'
    printf '%s\n' 'fi'
    printf 'exec %q "$@"\n' "$real_tar"
} > "$fake_bin/tar"
chmod +x "$fake_bin/tar"

write_test_image_manifest() {
    local manifest="$1"
    local target_profile="$2"
    local image_tag="${3:-0123456789abcdef0123456789abcdef01234567}"
    local service
    local image_id

    {
        printf 'IMAGE_TAG=%s\n' "$image_tag"
        for service in backend admin reporter; do
            image_id="$(printf 'eyesonu/%s-%s:%s' "$service" "$target_profile" "$image_tag" | sha256sum | awk '{print $1}')"
            printf '%s_IMAGE_ID=sha256:%s\n' "${service^^}" "$image_id"
        done
    } > "$manifest"
}

active_release_path() {
    sed -n '1p' "$1"
}

temporary_release_directories() {
    find "$release_root" -maxdepth 1 -type d \( \
        -name ".pending-${runner_commit}.*" -o \
        -name ".pending-git-${runner_commit}.*" -o \
        -name '.git-home.*' -o \
        -name '.git-hooks.*' -o \
        -name '.git-template.*' \
    \) -printf '%f\n' | LC_ALL=C sort
}

temporary_active_marker_files() {
    find "$release_root" -maxdepth 1 -type f -name '.active-release-*.*' -printf '%f\n' | LC_ALL=C sort
}

test_immutable_release_runner() {
    local runner_repo="$temp_root/immutable-release-runner"
    local runner_commit
    local malicious_commit
    local runner_result_file="$temp_root/immutable-release-result"
    local deployed_tree
    local first_deployed_tree
    local deployed_runtime_root
    local deployed_compose_file
    local deployed_profile
    local hook_marker="$temp_root/immutable-post-checkout-ran"
    local filter_marker="$temp_root/immutable-filter-smudge-ran"
    local trace_marker="$temp_root/immutable-git-trace.json"
    local inherited_release_root="$temp_root/inherited-release-root"
    local release_root
    local active_dev_marker
    local active_master_marker
    local active_dev_tree
    local candidate_failure_recovery_marker="$temp_root/candidate-failure-recovery"
    local marker_failure_recovery_marker="$temp_root/marker-failure-recovery"
    local initial_marker_failure_recovery_marker="$temp_root/initial-marker-failure-recovery"
    local preflight_failure_output="$temp_root/marker-preflight-output"
    local rollback_race_output="$temp_root/rollback-race-output"
    local rollback_race_recovery_marker="$temp_root/rollback-race-recovery"
    local tar_failure_marker="$fake_bin/tar.failure-invoked"
    local candidate_stop_path
    local rollback_race_stop_path
    local marker_failure_stop_path

    mkdir -p "$runner_repo/infra/scripts"
    git init -q "$runner_repo"
    git -C "$runner_repo" config user.email "ci@example.invalid"
    git -C "$runner_repo" config user.name "Immutable release runner test"
    git -C "$runner_repo" config core.autocrlf false
    printf 'ignored-leak.pem\n' > "$runner_repo/.gitignore"
    mkdir -p "$runner_repo/infra/certbot/www" "$runner_repo/infra/certbot/conf"
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'set -Eeuo pipefail'
        printf '%s\n' 'test -n "${DEPLOY_TEST_RUNNER_OUTPUT:-}"'
        printf '%s\n' 'if [[ "${DEPLOY_ROLLBACK_ONLY:-}" == "1" ]]; then'
        printf '%s\n' '    test -n "${DEPLOY_TEST_RECOVERY_MARKER:-}"'
        printf '%s\n' '    printf "rollback|%s|%s\\n" "$1" "${DEPLOY_PREVIOUS_RELEASE:-}" >> "$DEPLOY_TEST_RECOVERY_MARKER"'
        printf '%s\n' '    exit 0'
        printf '%s\n' 'fi'
        printf '%s\n' 'if [[ "${DEPLOY_STOP_ONLY:-}" == "1" ]]; then'
        printf '%s\n' '    test -n "${DEPLOY_TEST_RECOVERY_MARKER:-}"'
        printf '%s\n' '    printf "stop|%s|%s\\n" "$1" "$DEPLOY_ROOT" >> "$DEPLOY_TEST_RECOVERY_MARKER"'
        printf '%s\n' '    exit 0'
        printf '%s\n' 'fi'
        printf '%s\n' 'if [[ "${DEPLOY_TEST_RUNNER_FAIL:-}" == "1" ]]; then'
        printf '%s\n' '    if [[ -n "${DEPLOY_TEST_MUTATE_ACTIVE_MARKER:-}" ]]; then printf "changed\\n" > "$DEPLOY_TEST_MUTATE_ACTIVE_MARKER"; fi'
        printf '%s\n' '    exit 65'
        printf '%s\n' 'fi'
        printf '%s\n' 'test -f "$DEPLOY_ENV_FILE"'
        printf '%s\n' 'test -f "$DEPLOY_COMPOSE"'
        printf '%s\n' 'printf "%s|%s|%s|%s\\n" "$DEPLOY_ROOT" "$DEPLOY_RUNTIME_ROOT" "$DEPLOY_COMPOSE" "$1" > "$DEPLOY_TEST_RUNNER_OUTPUT"'
    } > "$runner_repo/infra/scripts/deploy-on-host.sh"
    printf 'name: test\n' > "$runner_repo/infra/compose.deploy.yml"
    printf 'AUTO_ROLLBACK_SCHEMA_COMPATIBLE=1\n' > "$runner_repo/infra/release-policy.env"
    printf 'baseline\n' > "$runner_repo/tracked.txt"
    : > "$runner_repo/deploy.env"
    git -C "$runner_repo" add .gitignore infra/scripts infra/compose.deploy.yml infra/release-policy.env tracked.txt deploy.env
    git -C "$runner_repo" commit -qm "immutable runner fixture"
    runner_commit="$(git -C "$runner_repo" rev-parse HEAD)"

    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'printf "ran\\n" > "$DEPLOY_TEST_HOOK_MARKER"'
    } > "$runner_repo/.git/hooks/post-checkout"
    chmod +x "$runner_repo/.git/hooks/post-checkout"
    printf '* filter=evil\n' > "$runner_repo/.git/info/attributes"
    git -C "$runner_repo" config filter.evil.smudge "$fake_bin/evil-smudge"

    if PATH="$fake_bin:$PATH" \
        REAL_TAR="$real_tar" \
        DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        DEPLOY_TEST_FAIL_ACTIVE_MARKER=1 \
        DEPLOY_TEST_RECOVERY_MARKER="$initial_marker_failure_recovery_marker" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "first active-marker publication failure must stop the unmarked candidate and return failure"
    fi

    release_root="$(dirname "$runner_repo")/.eyesonu-deploy-releases"
    active_dev_marker="$release_root/.active-release-dev"
    active_master_marker="$release_root/.active-release-master"
    [[ ! -e "$active_dev_marker" && ! -L "$active_dev_marker" ]] \
        || fail "a first active-marker publication failure must not create an active marker"
    [[ "$(<"$initial_marker_failure_recovery_marker")" == "stop|dev|$release_root"/release-* ]] \
        || fail "a first active-marker publication failure must stop the exact unmarked dev candidate"

    PATH="$fake_bin:$PATH" \
        REAL_TAR="$real_tar" \
        DEPLOY_TEST_FILTER_MARKER="$filter_marker" \
        DEPLOY_TEST_HOOK_MARKER="$hook_marker" \
        DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        DEPLOY_COMPOSE="$temp_root/inherited-compose.yml" \
        DEPLOY_RELEASE_ROOT="$inherited_release_root" \
        GIT_TRACE2_EVENT="$trace_marker" \
        GIT_CONFIG_COUNT=2 \
        GIT_CONFIG_KEY_0=core.attributesFile \
        GIT_CONFIG_VALUE_0="$runner_repo/.git/info/attributes" \
        GIT_CONFIG_KEY_1=filter.evil.smudge \
        GIT_CONFIG_VALUE_1="$fake_bin/evil-smudge" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev

    [[ ! -e "$filter_marker" && ! -e "$hook_marker" && ! -e "$trace_marker" ]] \
        || fail "immutable release runner must not execute host Git filters, hooks, or inherited Git environment"
    IFS='|' read -r deployed_tree deployed_runtime_root deployed_compose_file deployed_profile < "$runner_result_file"
    [[ -d "$deployed_tree" && ! -e "$deployed_tree/.git" && "$deployed_tree" != "$runner_repo" && "$deployed_tree" != "$inherited_release_root/"* && "$deployed_runtime_root" == "$runner_repo/infra" && "$deployed_compose_file" == "$deployed_tree/infra/compose.deploy.yml" && "$deployed_profile" == "dev" ]] \
        || fail "immutable release runner did not publish a Git-free isolated deployment tree"
    first_deployed_tree="$deployed_tree"
    [[ -f "$active_dev_marker" && ! -L "$active_dev_marker" && "$(active_release_path "$active_dev_marker")" == "$first_deployed_tree" && "$(sed -n '2p' "$active_dev_marker")" =~ ^[0-9a-f]{64}$ ]] \
        || fail "a successful deployment must atomically mark its verified release active"

    local active_release_before_first_tamper
    active_release_before_first_tamper="$(<"$active_dev_marker")"
    printf 'tampered\n' >> "$first_deployed_tree/infra/scripts/deploy-on-host.sh"
    mkdir -p "$first_deployed_tree/.git/info"
    printf '* filter=evil\n' > "$first_deployed_tree/.git/info/attributes"
    : > "$first_deployed_tree/ignored-leak.pem"
    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "a tampered active release must be rejected as a rollback source"
    fi
    [[ "$(<"$active_dev_marker")" == "$active_release_before_first_tamper" ]] \
        || fail "a rejected active release must not change its marker"
    cp -- "$runner_repo/infra/scripts/deploy-on-host.sh" "$first_deployed_tree/infra/scripts/deploy-on-host.sh"
    rm -rf -- "$first_deployed_tree/.git"
    rm -f -- "$first_deployed_tree/ignored-leak.pem"

    PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev
    IFS='|' read -r deployed_tree deployed_runtime_root deployed_compose_file deployed_profile < "$runner_result_file"
    [[ "$deployed_tree" != "$first_deployed_tree" && ! -e "$deployed_tree/.git" && "$deployed_profile" == "dev" ]] \
        || fail "an intact verified release must deploy after the tampered release is restored"
    [[ "$(active_release_path "$active_dev_marker")" == "$deployed_tree" ]] \
        || fail "a later successful deployment must update the active release marker"
    active_dev_tree="$deployed_tree"

    local active_release_before_failed_deploy
    active_release_before_failed_deploy="$(<"$active_dev_marker")"
    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" DEPLOY_TEST_RUNNER_FAIL=1 \
        DEPLOY_TEST_RECOVERY_MARKER="$candidate_failure_recovery_marker" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "a failed deploy script must leave the existing active release intact and return failure"
    fi
    [[ "$(<"$active_dev_marker")" == "$active_release_before_failed_deploy" ]] \
        || fail "a failed deploy script must not advance the active release marker"
    candidate_stop_path="$(awk -F '|' '$1 == "stop" && $2 == "dev" { print $3 }' "$candidate_failure_recovery_marker")"
    [[ "$candidate_stop_path" == "$release_root"/release-* && "$candidate_stop_path" != "$active_dev_tree" ]] \
        || fail "a failed deploy script must stop the exact candidate profile before rollback"
    grep -Fxq "rollback|dev|$active_dev_tree" "$candidate_failure_recovery_marker" \
        || fail "a failed deploy script must rollback the exact previous dev release through the verified runner"

    printf 'not-started\n' > "$preflight_failure_output"
    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" REAL_MKTEMP="$real_mktemp" \
        DEPLOY_TEST_RUNNER_OUTPUT="$preflight_failure_output" DEPLOY_TEST_MARKER_PREFLIGHT_FAIL=1 \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "an active-marker preflight failure must stop before the candidate deploy script runs"
    fi
    [[ "$(<"$preflight_failure_output")" == "not-started" && "$(<"$active_dev_marker")" == "$active_release_before_failed_deploy" ]] \
        || fail "active-marker preflight failure must preserve the active release and avoid service mutation"

    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" DEPLOY_TEST_RUNNER_FAIL=1 \
        DEPLOY_TEST_MUTATE_ACTIVE_MARKER="$active_dev_marker" DEPLOY_TEST_RECOVERY_MARKER="$rollback_race_recovery_marker" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >"$rollback_race_output" 2>&1; then
        fail "a changed active marker during candidate failure must reject rollback"
    fi
    grep -Fq 'active release marker changed or became invalid before rollback' "$rollback_race_output" \
        || fail "rollback race failure must identify the active-marker revalidation gate"
    rollback_race_stop_path="$(awk -F '|' '$1 == "stop" && $2 == "dev" { print $3 }' "$rollback_race_recovery_marker")"
    [[ "$rollback_race_stop_path" == "$release_root"/release-* && "$rollback_race_stop_path" != "$active_dev_tree" ]] \
        || fail "rollback race handling must stop the failed candidate before rejecting the changed active marker"
    if grep -Fq 'rollback|' "$rollback_race_recovery_marker"; then
        fail "rollback must not start a release after the active marker changes"
    fi
    printf '%s' "$active_release_before_failed_deploy" > "$active_dev_marker"

    printf 'tampered\n' >> "$active_dev_tree/tracked.txt"
    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "rollback must reject a retained release whose content digest changed"
    fi
    printf 'baseline\n' > "$active_dev_tree/tracked.txt"
    [[ "$(<"$active_dev_marker")" == "$active_release_before_failed_deploy" ]] \
        || fail "a rejected retained release must not change the active marker"

    PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" master
    IFS='|' read -r deployed_tree deployed_runtime_root deployed_compose_file deployed_profile < "$runner_result_file"
    [[ "$deployed_profile" == "master" && "$(active_release_path "$active_dev_marker")" == "$active_dev_tree" && -f "$active_master_marker" && "$(active_release_path "$active_master_marker")" == "$deployed_tree" ]] \
        || fail "dev and master deployments must retain independent active release markers"

    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        DEPLOY_TEST_FAIL_ACTIVE_MARKER=1 DEPLOY_TEST_RECOVERY_MARKER="$marker_failure_recovery_marker" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "active-marker publication failure must rollback and return failure"
    fi
    marker_failure_stop_path="$(awk -F '|' '$1 == "stop" && $2 == "dev" { print $3 }' "$marker_failure_recovery_marker")"
    [[ "$(<"$active_dev_marker")" == "$active_release_before_failed_deploy" && "$marker_failure_stop_path" == "$release_root"/release-* && "$marker_failure_stop_path" != "$active_dev_tree" ]] \
        || fail "active-marker publication failure must stop the candidate without changing the previous marker"
    grep -Fxq "rollback|dev|$active_dev_tree" "$marker_failure_recovery_marker" \
        || fail "active-marker publication failure must restore the previous dev release"
    [[ -z "$(temporary_active_marker_files)" ]] \
        || fail "active-marker publication failure must remove its temporary marker file"

    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'printf "malicious\\n" > "$DEPLOY_TEST_RUNNER_OUTPUT"'
    } > "$runner_repo/infra/scripts/deploy-on-host.sh"
    git -C "$runner_repo" add infra/scripts/deploy-on-host.sh
    git -C "$runner_repo" commit -qm "malicious replacement target"
    malicious_commit="$(git -C "$runner_repo" rev-parse HEAD)"
    git -C "$runner_repo" replace "$runner_commit" "$malicious_commit"
    PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev
    git -C "$runner_repo" replace -d "$runner_commit"
    IFS='|' read -r deployed_tree deployed_runtime_root deployed_compose_file deployed_profile < "$runner_result_file"
    [[ "$deployed_tree" != "$first_deployed_tree" && "$deployed_profile" == "dev" && ! -e "$deployed_tree/.git" ]] \
        || fail "replace refs must not substitute the trusted deployment commit"

    local active_release_before_failed_materialization
    local temporary_directories_before_failed_materialization
    local temporary_marker_files_before_failed_materialization
    active_release_before_failed_materialization="$(<"$active_dev_marker")"
    temporary_directories_before_failed_materialization="$(temporary_release_directories)"
    temporary_marker_files_before_failed_materialization="$(temporary_active_marker_files)"
    rm -f -- "$tar_failure_marker"
    : > "$fake_bin/tar.fail"
    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "release publication must fail when archive extraction fails"
    fi
    rm -f -- "$fake_bin/tar.fail"
    [[ "$(<"$tar_failure_marker")" == "invoked" ]] \
        || fail "interrupted-materialization test must reach the archive extraction failure branch"
    [[ "$(<"$active_dev_marker")" == "$active_release_before_failed_materialization" ]] \
        || fail "a failed materialization must not advance the active release marker"
    [[ "$(temporary_release_directories)" == "$temporary_directories_before_failed_materialization" ]] \
        || fail "failed release extraction must remove only the temporary directories created by that attempt"
    [[ "$(temporary_active_marker_files)" == "$temporary_marker_files_before_failed_materialization" ]] \
        || fail "failed release extraction must not leave a temporary active-marker file"
    PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev
    IFS='|' read -r deployed_tree deployed_runtime_root deployed_compose_file deployed_profile < "$runner_result_file"
    [[ "$deployed_profile" == "dev" && ! -e "$deployed_tree/.git" ]] \
        || fail "the same commit must deploy successfully after an interrupted materialization retry"
    [[ "$(active_release_path "$active_dev_marker")" == "$deployed_tree" ]] \
        || fail "a successful retry must advance the active release marker only after deployment"
    [[ "$(temporary_release_directories)" == "$temporary_directories_before_failed_materialization" ]] \
        || fail "successful release publication must remove the temporary directories created by that attempt"
    [[ "$(temporary_active_marker_files)" == "$temporary_marker_files_before_failed_materialization" ]] \
        || fail "successful release publication must remove temporary active-marker files"

    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" DEPLOY_TEST_FLOCK_FAIL=1 DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >/dev/null 2>&1; then
        fail "immutable release runner must stop when the deployment lock cannot be acquired"
    fi

    local cleanup_failure_log="$temp_root/cleanup-failure.log"
    if PATH="$fake_bin:$PATH" REAL_TAR="$real_tar" REAL_RMDIR="$real_rmdir" DEPLOY_TEST_RMDIR_FAIL=1 DEPLOY_TEST_RUNNER_OUTPUT="$runner_result_file" \
        bash "$verified_runner_script" "$runner_commit" "$runner_repo" "$runner_repo/deploy.env" dev \
        >"$cleanup_failure_log" 2>&1; then
        fail "verified deployment runner must fail rather than hide an incomplete temporary cleanup"
    fi
    grep -Fq 'verified deployment temporary cleanup was incomplete' "$cleanup_failure_log" \
        || fail "verified deployment runner must report an incomplete temporary cleanup"
}

test_verified_jenkins_source_materializer() {
    local source_repo="$temp_root/verified-jenkins-source"
    local source_commit
    local malicious_commit
    local source_dir="$source_repo/.verified-release-source"
    local source_commit_file="$source_repo/.verified-release-commit"
    local hook_marker="$temp_root/materializer-post-checkout-ran"
    local filter_marker="$temp_root/materializer-filter-smudge-ran"
    local trace_marker="$temp_root/materializer-git-trace.json"

    mkdir -p "$source_repo"
    git init -q "$source_repo"
    git -C "$source_repo" config user.email "ci@example.invalid"
    git -C "$source_repo" config user.name "Verified Jenkins source test"
    git -C "$source_repo" config core.autocrlf false
    printf 'baseline\n' > "$source_repo/payload.txt"
    git -C "$source_repo" add payload.txt
    git -C "$source_repo" commit -qm "verified Jenkins source fixture"
    source_commit="$(git -C "$source_repo" rev-parse HEAD)"

    printf 'malicious\n' > "$source_repo/payload.txt"
    git -C "$source_repo" add payload.txt
    git -C "$source_repo" commit -qm "malicious replacement target"
    malicious_commit="$(git -C "$source_repo" rev-parse HEAD)"
    git -C "$source_repo" update-ref refs/remotes/origin/dev "$source_commit"
    git -C "$source_repo" replace "$source_commit" "$malicious_commit"

    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'printf "ran\\n" > "$DEPLOY_TEST_HOOK_MARKER"'
    } > "$source_repo/.git/hooks/post-checkout"
    chmod +x "$source_repo/.git/hooks/post-checkout"
    printf '* filter=evil\n' > "$source_repo/.git/info/attributes"
    git -C "$source_repo" config filter.evil.smudge "$fake_bin/evil-smudge"

    : > "$fake_bin/tar.fail"
    if (
        cd "$source_repo"
        PATH="$fake_bin:$PATH" \
            DEPLOY_TEST_FILTER_MARKER="$filter_marker" \
            DEPLOY_TEST_HOOK_MARKER="$hook_marker" \
            GIT_TRACE2_EVENT="$trace_marker" \
            GIT_CONFIG_COUNT=2 \
            GIT_CONFIG_KEY_0=core.attributesFile \
            GIT_CONFIG_VALUE_0="$source_repo/.git/info/attributes" \
            GIT_CONFIG_KEY_1=filter.evil.smudge \
            GIT_CONFIG_VALUE_1="$fake_bin/evil-smudge" \
            bash "$source_materializer_script" dev "$source_commit"
    ) >/dev/null 2>&1; then
        fail "verified Jenkins source publication must fail when archive extraction fails"
    fi
    rm -f -- "$fake_bin/tar.fail"
    if find "$source_repo" -maxdepth 1 -type d \( \
        -name '.verified-git-home.*' -o \
        -name '.verified-git-hooks.*' -o \
        -name '.verified-git-template.*' -o \
        -name '.verified-git-source.*' -o \
        -name '.verified-release-source.*' \
    \) -print -quit | grep -q .; then
        fail "failed Jenkins source publication must remove all isolated temporary directories"
    fi

    (
        cd "$source_repo"
        PATH="$fake_bin:$PATH" \
            DEPLOY_TEST_FILTER_MARKER="$filter_marker" \
            DEPLOY_TEST_HOOK_MARKER="$hook_marker" \
            GIT_TRACE2_EVENT="$trace_marker" \
            GIT_CONFIG_COUNT=2 \
            GIT_CONFIG_KEY_0=core.attributesFile \
            GIT_CONFIG_VALUE_0="$source_repo/.git/info/attributes" \
            GIT_CONFIG_KEY_1=filter.evil.smudge \
            GIT_CONFIG_VALUE_1="$fake_bin/evil-smudge" \
            bash "$source_materializer_script" dev "$source_commit"
    )

    [[ ! -e "$filter_marker" && ! -e "$hook_marker" && ! -e "$trace_marker" ]] \
        || fail "verified Jenkins source materializer must not execute checkout hooks, filters, or inherited Git environment"
    [[ -d "$source_dir" && ! -e "$source_dir/.git" && "$(<"$source_dir/payload.txt")" == "baseline" ]] \
        || fail "verified Jenkins source materializer must archive the original canonical commit without replacement"
    [[ "$(<"$source_commit_file")" == "$source_commit" ]] \
        || fail "verified Jenkins source materializer must record the exact canonical commit"

    printf 'tampered\n' > "$source_dir/payload.txt"
    mkdir -p "$source_dir/.git"
    rm -f -- "$source_commit_file"
    : > "$temp_root/redirected-release-commit"
    ln -s "$temp_root/redirected-release-commit" "$source_commit_file"
    (
        cd "$source_repo"
        PATH="$fake_bin:$PATH" bash "$source_materializer_script" dev "$source_commit"
    )
    [[ ! -e "$source_dir/.git" && "$(<"$source_dir/payload.txt")" == "baseline" && ! -L "$source_commit_file" && "$(<"$source_commit_file")" == "$source_commit" ]] \
        || fail "verified Jenkins source materializer must never reuse a retained source directory or follow a retained commit marker symlink"
    if find "$source_repo" -maxdepth 1 -type d \( \
        -name '.verified-git-home.*' -o \
        -name '.verified-git-hooks.*' -o \
        -name '.verified-git-template.*' -o \
        -name '.verified-git-source.*' -o \
        -name '.verified-release-source.*' \
    \) -print -quit | grep -q .; then
        fail "successful Jenkins source publication must remove all isolated temporary directories"
    fi
    git -C "$source_repo" replace -d "$source_commit"
}

test_missing_runtime_root() {
    local output_file="$temp_root/missing-runtime-root.log"

    if env \
        "DEPLOY_ROOT=$repo_root" \
        "DEPLOY_RUNTIME_ROOT=$temp_root/missing-runtime-root" \
        "DEPLOY_COMPOSE=$compose_file" \
        "DEPLOY_ENV_FILE=$example_env_file" \
        bash "$deploy_script" dev > "$output_file" 2>&1; then
        fail "deployment must reject a missing certificate runtime directory"
    fi
    grep -Fq 'required directory is missing' "$output_file" \
        || fail "missing certificate runtime failure must identify the directory contract"
}

test_missing_shared_nginx_ssl_parameters() {
    local ssl_parameters_file="$runtime_root/nginx/snippets/ssl-params.conf"
    local output_file="$temp_root/missing-nginx-ssl-parameters.log"

    rm -f -- "$ssl_parameters_file"
    if env \
        "DEPLOY_ROOT=$repo_root" \
        "DEPLOY_RUNTIME_ROOT=$runtime_root" \
        "DEPLOY_COMPOSE=$compose_file" \
        "DEPLOY_ENV_FILE=$example_env_file" \
        bash "$deploy_script" dev > "$output_file" 2>&1; then
        fail "deployment must reject a missing shared Nginx SSL-parameter file"
    fi
    grep -Fq 'shared Nginx SSL parameters are missing or unsafe' "$output_file" \
        || fail "missing shared Nginx SSL parameters must identify the runtime-file contract"
    printf 'ssl_protocols TLSv1.2 TLSv1.3;\n' > "$ssl_parameters_file"
}

write_rollback_fixture_release() {
    local release_dir="$1"

    mkdir -p "$release_dir/infra/scripts"
    cp "$deploy_script" "$release_dir/infra/scripts/deploy-on-host.sh"
    cp "$repo_root/infra/scripts/cleanup-legacy-containers.sh" "$release_dir/infra/scripts/cleanup-legacy-containers.sh"
    printf '%s\n' \
        'name: eyesonu-deploy' \
        'services:' \
        '  backend-dev:' \
        '    image: alpine:3.20' \
        '  admin-dev:' \
        '    image: alpine:3.20' \
        '  reporter-dev:' \
        '    image: alpine:3.20' \
        '  nginx:' \
        '    image: nginx:1.27-alpine' \
        > "$release_dir/infra/compose.deploy.yml"
    write_test_image_manifest "$release_dir/infra/.verified-release-images" dev
}

test_deploy_script_defers_rollback_to_verified_runner() {
    local releases_root="$temp_root/rollback-releases"
    local current_release="$releases_root/release-current"
    local previous_release="$releases_root/release-previous"
    local current_compose_file="$current_release/infra/compose.deploy.yml"
    local previous_compose_file="$previous_release/infra/compose.deploy.yml"
    local output_file="$temp_root/failed-deploy-rolls-back.log"

    write_rollback_fixture_release "$current_release"
    write_rollback_fixture_release "$previous_release"
    reset_captures

    if env \
        "PATH=$fake_bin:$PATH" \
        "REAL_DOCKER=$real_docker" \
        "DEPLOY_TEST_CAPTURED_ENV_PATH=$captured_env_path_file" \
        "DEPLOY_TEST_CAPTURED_PROJECT_NAME=$captured_project_name_file" \
        "DEPLOY_TEST_PLACEHOLDER_CALLS=$placeholder_calls_file" \
        "DEPLOY_TEST_COMPOSE_COMMANDS=$compose_commands_file" \
        "DEPLOY_TEST_DOCKER_CONFIG_LOG=$docker_config_log_file" \
        "DEPLOY_TEST_EXPECTED_ENV_FILE=$example_env_file" \
        "DEPLOY_TEST_FAIL_COMPOSE_FILE=$current_compose_file" \
        "DEPLOY_ROOT=$current_release" \
        "DEPLOY_PREVIOUS_RELEASE=$previous_release" \
        "DEPLOY_RUNTIME_ROOT=$runtime_root" \
        "DEPLOY_COMPOSE=$current_compose_file" \
        "DEPLOY_ENV_FILE=$example_env_file" \
        bash "$current_release/infra/scripts/deploy-on-host.sh" dev > "$output_file" 2>&1; then
        fail "a failed current release must return failure after rollback"
    fi

    grep -Fq 'verified release deployment failed' "$output_file" \
        || fail "a failed current release must return its failure to the verified runner"
    if grep -Fq -- "-f $previous_compose_file" "$compose_commands_file"; then
        fail "deploy-on-host must defer rollback until the verified runner revalidates the active release"
    fi
}

test_rollback_only_stops_candidate_before_restoring_previous_release() {
    local releases_root="$temp_root/rollback-only-releases"
    local current_release="$releases_root/release-current"
    local previous_release="$releases_root/release-previous"
    local current_compose_file="$current_release/infra/compose.deploy.yml"
    local previous_compose_file="$previous_release/infra/compose.deploy.yml"
    local output_file="$temp_root/rollback-only.log"
    local candidate_stop_command
    local previous_up_command

    write_rollback_fixture_release "$current_release"
    write_rollback_fixture_release "$previous_release"
    reset_captures

    if ! env \
        "PATH=$fake_bin:$PATH" \
        "REAL_DOCKER=$real_docker" \
        "DEPLOY_TEST_CAPTURED_ENV_PATH=$captured_env_path_file" \
        "DEPLOY_TEST_CAPTURED_PROJECT_NAME=$captured_project_name_file" \
        "DEPLOY_TEST_PLACEHOLDER_CALLS=$placeholder_calls_file" \
        "DEPLOY_TEST_COMPOSE_COMMANDS=$compose_commands_file" \
        "DEPLOY_TEST_DOCKER_CONFIG_LOG=$docker_config_log_file" \
        "DEPLOY_TEST_EXPECTED_ENV_FILE=$example_env_file" \
        "DEPLOY_ROOT=$current_release" \
        "DEPLOY_PREVIOUS_RELEASE=$previous_release" \
        "DEPLOY_RUNTIME_ROOT=$runtime_root" \
        "DEPLOY_COMPOSE=$current_compose_file" \
        "DEPLOY_ENV_FILE=$example_env_file" \
        DEPLOY_ROLLBACK_ONLY=1 \
        bash "$current_release/infra/scripts/deploy-on-host.sh" dev > "$output_file" 2>&1; then
        tail -n 50 "$output_file" >&2
        fail "rollback-only deployment must restore a previous release after candidate cleanup"
    fi

    candidate_stop_command="$(grep -F -- "-f $current_compose_file" "$compose_commands_file" | grep -F ' stop ' || true)"
    previous_up_command="$(grep -F -- "-f $previous_compose_file" "$compose_commands_file" | grep -F ' up ' || true)"
    [[ -n "$candidate_stop_command" ]] \
        || fail "rollback-only deployment did not stop the failed candidate profile"
    [[ "$candidate_stop_command" != *nginx* ]] \
        || fail "rollback-only candidate cleanup must not stop shared Nginx"
    [[ -n "$previous_up_command" ]] \
        || fail "rollback-only deployment did not restore the previous release"
}

test_stop_only_stops_the_full_profile_without_nginx() {
    local output_file="$temp_root/stop-only.log"
    local image_manifest="$temp_root/verified-images-stop-only.env"
    local stop_command
    local service_name

    reset_captures
    write_test_image_manifest "$image_manifest" dev
    if ! env \
        "PATH=$fake_bin:$PATH" \
        "REAL_DOCKER=$real_docker" \
        "DEPLOY_TEST_CAPTURED_ENV_PATH=$captured_env_path_file" \
        "DEPLOY_TEST_CAPTURED_PROJECT_NAME=$captured_project_name_file" \
        "DEPLOY_TEST_PLACEHOLDER_CALLS=$placeholder_calls_file" \
        "DEPLOY_TEST_COMPOSE_COMMANDS=$compose_commands_file" \
        "DEPLOY_TEST_DOCKER_CONFIG_LOG=$docker_config_log_file" \
        "DEPLOY_TEST_EXPECTED_ENV_FILE=$example_env_file" \
        "DEPLOY_TEST_EXPECTED_PLACEHOLDER=MASTER_AI_WORKER_API_KEY" \
        "DEPLOY_ROOT=$repo_root" \
        "DEPLOY_RUNTIME_ROOT=$runtime_root" \
        "DEPLOY_COMPOSE=$compose_file" \
        "DEPLOY_ENV_FILE=$example_env_file" \
        "DEPLOY_IMAGE_MANIFEST=$image_manifest" \
        DEPLOY_STOP_ONLY=1 \
        bash "$deploy_script" dev > "$output_file" 2>&1; then
        tail -n 50 "$output_file" >&2
        fail "stop-only deployment must stop every dev service without touching shared Nginx"
    fi

    stop_command="$(grep -F -- '--profile dev stop ' "$compose_commands_file" || true)"
    [[ -n "$stop_command" ]] || fail "stop-only deployment did not invoke Docker Compose stop for the dev profile"
    for service_name in backend-dev admin-dev reporter-dev mysql-dev rabbitmq-dev minio-dev minio-init-dev; do
        [[ "$stop_command" == *"$service_name"* ]] \
            || fail "stop-only deployment did not stop dependent profile service: $service_name"
    done
    [[ "$stop_command" != *nginx* ]] \
        || fail "stop-only deployment must not stop the shared Nginx service"
}

test_forced_command_rejects_untrusted_input() {
    local output_file="$temp_root/forced-command-reject.log"
    local exit_status

    set +e
    env -i \
        "PATH=$PATH" \
        'SSH_ORIGINAL_COMMAND=eyesonu-deploy dev 0123456789012345678901234567890123456789 extra' \
        bash "$forced_command_script" > "$output_file" 2>&1
    exit_status=$?
    set -e

    [[ $exit_status -eq 126 ]] \
        || fail "deployment forced command must reject extra SSH command arguments"
    grep -Fq 'only accepts: eyesonu-deploy <dev|master> <full-commit>' "$output_file" \
        || fail "deployment forced command rejection must explain the restricted protocol"
}

reset_captures() {
    rm -f -- \
        "$captured_env_path_file" \
        "$captured_project_name_file" \
        "$placeholder_calls_file" \
        "$compose_commands_file" \
        "$docker_engine_commands_file" \
        "$docker_config_log_file"
}

run_deploy() {
    local target_profile="$1"
    local env_file="$2"
    local expected_placeholder="$3"
    local output_file="${4:-$temp_root/deploy-${target_profile}.log}"
    local inherited_variable_name="${5:-}"
    local inherited_variable_value="${6:-}"
    local shared_nginx_running="${7:-}"
    local image_manifest="$temp_root/verified-images-$target_profile.env"
    write_test_image_manifest "$image_manifest" "$target_profile"
    local -a command_env=(
        "PATH=$fake_bin:$PATH"
        "REAL_DOCKER=$real_docker"
        "DEPLOY_TEST_CAPTURED_ENV_PATH=$captured_env_path_file"
        "DEPLOY_TEST_CAPTURED_PROJECT_NAME=$captured_project_name_file"
        "DEPLOY_TEST_PLACEHOLDER_CALLS=$placeholder_calls_file"
        "DEPLOY_TEST_COMPOSE_COMMANDS=$compose_commands_file"
        "DEPLOY_TEST_DOCKER_ENGINE_COMMANDS=$docker_engine_commands_file"
        "DEPLOY_TEST_DOCKER_CONFIG_LOG=$docker_config_log_file"
        "DEPLOY_TEST_EXPECTED_ENV_FILE=$env_file"
        "DEPLOY_TEST_EXPECTED_PLACEHOLDER=$expected_placeholder"
        "DEPLOY_TEST_FAIL_COMPOSE_FILE="
        "DEPLOY_ROOT=$repo_root"
        "DEPLOY_RUNTIME_ROOT=$runtime_root"
        "DEPLOY_COMPOSE=$compose_file"
        "DEPLOY_ENV_FILE=$env_file"
        "DEPLOY_IMAGE_MANIFEST=$image_manifest"
        "DEPLOY_TEST_NGINX_RUNNING=$shared_nginx_running"
    )

    if [[ -n "$inherited_variable_name" ]]; then
        command_env+=("$inherited_variable_name=$inherited_variable_value")
    fi

    if env "${command_env[@]}" bash "$deploy_script" "$target_profile" > "$output_file" 2>&1; then
        return
    else
        local status=$?
        printf 'Deployment fixture failed with exit status %s:\n' "$status" >&2
        tail -n 50 "$output_file" >&2
        return "$status"
    fi
}

assert_successful_scope() {
    local label="$1"
    local expected_placeholder="$2"
    local expected_profile="$3"

    [[ -s "$captured_env_path_file" ]] || fail "$label did not invoke Docker Compose"
    [[ -s "$captured_project_name_file" ]] || fail "$label did not record the Compose project-name environment"
    if grep -Fxq 'set' "$captured_project_name_file"; then
        fail "$label allowed an inherited COMPOSE_PROJECT_NAME to select another stack"
    fi
    if ! awk -v expected="$expected_placeholder" '$0 != expected { exit 1 }' "$placeholder_calls_file"; then
        fail "$label did not override the inactive profile variable for every Compose call"
    fi
    # Nginx is now a root-managed ingress stack, so profile deployment invokes
    # Compose only for config, app up, and app ps. Those calls must all retain
    # the inactive-profile interpolation override.
    [[ "$(grep -c '^yes$' "$placeholder_calls_file")" -ge 3 ]] \
        || fail "$label did not preserve the inactive override through every profile Compose call"
    grep -Fq -- "--profile $expected_profile" "$compose_commands_file" \
        || fail "$label did not select the $expected_profile Compose profile"
    if ! grep -Fq -- "backend-$expected_profile" "$compose_commands_file"; then
        printf 'Captured Compose commands for failed scope assertion:\n' >&2
        tail -n 20 "$compose_commands_file" >&2
        fail "$label did not target $expected_profile services"
    fi
}

test_immutable_release_runner
test_verified_jenkins_source_materializer
test_missing_runtime_root
test_missing_shared_nginx_ssl_parameters
test_deploy_script_defers_rollback_to_verified_runner
test_rollback_only_stops_candidate_before_restoring_previous_release
test_stop_only_stops_the_full_profile_without_nginx
test_forced_command_rejects_untrusted_input

reset_captures
run_deploy dev "$missing_master_no_newline_env_file" "MASTER_AI_WORKER_API_KEY" \
    "" "MASTER_AI_WORKER_API_KEY" ""
assert_successful_scope "dev deployment with a blank inherited inactive key" "yes" "dev"
if grep -Fq -- 'backend-master' "$compose_commands_file"; then
    fail "dev deployment must not target master services"
fi

reset_captures
run_deploy dev "$missing_master_no_newline_env_file" "MASTER_AI_WORKER_API_KEY" \
    "" "COMPOSE_PROJECT_NAME" "foreign-stack"
assert_successful_scope "dev deployment with an inherited foreign Compose project name" "yes" "dev"

reset_captures
run_deploy dev "$empty_master_env_file" "MASTER_AI_WORKER_API_KEY"
assert_successful_scope "dev deployment with an empty inactive key in the env file" "yes" "dev"

reset_captures
run_deploy master "$missing_dev_env_file" "DEV_AI_WORKER_API_KEY"
assert_successful_scope "master deployment" "yes" "master"

reset_captures
run_deploy dev "$dev_only_env_file" "MASTER_AI_WORKER_API_KEY"
assert_successful_scope "dev deployment with every master variable absent" "yes" "dev"

reset_captures
run_deploy master "$master_only_env_file" "DEV_AI_WORKER_API_KEY"
assert_successful_scope "master deployment with every dev variable absent" "yes" "master"

reset_captures
run_deploy dev "$missing_master_no_newline_env_file" "MASTER_AI_WORKER_API_KEY" \
    "" "" "" "1"
grep -Fq -- 'ps -aq --filter name=^/eyesonu-nginx$' "$docker_engine_commands_file" \
    || fail "profile deployment must check whether the shared Nginx is already running"
if grep -Fq -- '--no-deps --wait --wait-timeout 180 nginx' "$compose_commands_file"; then
    fail "profile deployment must not recreate a shared running Nginx container"
fi
if grep -Fq -- 'nginx -s reload' "$compose_commands_file"; then
    fail "profile deployment must not reload shared Nginx from a profile release"
fi

set +e
reset_captures
run_deploy dev "$missing_master_no_newline_env_file" "MASTER_AI_WORKER_API_KEY" \
    "$temp_root/unhealthy-nginx.log" "DEPLOY_TEST_NGINX_STATE" "running|unhealthy" "1"
unhealthy_nginx_exit=$?

reset_captures
run_deploy dev "$missing_master_no_newline_env_file" "MASTER_AI_WORKER_API_KEY" \
    "$temp_root/mismounted-nginx.log" "DEPLOY_TEST_NGINX_MOUNT_MISMATCH" "1" "1"
mismounted_nginx_exit=$?
set -e

[[ $unhealthy_nginx_exit -ne 0 ]] \
    || fail "profile deployment must reject an unhealthy shared Nginx container"
grep -Fq 'shared Nginx must be running and healthy' "$temp_root/unhealthy-nginx.log" \
    || fail "unhealthy shared Nginx failure must identify the health gate"
[[ $mismounted_nginx_exit -ne 0 ]] \
    || fail "profile deployment must reject a shared Nginx runtime mount mismatch"
grep -Fq 'shared Nginx mount mismatch for /etc/nginx/conf.d' "$temp_root/mismounted-nginx.log" \
    || fail "shared Nginx mount mismatch failure must identify the affected mount"

set +e
reset_captures
run_deploy dev "$missing_dev_env_file" "" "$temp_root/missing-dev.log" \
    "DEV_AI_WORKER_API_KEY" "unexpected-parent-value"
missing_dev_exit=$?

reset_captures
run_deploy master "$missing_master_env_file" "" "$temp_root/missing-master.log" \
    "MASTER_AI_WORKER_API_KEY" ""
missing_master_exit=$?
set -e

[[ $missing_dev_exit -ne 0 ]] || fail "the active dev API key must not be satisfied by an inherited value"
grep -Fq 'DEV_AI_WORKER_API_KEY' "$temp_root/missing-dev.log" \
    || fail "active-profile failure did not identify the dev API key"
[[ $missing_master_exit -ne 0 ]] || fail "the active master API key must remain required after inherited values are cleared"
grep -Fq 'MASTER_AI_WORKER_API_KEY' "$temp_root/missing-master.log" \
    || fail "active-profile failure did not identify the master API key"

echo "PASS: verified deployment, profile isolation, and active-secret enforcement are covered"
