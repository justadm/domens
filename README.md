# Domens MVP

MVP-сервис для поиска/отслеживания востребованных доменных имен:
- свободных (`available`)
- освобождающихся (`pendingDelete`)
- не продленных / в риске освобождения

С уведомлением в Telegram и подтверждаемой регистрацией через API регистратора.

## Что в репозитории
- `docs/db_schema.sql` — схема PostgreSQL
- `docs/api_contracts.md` — API-контракты между модулями и внешними клиентами
- `docs/domain_base_strategy.md` — как собирать релевантную базу доменов
- `docs/telegram_bot_scope.md` — продуктовый scope Telegram-бота (команды, дисклеймер, подписки, этапы)
- `docs/telegram_local_and_prod_runbook.md` — как переключить Telegram с локального polling на прод webhook (IP/домен/HTTPS)
- `docs/copilot_feature.md` — свободные обращения клиента (вопрос/чат/действия с подтверждением) + детальный аудит
- `docs/llm_nlu_runbook.md` — подключение LLM для intent parsing (Ollama + fallback), безопасные ограничения
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

## Запуск в Docker
```bash
cd /Users/just/projects/domens
cp .env.example .env
docker compose up --build -d
```

Проверка:
- API: http://127.0.0.1:8080/health
- Swagger: http://127.0.0.1:8080/docs
- Web UI: http://127.0.0.1:8080/

## Прод: VPS + поддомен + автодеплой из GitHub
- Nginx mode (for busy servers with shared 80/443): `deploy/docker-compose.nginx.yml`
- Прод compose: `deploy/docker-compose.prod.yml`
- Reverse proxy/HTTPS: `deploy/Caddyfile`
- Deploy script на сервере: `scripts/deploy_prod.sh`
- GitHub Actions workflow: `.github/workflows/deploy.yml`
- Пошаговая инструкция: `docs/deploy_github_actions.md`

Кратко:
1. Подними временный поддомен 3-го уровня (например `domens.dev.example.com`) на IP VPS.
2. На сервере разверни репозиторий в `/opt/domens` и заполни `/opt/domens/.env`.
3. Добавь GitHub secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_PRIVATE_KEY`, ...).
4. Любой push в `main` автоматически выполняет деплой по SSH.

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
- Базовые роли: `viewer`, `operator`, `admin`, `superadmin`.
- `TELEGRAM_ADMIN_USER_IDS` при старте синхронизируется в роль `admin` (backward compatibility).
- Админ API:
  - `GET /v1/admin/roles`
  - `GET /v1/admin/users`
  - `GET /v1/admin/access-events`
  - `POST /v1/admin/grant`
  - `POST /v1/admin/revoke`
- Доступ к `/v1/admin/*`: только для пользователей с ролью `admin|superadmin` (или env admin fallback).

## Copilot (MVP+)
- Endpoints:
  - `POST /v1/copilot/message`
  - `POST /v1/copilot/confirm`
- Свободный текст от клиента обрабатывается по интентам и confidence.
- Изменяющие действия (`watch`, `alerts`, `register`) выполняются только после явного подтверждения.
- Веб-интерфейс: кнопки `Задать вопрос` и `Просто поговорить` + блок подтверждения.
- Веб-интерфейс: кнопка `Отправить` + блок подтверждения.
- Telegram/MAX паритет для Copilot:
  - Telegram: `/ask`, `/chat`, `/confirm <cp_token>`, `/cancel <cp_token>`
  - MAX: `/ask`, `/chat`, `/confirm <cp_token>`, `/cancel <cp_token>`
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
  - см. `docs/llm_nlu_runbook.md`

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
- Фоновый мониторинг включен по умолчанию (`MONITOR_ENABLED=true`).
- Кандидаты строятся из `MONITOR_SEED_WORDS x MONITOR_TLDS`.
- Фильтр алертов по статусам задается `MONITOR_ALERT_STATUSES` (рекомендуется `available,pending_delete`).
- Строгая проверка через API провайдера: `MONITOR_REQUIRE_PROVIDER_CHECK=true` (без эвристических алертов).
- Админ-копии алертов в Telegram: `TELEGRAM_ADMIN_USER_IDS` (список user_id через запятую).
- Алерты отправляются в Telegram и/или MAX (если настроены chat id).
- Ручной запуск цикла:
```bash
curl -X POST http://127.0.0.1:8080/v1/monitoring/run-once
```

## Ограничения MVP
- Хранилище сейчас in-memory для быстрого старта API.
- Полная SQL-схема дана в `docs/db_schema.sql` и готова для миграций.
