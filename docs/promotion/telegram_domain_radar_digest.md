# Telegram Template: Domain Radar Digest

Назначение: еженедельный пост в Telegram-канал или длинное сообщение от бота. Формат показывает ценность отбора: не просто список доменов, а объяснимый short-list.

## Template

```md
# Domain Radar: {Ниша} за {Период}

Мы отобрали {N} доменов из {TOTAL_CHECKED} кандидатов.
Фильтр: {TLD_LIST}, длина до {MAX_LENGTH}, score от {MIN_SCORE}.

| Домен | Score | Статус | Почему попал в подборку |
|---|---:|---|---|
| {domain_1} | {score_1} | {status_1} | {reason_1} |
| {domain_2} | {score_2} | {status_2} | {reason_2} |
| {domain_3} | {score_3} | {status_3} | {reason_3} |

## Лучший сигнал недели

**{top_domain}**

- Score: **{top_score}**
- Статус: **{top_status}**
- TLD: **.{top_tld}**
- Длина: **{top_length}**
- Подходит для: {best_for}

> Доступность домена не гарантируется. Перед регистрацией Domens делает свежую проверку у регистратора.

CTA:

- Founder: получить 5 доменов под SaaS-нишу.
- Web studio: получить short-list для клиента.
- Domainer: включить 1 digest/day по паттерну и TLD.

Напиши боту: `{example_prompt}`
```

## Example

```md
# Domain Radar: AI security за неделю

Мы отобрали 5 доменов из 420 кандидатов.
Фильтр: .com, .io, .ai, .ru, длина до 14, score от 70.

| Домен | Score | Статус | Почему попал в подборку |
|---|---:|---|---|
| agentshield.ai | 88 | available | короткий AI/security смысл, хорошая читаемость |
| secflow.io | 84 | pending_delete | понятная dev/security ассоциация |
| auditgrid.ru | 79 | available | B2B-звучание, подходит для compliance/SOC |

## Лучший сигнал недели

**agentshield.ai**

- Score: **88**
- Статус: **available**
- TLD: **.ai**
- Длина: **11**
- Подходит для: AI security SaaS, agent monitoring, SOC automation

> Доступность домена не гарантируется. Перед регистрацией Domens делает свежую проверку у регистратора.

CTA:

- Founder: получить 5 доменов под SaaS-нишу.
- Web studio: получить short-list для клиента.
- Domainer: включить 1 digest/day по паттерну и TLD.

Напиши боту: `найди домены для AI security SaaS`
```

## Production notes

- Таблица должна быть короткой: 3-7 строк.
- В канал лучше публиковать без прямого призыва "покупай", акцент на объяснение.
- Для canary можно добавлять строку: "Ответьте нишей в комментариях, выберем 3 заявки для ручной подборки".
