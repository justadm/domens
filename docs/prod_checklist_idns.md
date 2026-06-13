# Prod checklist: idns.devee.ru

Before enabling monitoring or registration, follow `docs/product_launch_runbook.md`.

## 1) DNS and network
- A record: `idns.devee.ru -> 85.239.44.49`
- Open ports: `22`, `80`, `443`

Checks:
```bash
dig +short idns.devee.ru
nc -zv 85.239.44.49 80
nc -zv 85.239.44.49 443
```

## 2) Server bootstrap (one-time)
```bash
sudo adduser deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/domens
sudo chown -R deploy:deploy /opt/domens
```

## 3) Project and environment
```bash
sudo -u deploy git clone git@github.com:justadm/domens.git /opt/domens
sudo -u deploy cp /opt/domens/.env.example /opt/domens/.env
```

Required values in `/opt/domens/.env`:
- `APP_ENV=prod`
- `APP_DOMAIN=idns.devee.ru`
- `POSTGRES_PASSWORD=<strong password>`
- `TELEGRAM_BOT_TOKEN=...`
- `TELEGRAM_BOT_USERNAME=...`
- choose Telegram delivery mode:
  - polling: `TELEGRAM_POLLING_ENABLED=true`, webhook URL empty;
  - webhook: `TELEGRAM_POLLING_ENABLED=false`, `WEBHOOK_URL=https://idns.devee.ru/v1/telegram/webhook`.
- `REGISTRATION_ENABLED=false` (safe mode)
- `REGISTRATION_REQUIRE_AVAILABLE_CHECK=true`
- `MONITOR_ENABLED=false` (safe first run)
- `MONITOR_REQUIRE_PROVIDER_CHECK=true`
- conservative alert limits before canary:
  - `MONITOR_ALERT_GLOBAL_RUN_LIMIT=3`
  - `MONITOR_ALERT_PER_TARGET_RUN_LIMIT=1`
  - `MONITOR_ALERT_PER_TARGET_DAILY_LIMIT=3`
  - `MONITOR_ALERT_COOLDOWN_MINUTES=1440`
- first canary safety flags:
  - `MONITOR_WATCHLIST_ONLY=true`
  - `MONITOR_ADMIN_FANOUT_ENABLED=false`
  - `MONITOR_EVENT_LOGGING_ENABLED=true`
- `TELEGRAM_ADMIN_USER_IDS=13903713`

## 4) First run (nginx mode on msk)
```bash
cd /opt/domens/deploy
sudo -n docker compose -p domens -f docker-compose.nginx.yml up -d --build
sudo -n docker compose -p domens -f docker-compose.nginx.yml ps
```

Why not `docker-compose.prod.yml`:
- `80/443` are already occupied by host nginx on `msk`;
- use host nginx vhost `idns.devee.ru` -> `127.0.0.1:28080` for API paths and `127.0.0.1:28200` for the SPA.

Expected compose services in nginx mode:
- `api`
- `frontend`
- `postgres`
- `redis`

## 5) Telegram delivery mode
Choose Telegram delivery mode before launch:
- Polling mode: `TELEGRAM_POLLING_ENABLED=true`, Telegram `getWebhookInfo.url` empty.
- Webhook mode: `TELEGRAM_POLLING_ENABLED=false`, webhook URL set to `https://idns.devee.ru/v1/telegram/webhook`.

Polling mode is acceptable for launch while Telegram egress from MSK is routed through the non-RU uplink and the bot answers command smoke tests.

### Webhook mode setup
In BotFather:
- `/setdomain` -> `idns.devee.ru`

Set webhook:
```bash
curl -s "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://idns.devee.ru/v1/telegram/webhook"
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Expected:
- `url` is set to `https://idns.devee.ru/v1/telegram/webhook`
- no `last_error_message`

### Polling mode setup
Ensure webhook is empty:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Expected:
- `url` is empty
- `pending_update_count` does not grow after commands are processed

## 6) GitHub Actions deploy secrets
Set in GitHub repository settings:
- `DEPLOY_HOST=85.239.44.49`
- `DEPLOY_PORT=22`
- `DEPLOY_USER=opsadmin` (or your deploy user)
- `DEPLOY_APP_DIR=/opt/domens`
- `DEPLOY_SSH_PRIVATE_KEY=<private key for deploy user>`
- `DEPLOY_COMPOSE_FILE=deploy/docker-compose.nginx.yml`
- `DEPLOY_COMPOSE_PROJECT=domens`

## 7) Smoke tests after deploy
```bash
curl -s https://idns.devee.ru/health
curl -s https://idns.devee.ru/v1/auth/telegram/widget-config
```

Telegram checks:
- `/start`
- `/help`
- `/profile`
- `/menu`
- `/watch list`
- `ADMIN_CHAT_ID=<admin_chat_id> ./scripts/smoke_telegram_stage.sh`
- ensure alerts are coming without noisy false positives.
- while canary is active, inspect monitor audit events:

```bash
ssh msk 'docker exec -i domens-postgres-1 psql -U domens -d domens -c "select created_at,event_type,telegram_chat_id,payload from bot_events where event_type like '\''monitor_%'\'' order by created_at desc limit 50;"'
```

## 8) Switch to real registration later
Only after final validation:
- set `REGISTRATION_ENABLED=true`
- restart API service.

Rollback:
- set `REGISTRATION_ENABLED=false`
- restart API service.
