# API Contracts (MVP)

## 1) Domain scan/check

### POST `/v1/domains/check`
Пакетная проверка доменов по доступности/статусу.

Auth: admin session required. This endpoint can trigger provider checks and must not be public.

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

Auth: admin session required.

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

Auth: admin session required. Normal product alerts should be created by the monitoring service, not by public clients.

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

## 7) Copilot (free-form assistant)

### POST `/v1/copilot/message`
Request:
```json
{
  "message": "добавь watch для ai security",
  "mode": "assistant",
  "conversation_id": null,
  "channel": "web"
}
```

Response:
```json
{
  "conversation_id": "uuid",
  "reply": "Понял как создание watch-правила...",
  "intent": "create_watch",
  "confidence": 0.88,
  "requires_confirmation": true,
  "confirmation_token": "cp_xxx",
  "action_preview": {
    "action": "create_watch",
    "query": "ai security",
    "tlds": [".com", ".io", ".ai", ".ru"]
  }
}
```

### POST `/v1/copilot/confirm`
Request:
```json
{
  "confirmation_token": "cp_xxx",
  "decision": "confirm"
}
```

Response:
```json
{
  "status": "executed",
  "message": "Действие выполнено.",
  "execution_result": {
    "rule_id": "uuid",
    "query": "ai security"
  }
}
```

## 8) Cabinet alerts

### GET `/v1/cabinet/alerts`
Auth: user session required.

Returns user-visible alert history with explanations, feedback state, and active suppression state for the user's own alert destinations.

Query:
- `limit` - page size, clamped by the backend.
- `offset` - pagination offset.
- `search` - optional text search across domain, alert type, destination, and explanation payload.
- `feedback` - optional filter by feedback type: `more`, `less`, `never`, or `why`.
- `domains` - optional comma-separated exact FQDN filter, used when opening alert rows linked to a digest.

Response `200`:
```json
{
  "total": 1,
  "limit": 30,
  "offset": 0,
  "next_offset": null,
  "prev_offset": null,
  "items": [
    {
      "id": "alert-uuid",
      "domain_id": "domain-uuid",
      "domain": "assistlab.io",
      "alert_type": "watch_rule_match:rule-uuid",
      "channel": "telegram",
      "channel_target": "7951273850",
      "acknowledged": false,
      "created_at": "2026-06-16T06:04:53+00:00",
      "acknowledged_at": null,
      "provider": "timeweb",
      "provider_status": "available",
      "provider_checked_at": "2026-06-16T06:04:53+00:00",
      "provider_confidence": "provider_checked",
      "explanation": {
        "score": 70,
        "status": "available",
        "provider": "timeweb",
        "matched_query": "assist lab",
        "tld": "io",
        "length": 9,
        "risk": "provider_checked",
        "checked_at": "2026-06-16T06:04:53+00:00"
      },
      "latest_feedback": {
        "type": "less",
        "created_at": "2026-06-16T06:10:00+00:00",
        "payload": {"source": "cabinet"}
      },
      "feedback_counts": {"less": 1},
      "suppression_state": {
        "active": true,
        "reason": "user_less",
        "created_at": "2026-06-16T06:10:00+00:00",
        "expires_at": "2026-09-14T06:10:00+00:00"
      }
    }
  ]
}
```

Source transparency fields are always present in cabinet alert items:
- `provider` - provider/source used for availability context; falls back to `heuristic`.
- `provider_status` - provider/domain status for the alert; falls back to `unknown` when no source check exists.
- `provider_checked_at` - timestamp of the provider/domain-state check, or `null`.
- `provider_confidence` - source quality tier such as `provider_checked`, `heuristic`, `stale`, `rate_limited`, or `unknown`.

### POST `/v1/cabinet/alerts/{alert_id}/feedback`
Auth: user session required.

Records feedback on a user-owned alert. `less` and `never` also create user-level suppressions.

Request:
```json
{
  "feedback_type": "less"
}
```

Response `200`:
```json
{
  "ok": true,
  "alert_id": "alert-uuid",
  "domain": "assistlab.io",
  "feedback": {
    "type": "less",
    "created_at": "2026-06-16T06:10:00+00:00",
    "payload": {"source": "cabinet"}
  }
}
```

### GET `/v1/cabinet/digests`
Auth: user session required.

Returns user-visible Telegram digest history from `monitor_digest_sent` audit events for the user's own alert destinations.

Query:
- `limit` - page size, clamped by the backend.
- `offset` - pagination offset.
- `search` - optional text search across destination and digest payload.

Response `200`:
```json
{
  "total": 1,
  "limit": 30,
  "offset": 0,
  "next_offset": null,
  "prev_offset": null,
  "items": [
    {
      "id": "bot-event-uuid",
      "channel": "telegram",
      "channel_target": "7951273850",
      "created_at": "2026-06-16T06:13:20+00:00",
      "domains": ["catchhub.ru"],
      "items_count": 1,
      "message_id": "614",
      "delivery": {
        "mode": "telegram",
        "chat_id": "7951273850",
        "message_id": "614",
        "items_count": 1
      }
    }
  ]
}
```

