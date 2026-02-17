# Domens MVP

MVP-сервис для поиска/отслеживания востребованных доменных имен:
- свободных (`available`)
- освобождающихся (`pendingDelete`)
- не продленных / в риске освобождения

С уведомлением в Telegram и подтверждаемой регистрацией через API регистратора.

## Что в репозитории
- `docs/db_schema.sql` — схема PostgreSQL
- `docs/api_contracts.md` — API-контракты между модулями и внешними клиентами
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

## Telegram flow (MVP)
1. Сервис находит домен-кандидат.
2. Создает алерт с токеном подтверждения.
3. Отправляет сообщение в Telegram с кнопками:
   - `Пропустить`
   - `Зарегистрировать`
4. При нажатии `Зарегистрировать` идет callback на backend.
5. Backend создает задачу регистрации через API регистратора и присылает результат.

## Ограничения MVP
- Хранилище сейчас in-memory для быстрого старта API.
- Полная SQL-схема дана в `docs/db_schema.sql` и готова для миграций.
