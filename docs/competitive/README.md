# Domens Competitive Research

Дата среза: 2026-06-14.

Цель документа - зафиксировать конкурентный контекст, функции рынка, сильные приемы конкурентов, реальные факапы индустрии и выводы для запуска Domens.

## Короткий вывод

Domens не должен напрямую конкурировать с крупными domain search, drop-catching и marketplace игроками по ширине TLD, скорости поиска, аукционам или объему инвентаря.

Самая сильная ниша для MVP:

> персональный explainable domain radar: 1-3 сильных доменных сигнала в день под нишу пользователя, в Telegram, с понятным объяснением, обратной связью и безопасной регистрацией только после свежей проверки и явного подтверждения.

Это отличается от рынка тем, что Domens продает не "еще один поиск доменов", а спокойный мониторинг возможностей под конкретную нишу.

## Карта конкурентов

| Сегмент | Примеры | Что у них сильное | Где у Domens шанс |
| --- | --- | --- | --- |
| Быстрый domain search и генераторы | Instant Domain Search, Namecheap, GoDaddy, Domainr | Мгновенная проверка, много TLD, suggestions, premium/marketplace выдача | Не соревноваться в ширине. Давать меньше, но релевантнее: объяснение, ниша, Telegram, feedback loop |
| API/domain intelligence | Domainr, DomainTools, WhoisXML API | Данные, API, мониторинг статусов, registry/WHOIS/RDAP слой | Использовать как возможный источник/провайдера, но не строить публичное обещание на одном источнике |
| Expired/drop/backorder | NameJet, SnapNames, DropCatch, ExpiredDomains.net, Park.io | Pending delete, backorder, аукционы, bulk lists, SEO-фильтры | Брать идею watchlist/digest, но не входить в аукционы в MVP |
| Brandable marketplaces | BrandBucket, Atom | Кураторская витрина, naming, логотипы, upfront pricing, trust/transfer guarantee | Применить кураторский подход к алертам: "почему это имя сильное", а не просто список |
| Enterprise brand protection | MarkMonitor и аналоги | Защита бренда, портфель доменов, abuse/fraud мониторинг | Не enterprise в MVP. Но использовать trust language: риски trademark/cybersquatting, отказ от юридических гарантий |

## Функции рынка, которые стоит учитывать

### Instant domain search / generator

Типовые функции:

- быстрый поиск по имени;
- проверка множества TLD;
- suggestions/generator;
- premium и aftermarket домены;
- сравнение цен регистраторов;
- WHOIS/history/value estimates;
- privacy/no-front-running обещания.

Вывод для Domens:

- не делать landing с обещанием "самый быстрый поиск";
- добавить публичное объяснение, что пользовательские запросы не используются для front-running;
- в интерфейсе показывать источник проверки и время проверки;
- отделять "идея домена выглядит перспективной" от "домен точно можно купить сейчас".

### Domain API / monitoring

Типовые функции:

- availability API;
- registry/WHOIS/RDAP данные;
- premium/for-sale detection;
- мониторинг критичных доменов и смен статусов;
- API для интеграций.

Вывод для Domens:

- хранить `provider_checked_at`, `provider_name`, `provider_status`, `provider_confidence`;
- различать `provider_checked`, `heuristic`, `stale`, `unknown`, `rate_limited`;
- не слать пользователю боевой алерт, если статус `unknown/stale`, кроме отдельного экспериментального режима;
- блокировать регистрацию, если fresh provider check не подтвердил доступность.

### Expired domains / drop-catching

Типовые функции:

- pending delete lists;
- deleted/dropped domains;
- backorder;
- auctions;
- bulk tools;
- фильтры по TLD, длине, словам, SEO-метрикам, backlinks, Archive.org;
- watchlist.

Вывод для Domens:

- digest/watchlist - полезный паттерн;
- auction/backorder - высокий риск для MVP: сложная экономика, платежи, споры, ожидания клиента;
- лучше начать с "радары по нишам" и "interest/registration intent", а не с автоматического участия в дропах.

### Curated brandable marketplaces

Типовые функции:

- human-curated names;
- категории по стилю/индустрии;
- upfront price;
- логотипы;
- transfer guarantee/refund при технической невозможности transfer;
- lease-to-own;
- naming contests и AI-тесты аудитории.

