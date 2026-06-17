# Telegram Content Calendar

Двухнедельный план публикаций для канала Domens. План рассчитан на мягкий запуск без массового трафика.

## Week 1

### Day 1: Positioning Post

Цель: объяснить, чем Domens отличается от обычного domain checker.

Тезисы:

- не проверяем все подряд;
- ищем редкие сильные сигналы;
- показываем причину алерта;
- пользователь управляет watchlist и скрытиями;
- регистрация всегда требует подтверждения.

CTA:

```md
Ответьте нишей в комментариях или напишите боту: `найди домены для {ниша}`.
```

### Day 2: Showcase Post

Использовать: [Channel Showcase Post](./telegram_channel_showcase_post.md)

Ниша:

- AI security;
- devtools;
- Telegram mini apps;
- e-commerce automation.

### Day 3: Behind The Score

Цель: показать доверие к скорингу.

Структура:

```md
# Что значит score домена

Мы учитываем:

- длину;
- читаемость;
- brandability;
- совпадение с темой;
- ликвидность похожих паттернов;
- статус и свежесть проверки.
```

CTA:

```md
Хотите проверить нишу - напишите боту тему и TLD.
```

### Day 4: Canary Invitation

Использовать короткую версию из [Canary Outreach Messages](./canary_outreach_messages.md).

Цель: набрать первых пользователей без публичного обещания широкого доступа.

### Day 5: Domain Radar Digest

Использовать: [Domain Radar Digest](./telegram_domain_radar_digest.md)

Правило:

- максимум 5 доменов;
- обязательно объяснить лучший сигнал недели;
- обязательно добавить disclaimer про свежую проверку.

## Week 2

### Day 6: Negative Example

Цель: показать, что Domens не шлет шум.

Структура:

```md
# Почему этот домен не прошел фильтр

Домен: {domain}

Причины:

- слишком длинный;
- слабая читаемость;
- не совпадает с watchlist;
- низкая уверенность в статусе.
```

CTA:

```md
Хороший радар ценен не только тем, что нашел, но и тем, что не отправил.
```

### Day 7: Lead Magnet Report

Использовать: [Lead Magnet Report](./telegram_lead_magnet_report.md)

Формат:

- взять одну публичную нишу;
- показать короткий отчет;
- предложить включить watchlist.

### Day 8: Feedback Loop Post

Цель: объяснить, зачем кнопки "Больше таких", "Меньше таких", "Не повторять".

Тезисы:

- радар учится на предпочтениях пользователя;
- скрытия важнее лайков;
- цель - меньше уведомлений, но выше точность.

### Day 9: Partner Post

Цель: обратиться к веб-студиям и брендинг-командам.

Оффер:

```md
Если вы запускаете клиентский продукт, Domens может дать доменный short-list: варианты, score, статус, объяснение и риски.
```

### Day 10: Canary Result Snapshot

Публиковать только после реального 24h canary report.

Структура:

```md
# 24h canary snapshot

- monitor runs: {count}
- checked candidates: {count}
- digests sent: {count}
- repeated-domain spam: 0
- feedback callbacks: {count}
- registration attempts while disabled: 0

Вывод: {keep_on|tune_limits|rollback}
```

## Cadence

- 3-5 публикаций в неделю достаточно.
- Один пост должен решать одну задачу: объяснить, показать пример, пригласить, собрать обратную связь.
- Не публиковать сырые длинные списки доменов.
