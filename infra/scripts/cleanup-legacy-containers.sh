#!/usr/bin/env sh
set -eu

# Removes only the legacy names used by the previous Jenkinsfile.
# It deliberately does not remove volumes or images.
legacy_names="
  eyesforu-backend
  eyesforu-backend-dev
  eyesforu-backend-prod
  eyesforu-frontend
  eyesforu-frontend-dev
  eyesforu-frontend-prod
  eyesforu-frontend-reporter
  eyesforu-frontend-reporter-dev
  eyesforu-frontend-reporter-prod
"

for name in $legacy_names; do
  if docker container inspect "$name" >/dev/null 2>&1; then
    echo "Removing legacy container: $name"
    docker rm --force "$name"
  fi
done
