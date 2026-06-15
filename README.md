# Domens MVP

MVP-сервис для поиска/отслеживания востребованных доменных имен:
- свободных (`available`)
- освобождающихся (`pendingDelete`)
- не продленных / в риске освобождения

С уведомлением в Telegram и подтверждаемой регистрацией через API регистратора.

## Что в репозитории
- `docs/db_schema.sql` — схема PostgreSQL
- `docs/api_contracts.md` — API-контракты между модулями и внешними клиентами
- `docs/legal/` — draft privacy/offer/support пакет для closed pilot, требует юридического ревью
- `docs/domain_base_strategy.md` — как собирать релевантную базу доменов
- `docs/telegram_bot_scope.md` — продуктовый scope Telegram-бота (команды, дисклеймер, подписки, этапы)
- `docs/telegram_local_and_prod_runbook.md` — как переключить Telegram с локального polling на прод webhook (IP/домен/HTTPS)
- `docs/copilot_feature.md` — свободные обращения клиента (вопрос/чат/действия с подтверждением) + детальный аудит
- `docs/llm_nlu_runbook.md` — подключение LLM для intent parsing (Ollama + fallback), безопасные ограничения
- `docs/hybrid_llm_mvp_plan.md` — целевая архитектура MVP: `0.5b` для intent, `7b` для chat/qa, state machine и quality gates
- `docs/shared_ollama_multi_project.md` — одна общая Ollama-модель для нескольких проектов, с изоляцией коннекторов
- `app/` — каркас backend (FastAPI)

## Быстрый старт
```bash
cd /Users/just/projects/domens
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8080
```

Swagger:
- http://127.0.0.1:8080/docs

## Frontend (Vue, отдельно от backend)
- Новый фронт-бутстрап находится в `frontend/`.
- Стек: Vue 3 + Vite + Pinia + Vue Router.
- Единый shell для LK/Admin, отличия по RBAC.

Запуск:
```bash
cd /Users/just/projects/domens/frontend
npm install
npm run dev
```

Опционально:
```bash
VITE_API_BASE_URL=https://idns.devee.ru npm run dev
```

План поэтапной миграции со старого `web/`:
- `docs/frontend_vue_migration_plan.md`

## Запуск в Docker
```bash
cd /Users/just/projects/domens
cp .env.example .env
docker compose up --build -d
```

Проверка:
- API: http://127.0.0.1:28080/health
- Swagger: http://127.0.0.1:28080/docs
- Web UI: http://127.0.0.1:28200/

## Прод: VPS + поддомен + деплой из Gitea
- Nginx mode (for busy servers with shared 80/443): `deploy/docker-compose.nginx.yml`
- Прод compose: `deploy/docker-compose.prod.yml`
- Shared Ollama (multi-project): `deploy/docker-compose.shared-ollama.yml`
- Reverse proxy/HTTPS: `deploy/Caddyfile`
- Deploy script на сервере: `scripts/deploy_prod.sh`
- Основной git remote: Gitea `ssh://git@git.devee.ru:65023/just/domens.git`
- GitHub Actions workflow остается резервным путем: `.github/workflows/deploy.yml`
- Пошаговая инструкция: `docs/prod_checklist_idns.md`

Кратко:
1. Подними поддомен на IP VPS.
2. На сервере разверни репозиторий в `/opt/domens` и заполни `/opt/domens/.env`.
3. Проверь safe flags: `REGISTRATION_ENABLED=false`, `MONITOR_WATCHLIST_ONLY=true`, `MONITOR_ADMIN_FANOUT_ENABLED=false`.
4. Деплой:
```bash
ssh msk 'cd /opt/domens && APP_DIR=/opt/domens BRANCH=main COMPOSE_FILE=deploy/docker-compose.nginx.yml COMPOSE_PROJECT=domens bash scripts/deploy_prod.sh'
```

## Make команды
```bash
cd /Users/just/projects/domens
make up
make ps
make db-migrate
make health
make logs
make down
```

