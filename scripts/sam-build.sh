#!/usr/bin/env bash
# Build SAM project with container support.
# Copies src/backend/app/ into src/lambdas/ temporarily so the container can see it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAMBDAS_DIR="$REPO_ROOT/src/lambdas"
APP_COPY="$LAMBDAS_DIR/app"

cleanup() { rm -rf "$APP_COPY"; }
trap cleanup EXIT

# Copy backend app/ into lambdas/ for container mount
cp -r "$REPO_ROOT/src/backend/app" "$APP_COPY"

# Build
cd "$REPO_ROOT/infra"
DOCKER_HOST="${DOCKER_HOST:-unix://$HOME/.docker/run/docker.sock}" \
  sam build --use-container "$@"
