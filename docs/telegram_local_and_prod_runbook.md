# Telegram: локалка -> прод (IP/Domain)

Этот runbook нужен, чтобы без потерь перейти с локального режима (long polling) на прод-режим (webhook по HTTPS).

## 1. Локальный режим (MacBook, без публичного домена)
Используется long polling через `getUpdates`.

### Что должно быть в `.env`
```env
TELEGRAM_BOT_TOKEN=<bot_token>
TELEGRAM_BOT_USERNAME=<bot_username>

TELEGRAM_POLLING_ENABLED=true
TELEGRAM_POLLING_TIMEOUT_SECONDS=25
TELEGRAM_POLLING_ALLOWED_UPDATES=message,callback_query
```

### Как проверить
```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```
Ожидаемо для polling:
- `url` пустой (`"url":""`)
- `allowed_updates` содержит `message,callback_query`

## 2. Прод-режим (домен + HTTPS)
Для Telegram webhook обязательно нужен **публичный HTTPS URL**.

### Предусловия
- Есть домен (например `domens.example.com`).
- DNS A/AAAA указывает на прод-IP.
- На сервере поднят HTTPS (Nginx/Caddy/Traefik + валидный TLS сертификат).
- Приложение доступно извне по URL:
  - `https://domens.example.com/v1/telegram/webhook`

### Что переключить в `.env` на проде
```env
TELEGRAM_BOT_TOKEN=<bot_token>
TELEGRAM_BOT_USERNAME=<bot_username>

TELEGRAM_POLLING_ENABLED=false
```

### Установить webhook
```bash
TOKEN="<bot_token>"
WEBHOOK_URL="https://domens.example.com/v1/telegram/webhook"

curl -s "https://api.telegram.org/bot${TOKEN}/setWebhook?url=${WEBHOOK_URL}"
curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

Ожидаемо для webhook:
- `url` заполнен
- `last_error_message` пустой
- `pending_update_count` не растет постоянно

## 3. Быстрый rollback на polling
Если webhook на проде временно недоступен:

1. В `.env`:
```env
TELEGRAM_POLLING_ENABLED=true
```
2. Перезапуск сервиса.
3. Проверка:
```bash
curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```
После старта polling сервис делает `deleteWebhook`, и `url` должен стать пустым.

## Current stage delivery mode

As of 2026-06-12, MSK stage uses Telegram polling:

- `TELEGRAM_POLLING_ENABLED=true`
- Telegram `getWebhookInfo.url` is empty
- `WEBHOOK_URL` may remain configured in `.env`, but it is ignored while polling is enabled
- `/help`, `/profile`, and `/watch list` are observed in `bot_events`

Before product launch, choose one production mode:
- polling: simpler behind custom routing, webhook stays empty;
- webhook: lower idle API traffic, requires stable public Telegram delivery to `https://idns.devee.ru/v1/telegram/webhook`.

## 4. Чеклист перед релизом
1. `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME` корректны.
2. Прод-домен резолвится на нужный IP.
3. HTTPS сертификат валиден.
4. `https://<domain>/health` отдает `200`.
5. `setWebhook` выполнен успешно.
6. `/start` и `/help` отвечают в реальном Telegram-чате.

## Stage smoke after routing changes
Run on MSK:

```bash
cd /opt/domens
ADMIN_CHAT_ID=<admin_chat_id> ./scripts/smoke_telegram_stage.sh
```

Expected:
- host `getMe` succeeds;
- `domens-api-1` can open TCP to `api.telegram.org:443`;
- webhook URL matches the chosen delivery mode: empty for polling, `https://idns.devee.ru/v1/telegram/webhook` for webhook;
- optional admin `sendMessage` succeeds.

## 5. Частые ошибки
- `chat not found`: бот пишет в неверный chat id или пользователь/чат не стартовал бота.
- `url=""` при `TELEGRAM_POLLING_ENABLED=false`: webhook не установлен.
- Нет ответов на `/start` при webhook: нет публичного HTTPS или endpoint недоступен извне.
