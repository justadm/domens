# План реализации: Frontend отдельно (Vue), Backend отдельно (FastAPI)

Дата: 2026-02-19

## Статус на 2026-02-19

- Этап 1: выполнен.
- Этап 2: выполнен для ключевых разделов LK/Admin:
  - LK: `/lk/watch`, `/lk/alerts`, `/lk/history` переведены на реальные `/v1/cabinet/*` API.
  - LK: добавлены `/lk/domens` и `/lk/orders` (фильтры, поиск, пагинация) через новые API:
    - `GET /v1/cabinet/domains`
    - `GET /v1/cabinet/orders`
  - LK: добавлены детальные страницы:
    - `GET /v1/cabinet/domains/{domain_id}`
    - `POST /v1/cabinet/domains/{domain_id}/recheck`
    - `GET /v1/cabinet/orders/{order_id}`
    - `POST /v1/cabinet/orders/{order_id}/execute`
    - `POST /v1/cabinet/orders/{order_id}/cancel`
  - Admin: `/admin/users`, `/admin/events` переведены на реальные `/v1/admin/*` API + CSV export.
- Этап 3: выполнен (split nginx + frontend container `28200` в проде).
- Этап 4: в работе (legacy frontend backend пока оставлен как fallback).

## Цель

Перейти от встроенного frontend (`web/*` в backend) к классической схеме:
- `backend` = API + webhooks + workers
- `frontend` = отдельное SPA-приложение (Vue 3 + Vite)

Сохранить стабильный прод, предсказуемый rollback и отсутствие конфликтов с соседними проектами.

## Текущий baseline (domens)

- Backend prod: `127.0.0.1:28080` (`domens-api` container:8080)
- Frontend prod: `127.0.0.1:28200` (reserved)
- Public domain: `idns.devee.ru`
- Shared nginx entrypoint: `80/443`

## Архитектурная схема после миграции

- `idns.devee.ru/` и SPA-маршруты (`/lk/*`, `/admin/*`) -> frontend (`127.0.0.1:28200`)
- `idns.devee.ru/v1/*` -> backend (`127.0.0.1:28080`)
- `idns.devee.ru/docs`, `idns.devee.ru/openapi.json`, `idns.devee.ru/health` -> backend

Примечание:
- На первом этапе backend legacy html-роуты можно оставить как fallback.
- На втором этапе выключить legacy frontend в backend.

## Этапы

## Этап 0. Infra подготовка

1. Зафиксировать порты в `docs/PORT_REGISTRY.md`.
2. Подготовить nginx split-конфиг (см. `docs/34_nginx_split_frontend_backend_runbook.md`).
3. Убедиться, что frontend порт `28200` свободен.

Критерий готовности:
- Порт и nginx-план согласованы, rollback-путь описан.

## Этап 1. Каркас frontend

1. Поддерживать отдельный проект `frontend/` (Vue 3 + TS + Pinia + Router).
2. Единый shell для LK/Admin.
3. RBAC меню/роут-guard по capabilities из `/v1/auth/me`.

Критерий готовности:
- Навигация работает, layout единый, страницы рендерятся без backend-html.

## Этап 2. Миграция API-интеграции

1. Перенести auth/session в SPA:
   - `GET /v1/auth/me`
   - `POST /v1/auth/logout`
2. Перенести LK страницы:
   - `/lk` dashboard
   - `/lk/watch`
   - `/lk/alerts`
   - `/lk/registrations`
   - `/lk/history`
3. Перенести Admin страницы:
   - `/admin` dashboard
   - `/admin/users`
   - `/admin/events`
4. Единый API-client:
   - 401/403 обработка
   - retry только для idempotent GET
   - trace/correlation-id (если нужно)

Критерий готовности:
- SPA использует только API (`/v1/*`), без зависимости от backend html.

## Этап 3. Прод переключение nginx

1. Поднять frontend сервис на `127.0.0.1:28200`.
2. Обновить nginx:
   - `/v1/*` + `docs/openapi/health` -> backend `28080`
   - остальное -> frontend `28200`
3. Прогнать smoke-checks.

Критерий готовности:
- UI отдается frontend-сервисом, API/webhooks стабильны.

## Этап 4. Декомиссия legacy frontend в backend

1. Удалить/выключить backend HTML routes (`/`, `/lk`, `/admin` статик) после стабилизации.
2. Удалить legacy static JS/CSS из `web/`.
3. Обновить e2e/smoke тесты под split-архитектуру.

Критерий готовности:
- Backend содержит API/webhooks/workers, frontend полностью вынесен.

## Риски и mitigation

1. Риск: конфликт маршрутов SPA и API.
- Mitigation: backend только под `/v1/*` и служебные `docs/openapi/health`.

2. Риск: сломать Telegram/MAX webhook.
- Mitigation: отдельные smoke на `/v1/telegram/webhook` и `/v1/max/webhook`.

3. Риск: кэш old frontend.
- Mitigation: cache-bust и deploy smoke c проверкой версии ассетов.

4. Риск: портовые конфликты shared host.
- Mitigation: использовать только закрепленные порты (`28080`, `28200`) и проверку `ss -ltnp`.

## Rollback

1. Вернуть nginx route `location /` обратно на backend `28080`.
2. Reload nginx.
3. Отключить frontend сервис `28200`.
4. Проверить `/health`, `/v1/auth/me`, `/admin`.

## Definition of Done

- Frontend и backend деплоятся независимо.
- UI не зависит от backend HTML.
- API/webhooks стабильны.
- Документация портов/deploy/rollback актуальна.