## База данных
- В рантайме используется PostgreSQL (без in-memory store).
- Миграции выполняются через Alembic.
- В Docker-режиме `api` выполняет `alembic upgrade head` перед запуском Uvicorn.

## Telegram flow (MVP)
1. Сервис находит домен-кандидат.
2. Создает алерт с токеном подтверждения.
3. Отправляет сообщение в Telegram с кнопками:
   - `Пропустить`
   - `Зарегистрировать`
4. При нажатии `Зарегистрировать` идет callback на backend.
5. Backend автоматически подтверждает и сразу запускает регистрацию через API регистратора.

## RBAC (MVP+)
- В БД добавлены таблицы `roles`, `user_roles`.
- Базовые роли: `viewer`, `operator`, `viewer_admin`, `manager_admin`, `admin`, `superadmin`.
- `TELEGRAM_ADMIN_USER_IDS` при старте синхронизируется в роль `admin` (backward compatibility).
- Админ API:
  - `GET /v1/admin/dashboard` (aggregated service stats for admin page)
  - `GET /v1/admin/roles`
  - `GET /v1/admin/users`
  - `GET /v1/admin/users-activity` (users, registration status, permissions/capabilities + filters/pagination)
  - `GET /v1/admin/users-activity.csv` (CSV export with same filters)
  - `GET /v1/admin/bot-events` (global event stream + filters/pagination)
  - `GET /v1/admin/bot-events.csv` (CSV export with same filters)
  - `GET /v1/admin/access-events` (filters + pagination: `action`, `actor`, `target`, `created_from/to`, `limit/offset`)
  - `POST /v1/admin/grant`
  - `POST /v1/admin/revoke`
- Доступ к `/v1/admin/*`: по permission `admin.panel.read` (роль `admin|superadmin`, либо env admin fallback).
- Runtime status endpoint: `GET /v1/admin/copilot-runtime` (LLM mode, fallback, limits, inflight/degrade state).
- Separate admin web page: `/admin` (dedicated layout, not shared main SPA).
- Dashboard can merge external e-commerce counters via:
  - `ECOM_STATS_ENABLED=true`
  - `ECOM_STATS_BASE_URL=https://<service>`
  - `ECOM_STATS_PATH=/admin/stats`
  - `ECOM_STATS_TOKEN=<bearer>`
  - `ECOM_STATS_TIMEOUT_SECONDS=8`
- `GET /v1/auth/me` and `GET /v1/cabinet/profile` now return both:
  - `permissions[]` (effective permissions),
  - `capabilities{}` (UI-friendly flags, e.g. `admin_panel_read`, `copilot_register_domain`).

## Copilot (MVP+)
- Endpoints:
  - `POST /v1/copilot/message`
  - `POST /v1/copilot/confirm`
- Свободный текст от клиента обрабатывается по интентам и confidence.
- Изменяющие действия (`watch`, `alerts`, `register`) выполняются только после явного подтверждения.
- Для `register` требуется permission `copilot.register_domain` (по умолчанию у `operator|admin|superadmin`).
- Веб-интерфейс: кнопки `Задать вопрос` и `Просто поговорить` + блок подтверждения.
- Веб-интерфейс: кнопка `Отправить` + блок подтверждения.
- Telegram/MAX паритет для Copilot:
  - Telegram: `/ask`, `/chat`, `/confirm <cp_token>`, `/cancel <cp_token>`
  - MAX: `/ask`, `/chat`, `/confirm <cp_token>`, `/cancel <cp_token>`
- Telegram admin команды: `/admin roles|users|access-events|grant|revoke`.
- Язык Copilot-ответов выбирается по `locale` пользователя (`en*` -> EN, иначе RU).
- Веб-язык автоматически подхватывается из `locale` профиля, пока пользователь вручную не сменит язык в селекторе.
- Подробный аудит хранится в таблицах:
  - `conversations`
  - `conversation_messages`
  - `copilot_action_confirmations`
  - `copilot_events`
