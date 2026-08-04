#!/usr/bin/env bash
set -Eeuo pipefail

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
umask 077

original_command="${SSH_ORIGINAL_COMMAND:-}"
command_name=""
profile=""
commit=""
extra=""

IFS=' ' read -r command_name profile commit extra <<< "$original_command"
[[ "$command_name" == "eyesonu-deploy" && -n "$profile" && -n "$commit" && -z "$extra" ]] || {
    echo "ERROR: deployment SSH key only accepts: eyesonu-deploy <dev|master> <full-commit>" >&2
    exit 126
}
case "$profile" in
    dev|master) ;;
    *)
        echo "ERROR: deployment SSH key received an unsupported profile." >&2
        exit 126
        ;;
esac
[[ "$commit" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || {
    echo "ERROR: deployment SSH key received an invalid commit ID." >&2
    exit 126
}

exec /usr/bin/sudo -n /usr/local/libexec/eyesonu-run-deployment "$commit" "$profile"
