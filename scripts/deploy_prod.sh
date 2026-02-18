#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/domens}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.nginx.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-domens}"

if docker info >/dev/null 2>&1; then
  USE_SUDO_DOCKER=0
elif sudo -n docker info >/dev/null 2>&1; then
  USE_SUDO_DOCKER=1
else
  echo "Docker is not accessible for current user and sudo -n docker is unavailable."
  exit 1
fi

dcompose() {
  if [[ "$USE_SUDO_DOCKER" -eq 1 ]]; then
    sudo -n docker compose "$@"
  else
    docker compose "$@"
  fi
}

cd "$APP_DIR"

git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

dcompose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" up -d --build --remove-orphans

if [[ "$USE_SUDO_DOCKER" -eq 1 ]]; then
  sudo -n docker image prune -f >/dev/null 2>&1 || true
else
  docker image prune -f >/dev/null 2>&1 || true
fi

echo "Deploy complete at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
