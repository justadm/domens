# First Public Posts

Первые публикации для Telegram-канала. Их можно использовать до широкого запуска, если canary работает и нет повторного same-domain спама.

## Post 1: Soft Launch

```md
# Запускаем Domens canary

Domens - тихий Telegram-first радар доменов.

Мы не хотим делать еще один domain checker, который вываливает сотни сырых вариантов. Цель другая: присылать мало, но по делу.

Какой сигнал считается хорошим:

- домен подходит под вашу нишу;
- TLD и длина не выбиваются из настроек;
- есть понятное объяснение;
- статус проверен или риск явно указан;
- один и тот же домен не повторяется без причины.

Сейчас идет закрытый canary. Нужны первые пользователи, которым важна точность, а не объем.

CTA:

- Founder: получить 5 доменов под SaaS-нишу.
- Web studio: получить short-list для клиента.
- Domainer: включить 1 digest/day по паттерну и TLD.

Напишите боту нишу: `найди домены для AI security SaaS`.

> Регистрация домена не гарантируется. Перед покупкой нужна свежая проверка у регистратора.
```

## Post 2: First Digest

```md
# Domain Radar: AI security

Тестовая подборка для canary. Радар отобрал 3 домена из 120 кандидатов.

| Домен | Score | Статус | Почему интересен |
|---|---:|---|---|
| agentshield.ai | 88 | available | короткий AI/security смысл, хорошая читаемость |
| guardflow.io | 83 | available | звучит как devtool/security workflow |
| secagent.ru | 74 | available | короткий вариант под RU-рынок |

## Лучший сигнал

**agentshield.ai**

- TLD: `.ai`
- Длина: 11
- Подходит для: agent monitoring, SOC automation, AI security SaaS
- Риск: перед регистрацией нужна свежая проверка доступности

Если хотите такую подборку под свою нишу, напишите боту:
`найди домены для {ваша ниша}`
```

## Post 3: Negative Example

```md
# Почему радар не должен слать все подряд

Плохой доменный радар быстро превращается в спам: много вариантов, мало смысла, повторяются одни и те же корни.

Domens режет шум до алерта.

Пример домена, который не должен попасть в digest:

| Домен | Почему нет |
|---|---|
| best-ai-security-platform-online.io | слишком длинный, generic, плохо читается |
| ai-secure-agent-tools-pro.com | шумный набор слов, слабый brandability |
| agentguard123.ai | цифры в брендовом имени без причины |

Хороший сигнал должен отвечать на вопрос: почему этот домен стоит внимания именно сейчас?

Поэтому в Domens у каждого алерта есть score, статус, причина и feedback-кнопки.
```

## Post 4: Feedback Loop

```md
# Радар должен учиться на отказах

В Domens важны не только хорошие домены, но и отказы.

Когда пользователь нажимает:

- `Больше таких` - усиливаем похожий паттерн;
- `Меньше таких` - снижаем похожие сигналы;
- `Не повторять` - скрываем домен для пользователя.

Цель не в том, чтобы присылать больше. Цель - присылать меньше, но точнее.

Canary-метрика: repeated same-domain spam должен быть равен 0.
```

## Post 5: Canary Evidence Placeholder

Publish only after a real 24h canary report.

```md
# 24h canary snapshot

За последние 24 часа:

- monitor runs: {monitor_runs}
- checked candidates: {checked_candidates}
- digests sent: {digests_sent}
- feedback callbacks: {feedback_callbacks}
- repeated same-domain spam: 0
- unexpected registration attempts: 0

Вывод: {keep_on|tune_limits|rollback}

Следующий шаг: {next_step}
```
