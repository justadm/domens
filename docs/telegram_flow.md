# Telegram Flow (MVP)

## Buttons payload
- `register:<confirmation_token>`
- `skip:<confirmation_token>`

## Sequence
1. Backend находит интересный домен и вызывает `POST /v1/alerts/trigger`.
2. Notifier отправляет сообщение в Telegram c inline keyboard.
3. Пользователь нажимает кнопку `Зарегистрировать`.
4. Telegram шлет callback на `/v1/telegram/webhook`.
5. Backend извлекает token и вызывает внутренне `confirm_registration`.
6. Создается `registration_order` со статусом `queued`.
7. Worker/API запускает `execute_registration`.
8. Результат (`registered`/`failed`) отправляется в Telegram.

## Idempotency
- Один `confirmation_token` можно подтвердить только один раз.
- Повторные callbacks должны возвращать текущий статус без дубля заказа.
