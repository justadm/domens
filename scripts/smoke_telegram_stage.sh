#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/domens}"
ADMIN_CHAT_ID="${ADMIN_CHAT_ID:-}"

cd "$APP_DIR"

read_env() {
  local key="$1"
  local value

  value="$(awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' .env)"
  value="${value%$'\r'}"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

token="$(read_env TELEGRAM_BOT_TOKEN)"
webhook_url="$(read_env WEBHOOK_URL)"

if [[ -z "$token" ]]; then
  echo "TELEGRAM_BOT_TOKEN is missing"
  exit 1
fi

echo "== Host Telegram API =="
curl -4 -fsS --max-time 15 "https://api.telegram.org/bot${token}/getMe" >/dev/null
echo "host_getMe=ok"

echo "== Container Telegram TCP =="
docker exec domens-api-1 python -c 'import socket; s=socket.create_connection(("api.telegram.org",443),15); s.close(); print("container_tcp=ok")'

echo "== Webhook info =="
curl -4 -fsS --max-time 15 "https://api.telegram.org/bot${token}/getWebhookInfo"
echo

if [[ -n "$webhook_url" ]]; then
  echo "== Backend webhook endpoint =="
  curl -fsS -X POST "$webhook_url" -H 'Content-Type: application/json' -d '{}' >/dev/null
  echo "backend_webhook=ok"
fi

if [[ -n "$ADMIN_CHAT_ID" ]]; then
  echo "== Send message =="
  curl -4 -fsS --max-time 15 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    -H 'Content-Type: application/json' \
    -d "{\"chat_id\":\"${ADMIN_CHAT_ID}\",\"text\":\"Domens Telegram smoke OK\"}" >/dev/null
  echo "sendMessage=ok"
fi