- Опционально доступен LLM-NLU слой (Ollama/OpenRouter) с fallback на rule-based parser:
  - `COPILOT_LLM_NLU_ENABLED`
  - `COPILOT_LLM_PROVIDER`
  - `COPILOT_LLM_CONFIDENCE_THRESHOLD`
  - `COPILOT_LLM_INTENT_MODEL`, `COPILOT_LLM_REPLY_MODEL`
  - `COPILOT_LLM_INTENT_TIMEOUT_SECONDS`, `COPILOT_LLM_REPLY_TIMEOUT_SECONDS`
  - `COPILOT_LLM_KNOWLEDGE_ENABLED`
  - `COPILOT_LLM_KNOWLEDGE_FILES`
  - `COPILOT_LLM_KNOWLEDGE_MAX_CHARS`
  - `COPILOT_LLM_CHAT_CONTEXT_MESSAGES`
  - `COPILOT_LLM_REPLY_MAX_CHARS`
  - см. `docs/llm_nlu_runbook.md`
  - важно: использовать только один shared runtime Ollama на сервере (host/systemd или docker), см. `docs/shared_ollama_multi_project.md`
  - профиль модели для MVP low-RAM: `qwen2.5:0.5b` (высокое качество: `qwen2.5:7b-instruct`)

## LK без авторизации (опционально)
- Для быстрого входа в кабинет можно включить гостевой режим:
  - `WEB_GUEST_AUTH_ENABLED=true`
  - `WEB_GUEST_USER_ID=<telegram_user_id>`
  - `WEB_GUEST_IS_ADMIN=true|false`
- В этом режиме `/v1/auth/me` возвращает guest-пользователя даже без cookie-сессии.
- В левом меню добавлен пункт `LK` (быстрый переход в кабинет).

## Провайдеры
- Регистратор: Timeweb (`TIMEWEB_API_*`), используется endpoint `POST /api/v1/add-domain/{fqdn}`.
- Резервный регистратор: Reg.ru (`REG_RU_*`) в fallback-цепочке.
- Проверка домена: Timeweb (`GET /api/v1/check-domain/{fqdn}`) с fallback на эвристику.
- DNS reserve: Selectel DNS Hosting (`SELECTEL_*`) через `ensure_zone` при fail основного регистратора.
- Резервный канал уведомлений: MAX (`MAX_*`) + webhook `POST /v1/max/webhook`.

### Защита от случайной покупки
- `REGISTRATION_ENABLED=false` (по умолчанию) блокирует фактическую регистрацию во внешних API.
- Для боевого режима вручную включается `REGISTRATION_ENABLED=true`.
- `REGISTRATION_REQUIRE_AVAILABLE_CHECK=true` выполняет pre-check доступности у регистратора перед попыткой регистрации.

## Мониторинг доменов
- Фоновый мониторинг выключен по умолчанию (`MONITOR_ENABLED=false`).
- Кандидаты строятся из `MONITOR_SEED_WORDS x MONITOR_TLDS`.
- Фильтр алертов по статусам задается `MONITOR_ALERT_STATUSES` (рекомендуется `available,pending_delete`).
- Строгая проверка через API провайдера: `MONITOR_REQUIRE_PROVIDER_CHECK=true` (без эвристических алертов).
- Watchlist-first canary включается через `MONITOR_WATCHLIST_ONLY=true`.
- Админ-фан-аут выключен по умолчанию: `MONITOR_ADMIN_FANOUT_ENABLED=false`.
- Алерты в Telegram группируются в digest при `MONITOR_DIGEST_ENABLED=true`.
- Для одного destination действует cooldown между watchlist-алертами: `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES=360`.
- Ручной запуск цикла требует admin-сессию:
```bash
curl -X POST http://127.0.0.1:28080/v1/monitoring/run-once
```

## Ограничения MVP
- В рантайме используется PostgreSQL.
- Legal package для публичного продвижения еще не готов: нужны privacy policy, offer/agreement, контакты поддержки и условия ответственности.
- Перед публичным запуском нужен зафиксированный 24h canary report по `docs/product_launch_runbook.md`.
