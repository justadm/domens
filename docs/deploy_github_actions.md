# Deploy to VPS via GitHub Actions

## 1) DNS and domain
1. Create a temporary subdomain, e.g. `domens.dev.example.com`.
2. Point `A` record to your VPS public IP.
3. Open ports `80` and `443` on VPS firewall/security group.

## 2) Server bootstrap (once)
```bash
sudo mkdir -p /opt/domens
sudo chown -R $USER:$USER /opt/domens
cd /opt/domens
git clone git@github.com:justadm/domens.git .
cp .env.example .env
```

Set in `/opt/domens/.env` at minimum:
- `APP_ENV=prod`
- `APP_DOMAIN=domens.dev.example.com`
- `POSTGRES_PASSWORD=<strong password>`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`
- provider credentials (Timeweb/Selectel/Reg.ru)

Then first run (nginx mode for shared servers):
```bash
cd /opt/domens/deploy
sudo -n docker compose -p domens -f docker-compose.nginx.yml up -d --build
```

## 3) GitHub repository secrets
Add these secrets in GitHub -> Settings -> Secrets and variables -> Actions:
- `DEPLOY_HOST` - VPS IP or hostname
- `DEPLOY_PORT` - usually `22`
- `DEPLOY_USER` - SSH user on VPS
- `DEPLOY_APP_DIR` - `/opt/domens`
- `DEPLOY_SSH_PRIVATE_KEY` - private key that has access to VPS
- `DEPLOY_COMPOSE_FILE` - optional, default `deploy/docker-compose.nginx.yml`
- `DEPLOY_COMPOSE_PROJECT` - optional, default `domens`

## 4) Automatic deploy
Push to `main`.
Workflow `.github/workflows/deploy.yml` will SSH into server and run:
```bash
COMPOSE_FILE=deploy/docker-compose.nginx.yml COMPOSE_PROJECT=domens bash /opt/domens/scripts/deploy_prod.sh
```

## 5) Telegram auth/webhook notes
- Telegram Login Widget requires public HTTPS domain set in BotFather `/setdomain`.
- For webhook mode set `WEBHOOK_URL=https://domens.dev.example.com/v1/telegram/webhook`.
- For local dev keep polling mode.
