# Promotion Metrics

Цель: не запускать рекламу вслепую. Каждый пост, личное приглашение, отчет и canary-watchlist должны оставлять след в простой воронке.

## Event Naming

Минимальные события:

- `promotion_touch` - человек увидел или получил приглашение.
- `report_requested` - человек дал нишу/запрос.
- `report_sent` - Domens отправил lead magnet report.
- `watchlist_enabled` - пользователь включил watchlist.
- `digest_sent` - пользователю ушел digest.
- `alert_feedback` - пользователь нажал feedback-кнопку.
- `domain_hidden` - пользователь скрыл домен/корень/TLD.
- `registration_interest` - пользователь спросил или нажал регистрацию.
- `retained_d1` - пользователь вернулся/отреагировал на следующий день.
- `retained_d7` - пользователь активен через 7 дней.

## Mapping To Product Events

Промо-метрики должны быть сверяемы с реальными событиями БД/логов, иначе они не являются launch evidence.

| Promotion event | Product/log source | Notes |
|---|---|---|
| `promotion_touch` | manual tracking / campaign link / bot start payload | Для ручного canary допустима таблица |
| `report_requested` | incoming Telegram message / Copilot message / manual row | Сохранять `source`, `cta`, `segment`, `niche` |
| `report_sent` | bot outbound event / manual row | Отчет должен иметь stable campaign id |
| `watchlist_enabled` | watch rule created / `user_watch_rules` | Связать с `watch_rule_id` |
| `digest_sent` | `monitor_digest_sent` in `bot_events` | Связать с chat/user and campaign if possible |
| `alert_feedback` | feedback callback / alert feedback table | Сохранять `feedback_type` and optional `feedback_reason` |
| `domain_hidden` | suppression created | Причина: `user_less`, `user_never`, root/TLD/domain |
| `registration_interest` | register callback / Copilot register intent | Отдельно от execution while registration disabled |
| `retained_d1` | activity after 24h | Digest open/reply/feedback/watch edit |
| `retained_d7` | activity after 7d | Digest open/reply/feedback/watch edit |

## Required Fields

Каждое событие должно фиксировать:

| Field | Meaning | Example |
|---|---|---|
| `source` | Откуда пришел пользователь | `personal_dm`, `telegram_channel`, `web_studio_ref`, `domainer_chat`, `paid_telegram_ads` |
| `campaign` | Конкретная кампания/пост | `canary_week_1`, `ai_security_digest_01` |
| `cta` | Обещание/призыв | `founder_5_domains`, `studio_client_shortlist`, `domainer_1_digest_day` |
| `segment` | Сегмент | `founder`, `web_studio`, `domainer`, `seo_team`, `agency` |
| `niche` | Ниша пользователя | `AI security SaaS` |
| `tlds` | Запрошенные TLD | `.com,.io,.ai,.ru` |
| `max_length` | Ограничение длины | `14` |
| `daily_limit` | Лимит digest/alert | `1` |
| `telegram_user_id` | ID, если доступен | `13903713` |
| `watch_rule_id` | Правило, если создано | `uuid` |
| `digest_id` | Digest/alert batch | `uuid` |
| `feedback_type` | Реакция | `more`, `less`, `never` |
| `feedback_reason` | Причина обратной связи, если есть | `irrelevant`, `bad_tld`, `trademark_risk` |

## CTA Taxonomy

Использовать стабильные значения:

- `founder_5_domains` - получить 5 доменов под SaaS-нишу.
- `studio_client_shortlist` - получить short-list для клиента.
- `domainer_1_digest_day` - включить 1 digest/day по паттерну/TLD.
- `manual_canary_invite` - ручное приглашение в canary.
- `channel_digest_reply` - ответ на публичный digest.

## Funnel Dashboard

Минимальная таблица по кампании:

| Metric | Definition | Target before ads |
|---|---|---:|
| Touches | `promotion_touch` | 20-50 for canary |
| Report request rate | `report_requested / promotion_touch` | >= 20% |
| Report delivery rate | `report_sent / report_requested` | >= 90% |
| Watchlist activation | `watchlist_enabled / report_sent` | >= 25% |
| Feedback rate | `alert_feedback / digest_sent` | >= 15% |
| Negative feedback rate | `(less + never) / alert_feedback` | Track, not minimize blindly |
| D1 retention | `retained_d1 / watchlist_enabled` | >= 30% |
| D7 retention | `retained_d7 / watchlist_enabled` | >= 15% |
| Repeated spam | Same domain to same destination without meaningful change | 0 |
| Blocked registration attempts | Attempts while `REGISTRATION_ENABLED=false` | 0 unexpected |

## Feedback Reasons

Start with a compact taxonomy:

- `irrelevant` - не попало в нишу;
- `too_expensive` - ожидаемо дорогой TLD/покупка;
- `bad_tld` - TLD не подходит;
- `trademark_risk` - похоже на бренд или риск UDRP;
- `already_seen` - пользователь уже видел похожий паттерн;
- `too_many_alerts` - частота выше ожиданий;
- `bad_name_quality` - плохо читается, generic, weak brandability;
- `provider_status_uncertain` - слабая уверенность источника;
- `other` - нужен текстовый комментарий.

## Manual Tracking Sheet

Until this is automated, keep one row per person/report:

| Date | Source | CTA | Segment | Niche | TLD | Report sent | Watchlist | Digest sent | Feedback | D1 | D7 | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-14 | personal_dm | founder_5_domains | founder | AI security | .ai,.io | yes | yes | 1 | more | yes | pending | Wants global names |

## Rules

- Paid traffic is blocked until metrics are captured for organic/canary traffic.
- A public post without a stable CTA value is not launch evidence.
- Do not optimize only for "more feedback": `less` and `never` are valuable because they reduce noise.
- Keep registration interest separate from registration execution while `REGISTRATION_ENABLED=false`.
