# Competitive Messaging

Этот файл переводит конкурентный анализ в промо-решения. Он не заменяет `docs/competitive/`; когда аудитор закончит отдельный конкурентный раздел, этот файл нужно сверить с ним.

## Market Map

### Instant domain search and generators

Examples:

- Instant Domain Search;
- Domainr;
- Namecheap;
- GoDaddy.

Their strengths:

- search-as-you-type;
- large TLD coverage;
- bulk search;
- price comparison;
- WHOIS/history;
- registrar checkout;
- API and monitoring in some products.

Domens should not compete here on raw speed or maximum TLD coverage.

### Expired, drop, and backorder tools

Examples:

- NameJet;
- SnapNames;
- DropCatch;
- ExpiredDomains.net;
- Park.io.

Their strengths:

- expired and pending-delete inventory;
- backorder flows;
- auctions;
- bulk lists and filters;
- historical/SEO signals.

Domens should not claim it can catch any drop or replace dedicated backorder platforms.

### Brandable marketplaces and naming platforms

Examples:

- BrandBucket;
- Atom/Squadhelp.

Their strengths:

- curated premium inventory;
- logos and naming presentation;
- upfront pricing;
- transfer/escrow workflows;
- naming contests;
- trademark/search add-ons.

Domens should not position as a premium marketplace in the early product.

Useful pattern to borrow:

- concise value tags such as `short`, `memorable`, `brandable`, `exact-match`, `local`, `SaaS`, `marketplace`, `agency`;
- curated explanation for why the name is strong;
- explicit risk notes instead of generic hype.

### Enterprise brand protection and domain intelligence

Examples:

- MarkMonitor;
- DomainTools;
- WhoisXML;
- Domainr API.

Their strengths:

- brand protection;
- cybersquatting/phishing monitoring;
- enterprise domain intelligence;
- critical domain change alerts.

Domens should not claim enterprise brand protection or legal monitoring.

## Domens Positioning

Use:

```md
Domens is not another domain checker. It is a personal explainable radar for a specific niche: fewer alerts, stronger reasons, Telegram workflow, feedback loop.
```

Russian:

```md
Domens - не очередной domain checker. Это персональный explainable radar под конкретную нишу: меньше алертов, больше причин, Telegram workflow и feedback-loop.
```

## Differentiators To Use

- Quiet by design: 1-3 strong signals, not raw lists.
- Watchlist-first: user niche and constraints drive candidates.
- Explainable alerts: score, status, provider, TLD, length, reason, risk.
- Feedback loop: more/less/never changes future alerts.
- Telegram-first: daily digest where the user already works.
- Safety-first registration: explicit confirmation and fresh provider check.
- No-front-running pledge: user searches are not used for Domens-owned registration or resale.

## Claims To Avoid

Do not say:

- "Поймаем любой drop".
- "Гарантируем доступность".
- "Автоматически зарегистрируем лучший домен".
- "Юридически безопасный домен".
- "Заменяем trademark search".
- "Лучше GoDaddy/Namecheap/Domainr по поиску".
- "Маркетплейс premium-доменов".

Use instead:

- "Показываем сильные сигналы".
- "Снижаем шум".
- "Объясняем, почему домен попал в подборку".
- "Перед регистрацией выполняется свежая проверка".
- "Score не является юридической проверкой".

## Trust Lessons To Reflect In Promo

### Search privacy and no front-running

User concern:

> If I search for a domain, will the service register or resell it against me?

Promotional answer:

```md
No front-running: Domens не использует пользовательские запросы для собственной регистрации или перепродажи доменов.
```

Trust requirements:

- explain what happens to watchlist queries;
- explain when provider checks are performed;
- do not send unnecessary provider checks during exploratory prompts if avoidable;
- keep audit logs for provider checks.

### Provider confidence

User concern:

> Is the status fresh and reliable?

Use confidence tiers:

- `provider_checked` - fresh provider check succeeded;
- `heuristic` - inferred without fresh provider confirmation;
- `stale` - previous check is too old;
- `unknown` - status cannot be trusted;
- `rate_limited` - provider/source throttled checks.

Promo rule:

```md
If confidence is not `provider_checked`, use cautious language and do not imply the domain can be registered.
```

### Trademark and cybersquatting

User concern:

> Does score mean legally safe?

Promotional answer:

```md
Нет. Score не является юридической проверкой товарных знаков. Он помогает оценить доменное имя как продуктовый сигнал, но не заменяет legal review.
```

### Auctions and marketplaces

User concern:

> Is Domens a marketplace or auction?

Promotional answer:

```md
Нет. Early Domens продает сигнал, объяснение и workflow. Мы не запускаем аукционный модуль и не разгоняем цены.
```

## Segment Messaging

### Founder

Angle:

> Save time during naming. Get a few explainable domain candidates instead of raw search noise.

CTA:

```md
Получить 5 доменов под SaaS-нишу.
```

### Web studio

Angle:

> Add a domain short-list to discovery and naming deliverables.

CTA:

```md
Получить short-list для клиента.
```

Useful add-on:

- exportable Markdown/PDF/Google Doc style report.

### Domainer

Angle:

> Track patterns and TLDs with one digest/day, not endless expired lists.

CTA:

```md
Включить 1 digest/day по паттерну и TLD.
```

## Product Gaps That Affect Promotion

Blocking before broad public promotion:

- no-front-running pledge visible in trust pack;
- provider confidence visible in alerts/reports;
- trademark disclaimer visible in trust and registration flows;
- one-click or documented data deletion path;
- 24h canary report accepted;
- examples library with anonymized good/bad canary alerts.
- source health view or canary evidence covering provider errors/rate limits;
- event mapping from promotion metrics to real DB/log events.

Non-blocking but useful:

- partner report export;
- user-visible "why not sent";
- simple brand/trademark stop-list;
- public examples library page.

## Value Tags

Use short tags in reports and public examples to make the reason readable:

- `short` - compact name;
- `memorable` - easy to remember;
- `brandable` - can work as a product/company name;
- `exact-match` - close to the user's query;
- `local` - useful for a local/RU market;
- `SaaS` - fits software/service positioning;
- `marketplace` - fits multi-sided/platform positioning;
- `agency` - useful for service/consulting businesses;
- `devtool` - fits developer tooling;
- `security` - fits security/compliance;
- `ai` - AI-related naming signal.
