# Prod checklist: idns.devee.ru

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
- `WEBHOOK_URL=https://idns.devee.ru/v1/telegram/webhook`
- `TELEGRAM_POLLING_ENABLED=false`
- `REGISTRATION_ENABLED=false` (safe mode)
- `REGISTRATION_REQUIRE_AVAILABLE_CHECK=true`
- `MONITOR_REQUIRE_PROVIDER_CHECK=true`
- `TELEGRAM_ADMIN_USER_IDS=13903713`

## 4) First run (nginx mode on msk)
```bash
cd /opt/domens/deploy
sudo -n docker compose -p domens -f docker-compose.nginx.yml up -d --build
sudo -n docker compose -p domens -f docker-compose.nginx.yml ps
```

Why not `docker-compose.prod.yml`:
- `80/443` are already occupied by host nginx on `msk`;
- use host nginx vhost `idns.devee.ru` -> `127.0.0.1:28080`.

## 5) Telegram domain + webhook
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
- `/watch seed`
- ensure alerts are coming without noisy false positives.

## 8) Switch to real registration later
Only after final validation:
- set `REGISTRATION_ENABLED=true`
- restart API service.

Rollback:
- set `REGISTRATION_ENABLED=false`
- restart API service.
