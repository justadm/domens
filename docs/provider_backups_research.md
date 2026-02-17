# Backup Providers Research (Selectel / Reg.ru / MAX)

## 1) Selectel DNS Hosting API (reserve)

Официальная документация:
- Общая API DNS Hosting: https://docs.selectel.ru/cloud/dns-hosting/
- Endpoint list (`/zones`, `/zones/{id}`, `/zones/{id}/rrsets`): https://docs.selectel.ru/api/dns-hosting/
- Авторизация токенами (`X-Auth-Token`, `X-Token`) и URL API: https://docs.selectel.ru/api/

Что подключено в проект:
- Клиент `SelectelApiClient` с `list_zones()` и `ensure_zone(fqdn)`.
- При fail в основном регистраторе (Timeweb) сервис пытается создать/проверить DNS zone в Selectel как резерв.
- Это **не регистрация домена у реестра**, а резерв контроля DNS.

Файлы:
- `/Users/just/projects/domens/app/services/selectel_api.py`
- `/Users/just/projects/domens/app/services/registrar.py`

## 2) Reg.ru API

Официальная документация API2:
- Общий индекс методов: https://www.reg.ru/support/help/api2
- Endpoint/метаданные (`api/regru2`, авторизация логин+пароль):
  https://www.reg.ru/support/help/api2/api-operations/accesspoint
- Проверка домена (`domain/check`):
  https://www.reg.ru/support/help/api2/api-operations/domain/check
- Регистрация домена (`domain/create`):
  https://www.reg.ru/support/help/api2/api-operations/domain/create

Что подключено в проект:
- Добавлен `RegRuApiClient` (form-data вызовы API2, JSON output).
- Добавлена ветка `registrar_provider=reg_ru`.
- В fallback-цепочке при `provider=timeweb` и `REGISTRAR_FALLBACK_ENABLED=true`:
  1) Timeweb
  2) Reg.ru (если заданы креды)
  3) Selectel DNS reserve

Файлы:
- `/Users/just/projects/domens/app/services/reg_ru_api.py`
- `/Users/just/projects/domens/app/services/registrar.py`

## 3) MAX Messenger API (reserve channel)

Источник локально:
- `/Users/just/projects/max/max_timeweb_bot/max_client.py`
- `/Users/just/projects/max/README.md`

Практический контракт из рабочего бота:
- `POST /messages?chat_id=<id>` — отправка текста/кнопок
- `POST /answers?callback_id=<id>` — ответ на callback
- `GET /updates` — polling апдейтов
- `Authorization: <MAX_TOKEN>`
- Базовый URL: `https://platform-api.max.ru`

Что подключено в проект:
- Отправка алертов/текста в MAX (`send_max_alert`, `send_max_text`).
- Новый webhook для callback-кнопок:
  - `POST /v1/max/webhook`
  - payload `register:<token>` / `skip:<token>`
- Callback `register` автоматически запускает confirm+execute (как в Telegram).

Файлы:
- `/Users/just/projects/domens/app/services/notifications.py`
- `/Users/just/projects/domens/app/routers/max.py`
- `/Users/just/projects/domens/app/main.py`

## Риски/ограничения
- Selectel DNS reserve не заменяет registrar purchase.
- Reg.ru integration добавлена в режиме API2 client; для production нужно подтвердить тариф/доступ и обработать все бизнес-ошибки API2.
- Для MAX нужен отдельный bot token и chat_id (ты как раз создаешь нового бота).
