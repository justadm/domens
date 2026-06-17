# Domens Promotion Launch Plan

Цель: продвигать Domens как тихий Telegram-first доменный радар, не разгоняя массовый трафик до принятого 24h canary report.

## Stage 0: Evidence Before Promotion

Когда: до публичного анонса.

Задачи:

- собрать 24h canary report из `docs/product_launch_runbook.md`;
- подтвердить, что `MONITOR_DIGEST_ENABLED=true` дает низкий и ожидаемый объем дайджестов;
- проверить, что feedback-кнопки реально меняют поведение:
  - "Больше таких";
  - "Меньше таких";
  - "Не повторять";
- убедиться, что `REGISTRATION_ENABLED=false` и не было неожиданных попыток регистрации;
- подготовить 3-5 реальных обезличенных примеров алертов.
- добавить no-front-running pledge в публичные trust/onboarding тексты;
- проверить, что provider confidence виден в отчетах или хотя бы отражен в copy.

Go/no-go:

- если есть повторный спам по одному домену или непонятные skip reasons, продвижение не расширять;
- если алерты объяснимы и digest-объем низкий, переходить к Stage 1.

## Stage 1: Closed Canary

Аудитория: 20-50 человек.

Кого звать:

- основатели небольших SaaS/AI-продуктов;
- веб-студии;
- брендинг/нейминг-специалисты;
- домейнеры, которым интересен сигнал, а не ручной перебор;
- владельцы Telegram/IT-каналов.

Оффер:

> Даем тихий доменный радар под вашу нишу: 1-3 сильных сигнала в день, с объяснением и кнопками обратной связи. Регистрация отключена по умолчанию и требует отдельного подтверждения.

Канал:

- личные сообщения;
- профильные Telegram-чаты;
- партнерские контакты студий;
- небольшой пост в личном канале/канале проекта.

Метрики:

- сколько людей включили watchlist;
- сколько дайджестов отправлено;
- сколько feedback-событий;
- сколько доменов скрыли;
- сколько раз пользователь попросил "больше таких";
- сколько раз пользователь спросил про регистрацию.

## Stage 2: Public Telegram Channel

Когда: после принятого canary report.

Что публиковать:

- `Domain Radar Digest` раз в неделю;
- `Channel Showcase Post` 2 раза в неделю;
- короткие разборы "почему домен прошел фильтр";
- короткие разборы "почему домен не прошел фильтр";
- примеры watchlist-запросов.

Главный CTA:

> Напишите боту нишу - получите мини-отчет и сможете включить тихий watchlist.

Не использовать:

- обещания гарантированной регистрации;
- длинные списки сырых доменов;
- агрессивные "успей купить";
- платный трафик на неподтвержденный flow.
- сравнения "быстрее/лучше GoDaddy/Namecheap/Domainr";
- обещания успешного drop-catch или trademark safety.

## Stage 3: Partner Distribution

Когда: после 2-3 недель стабильного Telegram-канала.

Партнеры:

- веб-студии;
- брендинговые агентства;
- no-code/integrator команды;
- Telegram-каналы про AI/startups/devtools.

Партнерский оффер:

> Domens готовит доменный short-list под нишу клиента: варианты, score, статус, объяснение, риски. Студия может использовать это как часть нейминга или discovery.

Формат:

- 1 бесплатный отчет на партнера;
- далее пакетная работа или платный доступ;
- без включения real registration до отдельного ops-решения.
- для web studio подготовить exportable Markdown/PDF/Google Doc style report как отдельный deliverable.

## Stage 4: Wider Launch

Когда: после устойчивых метрик и исправленных product gaps.

Каналы:

- Product Hunt;
- Indie Hackers;
- Hacker News Show HN, only when the product is directly tryable;
- русскоязычные Telegram-каналы про стартапы и AI;
- SEO-страницы под "подбор домена для SaaS/AI/стартапа".

Готовность:

- есть canary evidence;
- есть 5-10 публичных примеров;
- есть lead magnet report;
- есть понятный onboarding в Telegram;
- web cabinet показывает parity controls или хотя бы не конфликтует с Telegram-first сценарием.

## Public And Paid Channel Gates

### Show HN

Delay `Show HN` until users can try Domens with minimal friction. Hacker News describes Show HN as something people can try and explicitly asks not to post if the work is not ready for users.

Source: https://news.ycombinator.com/showhn.html

Gate:

- public bot or demo is tryable;
- no waitlist-only landing page as the main experience;
- operator is available to answer comments;
- canary evidence exists;
- onboarding does not require manual intervention for every user.

### Telegram Ads

Delay Telegram Ads until the bot/channel funnel is stable. Telegram Ads sponsored messages are shown in public one-to-many channels with 1000+ subscribers, and ad links must point to Telegram channel/bot destinations (`t.me/...` or `@...`), not external websites.

Source: https://ads.telegram.org/getting-started

Gate:

- Telegram bot CTA works end to end;
- public channel has enough trust content;
- metrics from `promotion_metrics.md` are captured;
- 24h canary report is accepted;
- trust pack is published;
- ad URL points to the bot or channel, not the web cabinet.
