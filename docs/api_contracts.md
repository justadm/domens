# API Contracts (MVP)

## 1) Domain scan/check

### POST `/v1/domains/check`
Пакетная проверка доменов по доступности/статусу.

Request:
```json
{
  "domains": ["brandflow.ai", "paygrid.com"],
  "source": "manual"
}
```

Response `200`:
```json
{
  "results": [
    {
      "domain": "brandflow.ai",
      "status": "pending_delete",
      "score": 87.4,
      "drop_time_estimated_at": "2026-02-19T11:45:00Z"
    },
    {
      "domain": "paygrid.com",
      "status": "registered",
      "score": 79.1,
      "drop_time_estimated_at": null
    }
  ]
}
```

## 2) Candidate ingestion

### POST `/v1/domains/candidates`
Добавление кандидатов (из трендов, словарей, внешних источников).

Request:
```json
{
  "candidates": ["agentdock.io", "ledgerfox.com"],
  "watchlist_id": "wl_main"
}
```

Response `202`:
```json
{
  "accepted": 2
}
```

## 3) Alert creation + Telegram notify

### POST `/v1/alerts/trigger`
Создает алерт и отправляет уведомление в Telegram с кнопками подтверждения.

Request:
```json
{
  "domain": "brandflow.ai",
  "telegram_chat_id": "123456",
  "watchlist_id": "wl_main"
}
```

Response `201`:
```json
{
  "alert_id": "alrt_123",
  "confirmation_token": "cfm_xxx",
  "status": "sent"
}
```

## 4) Registration (manual confirm)

### POST `/v1/registrations/confirm`
Подтверждает регистрацию по токену из Telegram callback.

Request:
```json
{
  "confirmation_token": "cfm_xxx",
  "confirmed_by": "tg:123456"
}
```

Response `200`:
```json
{
  "order_id": "ord_456",
  "domain": "brandflow.ai",
  "status": "queued"
}
```

### POST `/v1/registrations/{order_id}/execute`
Пробует регистрацию через API регистратора.

Response `200`:
```json
{
  "order_id": "ord_456",
  "status": "registered",
  "registrar_response": {
    "provider": "Namecheap",
    "external_order_id": "NC-99881"
  }
}
```

## 5) Telegram webhook

### POST `/v1/telegram/webhook`
Принимает callback на кнопки (`register:<token>`, `skip:<token>`).

Response `200`:
```json
{
  "ok": true
}
```

## 6) Health

### GET `/health`
Проверка состояния API.

Response `200`:
```json
{
  "status": "ok"
}
```

## Module boundaries
- `collector -> checker`:
  - input: список доменов
  - output: статус + confidence + ETA
- `checker -> notifier`:
  - событие `domain.interesting`
- `notifier -> registration`:
  - callback/command from Telegram
- `registration -> registrar adapter`:
  - единый интерфейс `check_availability()` и `register_domain()`
