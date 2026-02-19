# Nginx Runbook: Split Frontend and Backend (domens)

Дата: 2026-02-19

Цель для `idns.devee.ru`:
- `/v1/*` -> backend `127.0.0.1:28080`
- `/docs`, `/openapi.json`, `/health` -> backend `127.0.0.1:28080`
- `/` и SPA-маршруты (`/lk/*`, `/admin/*`) -> frontend `127.0.0.1:28200`

## 0) Preconditions

1. Backend работает на `127.0.0.1:28080`.
2. Frontend сервис поднят и отвечает на `127.0.0.1:28200`.
3. Есть `sudo -n`.

## 1) Backup текущего vhost

```bash
sudo -n cp /etc/nginx/sites-available/idns.devee.ru /etc/nginx/sites-available/idns.devee.ru.bak.$(date +%Y%m%d%H%M%S)
```

## 2) Replace `/etc/nginx/sites-available/idns.devee.ru`

```nginx
server {
    listen 80;
    server_name idns.devee.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name idns.devee.ru;

    ssl_certificate /etc/letsencrypt/live/devee.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/devee.ru/privkey.pem;

    access_log /var/log/nginx/idns.devee.ru.access.log;
    error_log /var/log/nginx/idns.devee.ru.error.log;

    # Backend API
    location /v1/ {
        proxy_pass http://127.0.0.1:28080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }

    # Backend service routes
    location = /docs {
        proxy_pass http://127.0.0.1:28080/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /openapi.json {
        proxy_pass http://127.0.0.1:28080/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://127.0.0.1:28080/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend SPA
    location / {
        proxy_pass http://127.0.0.1:28200;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 180s;
    }
}
```

## 3) Validate + reload

```bash
sudo -n nginx -t
sudo -n systemctl reload nginx
```

## 4) Smoke checks

```bash
curl -fsS https://idns.devee.ru/
curl -fsS https://idns.devee.ru/lk
curl -fsS https://idns.devee.ru/admin
curl -fsS https://idns.devee.ru/health
curl -fsS https://idns.devee.ru/v1/auth/me
curl -fsS https://idns.devee.ru/docs
```

Webhook checks (non-destructive):
```bash
curl -fsS https://idns.devee.ru/v1/telegram/webhook -X POST -H 'Content-Type: application/json' -d '{}' || true
curl -fsS https://idns.devee.ru/v1/max/webhook -X POST -H 'Content-Type: application/json' -d '{}' || true
```

## 5) Rollback

```bash
sudo -n cp /etc/nginx/sites-available/idns.devee.ru.bak.<TIMESTAMP> /etc/nginx/sites-available/idns.devee.ru
sudo -n nginx -t
sudo -n systemctl reload nginx
```
