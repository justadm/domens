# Trust Pack Checklist

Цель: перед публичной рекламой у пользователя должны быть понятные ответы: кто оператор, что происходит с данными, что сервис обещает и чего не обещает.

## Required Public Pages Or Documents

| Item | Status | Notes |
|---|---|---|
| Privacy policy | `missing` / `draft` / `published` | Какие данные Telegram/кабинета хранятся |
| Offer/agreement | `missing` / `draft` / `published` | Условия использования сервиса |
| Registration disclaimer | `missing` / `draft` / `published` | Доступность домена не гарантируется |
| Support contact | `missing` / `draft` / `published` | Telegram/email для вопросов |
| Operator identity | `missing` / `draft` / `published` | Кто оказывает сервис |
| Refund/payment policy | `missing` / `draft` / `published` | Нужен до платных планов |
| Abuse/contact policy | `missing` / `draft` / `published` | Жалобы на домены, TM-риск, данные |
| Search privacy / no-front-running pledge | `missing` / `draft` / `published` | Что происходит с пользовательскими запросами |
| Data deletion path | `missing` / `draft` / `published` | Удалить watchlist, Telegram link, историю запросов |
| Source health disclosure | `missing` / `draft` / `published` | Что значит stale/unknown/rate_limited |

## Minimum Disclaimer

Use this in public posts, bot reports, and registration flows:

```md
Domens показывает доменные сигналы и помогает оценить доступность, но не гарантирует регистрацию домена. Перед покупкой выполняется свежая проверка у регистратора. Решение о регистрации принимает пользователь.
```

## Data Handling Notes

Explain in plain language:

- какие Telegram-данные сохраняются;
- какие watchlist-запросы сохраняются;
- как используются feedback-кнопки;
- когда выполняются provider checks;
- что пользовательские запросы не используются для собственной регистрации/перепродажи;
- как скрыть домен или отключить алерты;
- как запросить удаление данных;
- что LLM/Copilot, если включен, не должен выполнять покупку без подтверждения.

## No-Front-Running Pledge

Public wording:

```md
Domens не использует пользовательские запросы, watchlist или проверки доменов для собственной регистрации, перепродажи или скрытого front-running.
```

Operational checks:

- provider checks are logged with source and timestamp;
- user queries are not reused in owned inventory or resale workflows;
- privacy policy explains retention and deletion;
- support contact can handle deletion requests.

## Registration Safety Notes

Public wording:

```md
Регистрация отключена по умолчанию для canary. Когда регистрация доступна, она требует явного подтверждения и свежей проверки доступности у регистратора.
```

Operational checks:

- `REGISTRATION_ENABLED=false` before public ads;
- `REGISTRATION_REQUIRE_AVAILABLE_CHECK=true`;
- unknown/stale availability blocks execution;
- provider confidence is visible as `provider_checked`, `heuristic`, `stale`, `unknown`, or `rate_limited`;
- registration rollback documented in `docs/product_launch_runbook.md`;
- support contact visible near registration disclaimer.

## Source Health Notes

Public wording:

```md
Иногда источник проверки может быть недоступен или ограничен. В этом случае Domens показывает осторожный статус (`unknown`, `stale` или `rate_limited`) и не должен создавать ощущение, что домен готов к регистрации.
```

Operational checks:

- admin can inspect provider errors/rate limits;
- canary report includes provider health counts;
- `unknown/stale/rate_limited` do not become confident public claims;
- registration flow requires `provider_checked` or equivalent fresh availability confirmation.

## Trademark And Risk Notes

Avoid promising legal safety.

Suggested wording:

```md
Score не является юридической проверкой товарных знаков. Перед коммерческим использованием домена пользователь должен самостоятельно оценить правовые риски.
```

## Before Paid Ads

Paid promotion is blocked until:

- trust pack has at least privacy, offer/agreement, support contact, and registration disclaimer;
- data deletion path is documented;
- source health/provider confidence wording is visible;
- promotion metrics are being tracked;
- 24h canary report has a `keep_on` or explicit `tune_limits` decision;
- bot/channel CTA points to a Telegram bot or channel that can handle incoming users;
- no broad promise of guaranteed availability or automated purchase appears in ad copy.