## 9) Cabinet preferences

### GET `/v1/cabinet/preferences`
Auth: user session required.

Returns user-visible radar preferences that affect future alerts.

Response `200`:
```json
{
  "watch_rules": [
    {
      "id": "rule-uuid",
      "query": "ai tools",
      "status": "active",
      "daily_alert_limit": 1
    }
  ],
  "suppressions": [
    {
      "id": "suppression-uuid",
      "fqdn": "stackai.ru",
      "reason": "user_never",
      "expires_at": "2027-06-13T09:05:00+00:00"
    }
  ]
}
```

### DELETE `/v1/cabinet/preferences/suppressions/{suppression_id}`
Auth: user session required.

Deletes one user-owned hidden-domain/suppression preference.

Response `200`:
```json
{
  "ok": true,
  "suppression_id": "suppression-uuid"
}
```

## 10) Admin runtime

### GET `/v1/admin/quality`
Auth: admin session required.

Admin quality and launch canary summary for the selected rolling window.

Query:
- `days` - rolling window, clamped to 1..90 days.

Response `200`:
```json
{
  "days": 7,
  "alerts_total": 2,
  "feedback_total": 1,
  "suppressed_total": 3,
  "feedback_ratios": {
    "more": 1,
    "less": 0,
    "never": 0,
    "why": 0,
    "positive_rate": 1.0,
    "negative_rate": 0.0,
    "total": 1
  },
  "monitor_runs_total": 24,
  "monitor_alerts_sent": 1,
  "monitor_digests_sent": 1,
  "monitor_checked_total": 21120,
  "monitor_skip_reasons": {
    "status_not_interesting": 19872,
    "watch_daily_limit": 1248,
    "target_cooldown": 2
  },
  "monitor_duplicate_alert_groups": [
    {
      "destination": "13903713",
      "fqdn": "assistlab.io",
      "count": 2,
      "first_sent_at": "2026-06-17T10:00:00+00:00",
      "last_sent_at": "2026-06-17T12:00:00+00:00"
    }
  ],
  "monitor_duplicate_alert_groups_total": 1,
  "telegram_errors_total": 0,
  "registration_enabled": false,
  "monitor_enabled": true,
  "monitor_watchlist_only": true,
  "monitor_admin_fanout_enabled": false,
  "monitor_alert_target_cooldown_minutes": 360
}
```

### GET `/v1/admin/quality-report.md`
Auth: admin session required.

Download-friendly Markdown snapshot of the same admin quality metrics used by
`/v1/admin/quality`. The endpoint does not recalculate quality independently.

Query:
- `days` - rolling window, clamped by the shared quality metrics service to 1..90 days.

Response `200`:
- `Content-Type: text/markdown; charset=utf-8`
- `Content-Disposition: attachment; filename="domens-quality-report-YYYY-MM-DD.md"`

The report includes:
- window and generation time;
- safety flags;
- totals;
- feedback distribution;
- duplicate groups;
- skip reasons;
- Telegram errors;
- manual go/no-go notes.

### GET `/v1/admin/copilot-runtime`
Admin-only runtime snapshot for Copilot/LLM status.

Response `200`:
```json
{
  "status": {
    "llm_enabled": true,
    "provider": "ollama",
    "model": "qwen2.5:0.5b",
    "intent_model": "qwen2.5:0.5b",
    "reply_model": "qwen2.5:7b-instruct",
    "intent_timeout_seconds": 12,
    "reply_timeout_seconds": 35,
    "fallback_enabled": false,
    "fallback_model": "qwen/qwen2.5-7b-instruct:free",
    "confidence_threshold": 0.65,
    "rate_limit": {
      "window_seconds": 60,
      "requests": 12,
      "tracked_users": 5
    },
    "degrade": {
      "inflight_threshold": 4,
      "current_inflight": 1
    }
  }
}
```

## 10) Admin access events

### GET `/v1/admin/access-events`
Admin-only access audit list with server-side filters and pagination.

Query params:
- `limit` (1..300, default `100`)
- `offset` (>=0, default `0`)
- `action` (optional exact match, example `grant_role`)
- `actor_telegram_user_id` (optional)
- `target_telegram_user_id` (optional)
- `created_from` (optional ISO datetime)
- `created_to` (optional ISO datetime)

Response `200`:
```json
{
  "total": 124,
  "limit": 50,
  "offset": 0,
  "next_offset": 50,
  "prev_offset": null,
  "items": [
    {
      "id": "evt-1",
      "action": "grant_role",
      "role_code": "operator",
      "actor_telegram_user_id": "13903713",
      "target_telegram_user_id": "42",
      "payload": {
        "source": "api"
      },
      "created_at": "2026-02-18T12:00:00+00:00"
    }
  ]
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