Вывод для Domens:

- пользователю нужен не только статус, но и причина ценности;
- полезны теги: `short`, `memorable`, `brandable`, `exact-match`, `local`, `SaaS`, `marketplace`, `agency`;
- для промо стоит показывать 5-10 хороших анонимизированных примеров canary-алертов;
- "кураторский радар" звучит сильнее, чем "генератор доменов".

## Реальные факапы рынка и уроки

### 1. Front-running и недоверие к поиску доменов

Исторически рынок доменов получал репутационные удары из-за подозрений, что поисковые запросы пользователей могут использоваться для резервации или покупки доменов раньше пользователя. Самый известный кейс - Network Solutions и практики резервации доменов после поиска.

Урок:

- search privacy должен быть частью trust pack, а не мелким текстом;
- нельзя отправлять пользовательские seed-запросы во внешние сервисы без необходимости;
- если внешний провайдер нужен, в политике нужно явно объяснить, какие данные уходят наружу.

Что добавить в Domens:

- `No front-running pledge`;
- секцию в privacy policy: "как обрабатываются поисковые запросы и watchlist";
- минимизацию provider calls: проверять кандидаты, а не весь сырой поток пользовательских идей;
- аудит событий `domain_check_requested`, `provider_check_started`, `provider_check_failed`.

### 2. Warehousing и конфликт интересов на expired/auction рынке

В expired-доменах есть системный конфликт: регистраторы и аукционные площадки могут контролировать инвентарь, сроки, видимость и экономику доменов. Для пользователя это создает ощущение, что рынок непрозрачен.

Урок:

- Domens не должен выглядеть как еще один черный ящик, который "куда-то торгуется за домен";
- на старте лучше продавать сигнал и объяснение, а не контроль покупки в непрозрачной аукционной цепочке.

Что добавить в Domens:

- прозрачное разделение: `signal`, `fresh check`, `registration attempt`, `result`;
- история попытки регистрации в кабинете;
- отказ от обещаний "мы гарантированно заберем домен".

### 3. Shill bidding и недоверие к аукционам

В аукционных механиках есть риск искусственного разгона цены через подставные ставки. Даже если конкретная площадка честная, пользовательский страх остается.

Урок:

- auction/backorder не должен быть ранним публичным обещанием Domens;
- если когда-то добавлять аукционные интеграции, нужен отдельный risk disclosure, лог ставок, правила участия и лимиты.

Что добавить в Domens сейчас:

- не использовать в промо формулировки "заберем домен на аукционе";
- CTA держать вокруг watchlist, digest и manual registration intent.

### 4. API fragility и rate limits

Доменные источники часто завязаны на WHOIS/RDAP/registry/registrar API, где возможны rate limits, неполные ответы, задержки и изменения правил. Даже крупные сервисы вынуждены убирать TLD или деградировать функции при ограничениях провайдеров.

Урок:

- статус "неизвестно" должен быть нормальным продуктовым состоянием, а не скрытой ошибкой;
- нельзя превращать эвристику в уверенное обещание доступности.

Что добавить в Domens:

- source health dashboard для админа;
- user-visible статус `проверено провайдером`, `требует повторной проверки`, `источник временно недоступен`;
- daily report по доле `rate_limited/unknown/stale`;
- запрет registration flow без fresh provider check.

### 5. Trademark, UDRP и cybersquatting

Даже свободный домен может быть плохой покупкой из-за товарных знаков, похожести на бренд, typosquatting или UDRP-риска.

Урок:

- domain score не должен выглядеть как юридическая безопасность;
- "свободен" не значит "можно безопасно использовать".

Что добавить в Domens:

- `tm_risk_note` в объяснение алерта;
- стоп-лист очевидных брендов и typo-паттернов;
- дисклеймер: проверка домена не является юридической консультацией;
- позже - интеграция trademark search или хотя бы ручной чек перед paid tier.

## Обязательные trust-элементы до публичного продвижения

