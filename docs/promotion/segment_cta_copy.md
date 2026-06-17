# Segment CTA Copy

Готовые CTA под разные аудитории. Использовать стабильные `cta` значения из `promotion_metrics.md`.

## Founder

CTA key: `founder_5_domains`

Short:

```md
Получить 5 доменов под SaaS-нишу.
```

Medium:

```md
Запускаете SaaS или AI-продукт? Напишите нишу - Domens подготовит 5 доменных вариантов с score, статусом и объяснением.
```

Post CTA:

```md
Founder CTA: напишите боту нишу и получите 5 доменов под SaaS-идею.

Пример:
`найди домены для AI security SaaS`
```

Bot reply:

```md
Ок, сделаю founder-подборку: до 5 доменов под нишу **{niche}**.

Фокус:

- короткое brandable-имя;
- понятная SaaS-ассоциация;
- TLD: {tld_list};
- объяснение по каждому варианту.
```

## Web Studio

CTA key: `studio_client_shortlist`

Short:

```md
Получить short-list доменов для клиента.
```

Medium:

```md
Для студий и интеграторов: отправьте нишу клиента, а Domens вернет short-list доменов со score, статусом, объяснением и рисками.
```

Post CTA:

```md
Web studio CTA: пришлите нишу клиента, язык рынка и желательные TLD - подготовим short-list для обсуждения на discovery.
```

Bot reply:

```md
Ок, сделаю studio short-list для клиента.

Нужно уточнить:

- ниша клиента;
- рынок: RU/global;
- желательные TLD;
- стиль: enterprise, devtool, consumer или premium.
```

## Domainer

CTA key: `domainer_1_digest_day`

Short:

```md
Включить 1 digest/day по паттерну и TLD.
```

Medium:

```md
Для домейнеров: задайте паттерн, TLD и ограничения. Domens будет присылать не поток, а 1 digest/day с объяснимыми сигналами.
```

Post CTA:

```md
Domainer CTA: выберите паттерн и TLD, включите 1 digest/day и оценивайте качество сигналов через feedback-кнопки.
```

Bot reply:

```md
Ок, включаем domainer-режим canary.

Настройки:

- паттерн: **{pattern}**
- TLD: {tld_list}
- лимит: 1 digest/day
- цель: меньше шума, больше объяснимых сигналов
```

## Generic Canary CTA

CTA key: `manual_canary_invite`

```md
Участвовать в canary: дать одну нишу, получить первый digest и помочь настроить точность радара.
```

## CTA Selection Rule

- Если человек запускает свой продукт - founder CTA.
- Если человек работает с клиентскими проектами - web studio CTA.
- Если человек оценивает домены как активы или паттерны - domainer CTA.
- Если сегмент неизвестен - generic canary CTA.
