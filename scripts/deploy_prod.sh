#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/domens}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.prod.yml}"

cd "$APP_DIR"

git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans

docker image prune -f >/dev/null 2>&1 || true

echo "Deploy complete at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