- Privacy policy с отдельным блоком про search/watchlist/privacy.
- No-front-running pledge.
- Support contact и operator identity.
- Registration disclaimer: регистрация не гарантируется до fresh provider check и успешного ответа регистратора.
- Trademark/UDRP disclaimer.
- Политика удаления данных пользователя и watchlist.
- Понятное хранение событий: что логируется, зачем и на какой срок.
- Видимый статус источника проверки в алертах и кабинете.

## Продуктовые нюансы, которые могли быть забыты

### Must before paid/public

- Provider confidence tiers: `provider_checked`, `heuristic`, `stale`, `unknown`, `rate_limited`.
- Public no-front-running wording.
- Data deletion path: удалить watchlist, Telegram link, историю запросов.
- Canary examples library: 5-10 анонимизированных алертов с "почему это сильный/слабый сигнал".
- Source health view: хотя бы админская таблица по provider errors/rate limits.
- Event mapping из промо-метрик в реальные события БД/логов.

### Should during canary

- "Why not sent" отчет для админа: какие кандидаты отфильтрованы и почему.
- Feedback reasons: `irrelevant`, `too_expensive`, `bad_tld`, `trademark_risk`, `already_seen`, `too_many_alerts`.
- Segment-specific CTA:
  - founder: получить 5 доменов под SaaS-нишу;
  - web studio: получить short-list для клиента;
  - domainer: включить 1 digest/day по паттерну и TLD.
- Partner report export для веб-студий.

### Later

- Trademark search integration.
- Portfolio monitoring for already-owned domains.
- Marketplace/auction integrations only after trust, payments and legal flows mature.
- API или white-label режим для агентств.

## Как это использовать в промо

Сильные формулировки:

- "Тихий радар доменных возможностей под вашу нишу".
- "Не 100 вариантов из генератора, а 1-3 объясненных сигнала в день".
- "Каждый алерт показывает, почему домен попал в выдачу".
- "Регистрация только после свежей проверки и явного подтверждения".
- "Мы не обещаем юридическую безопасность домена и не заменяем trademark check".

Формулировки, которых лучше избегать:

- "Гарантированно зарегистрируем домен".
- "Найдем все свободные домены".
- "Самый быстрый поиск доменов".
- "Безопасен для бренда" без trademark-проверки.
- "Заберем домен на дропе/аукционе" до отдельной инфраструктуры и правил.

## Каноническое позиционирование Domens

Domens - Telegram-first доменный радар для founders, веб-студий и домейнеров, который ежедневно отбирает небольшое число доменных возможностей под заданную нишу, объясняет причину отбора, собирает обратную связь и запускает регистрацию только после свежей проверки доступности и явного подтверждения пользователя.

## Список источников

- [Instant Domain Search](https://instantdomainsearch.com/) - быстрый поиск, TLD coverage, generator/marketplace/privacy positioning.
- [Domainr](https://domainr.com/) - domain availability API, monitoring, registry-oriented positioning.
- [NameJet](https://www.namejet.com/) - expired domains, pending delete, backorder, auction mechanics.
- [SnapNames](https://www.snapnames.com/) - expired/backorder/auction flow.
- [ExpiredDomains.net](https://www.expireddomains.net/) - deleted/pending delete lists, filters, TLD coverage, provider/rate-limit notes.
- [BrandBucket](https://www.brandbucket.com/) - curated brandable domain marketplace, transfer/refund trust wording.
- [Atom](https://www.atom.com/) - curated domains, AI naming/testing, contests, trademark/search tools.
- [Network Solutions](https://en.wikipedia.org/wiki/Network_Solutions) - historical domain search/front-running controversy context.
- [Domain name warehousing](https://en.wikipedia.org/wiki/Domain_name_warehousing) - expired-domain inventory conflict context.
- [Controversies surrounding GoDaddy](https://en.wikipedia.org/wiki/Controversies_surrounding_GoDaddy) - registrar trust, policy and platform-risk examples.
- [Uniform Domain-Name Dispute-Resolution Policy](https://en.wikipedia.org/wiki/Uniform_Domain-Name_Dispute-Resolution_Policy) - UDRP risk context.
- [Cybersquatting](https://en.wikipedia.org/wiki/Cybersquatting) - trademark/brand-abuse risk context.
- [Shill Bidding in English Auctions](https://arxiv.org/abs/1812.10868) - auction manipulation risk background.
