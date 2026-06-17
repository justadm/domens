# Examples Library

Библиотека примеров нужна для доверия, обучения канала и onboarding. Использовать только обезличенные данные: без реальных user id, приватных ниш клиента, внутренних токенов и доменов, которые пользователь явно просил не раскрывать.

## Purpose

- Показать, что Domens не шлет сырой список.
- Объяснить, как score и provider confidence влияют на алерт.
- Показать ценность negative examples: что не отправили и почему.
- Подготовить материал для public posts, landing, partner reports и canary review.

## Entry Format

```md
## {case_id}: {short_title}

- Segment: {founder|web_studio|domainer}
- Niche: {niche}
- Watch query: {watch_query}
- TLD: {tld_list}
- Date/window: {date_or_window}
- Result: {sent|skipped|suppressed|feedback_more|feedback_less|feedback_never}

### Domain

| Field | Value |
|---|---|
| Domain | `{domain}` |
| Score | `{score}` |
| Status | `{status}` |
| Provider confidence | `{provider_confidence}` |
| Reason | `{reason}` |
| Risk note | `{risk_note}` |

### Why it matters

{short_explanation}

### User reaction

{reaction_or_none}

### Promo use

{where_to_use}
```

## Good Example: Clear Niche Fit

```md
## EX-001: Clear AI security signal

- Segment: founder
- Niche: AI security SaaS
- Watch query: AI security
- TLD: .ai,.io
- Date/window: canary week 1
- Result: sent

### Domain

| Field | Value |
|---|---|
| Domain | `agentshield.ai` |
| Score | `88` |
| Status | `available` |
| Provider confidence | `provider_checked` |
| Reason | short, readable, direct AI/security association |
| Risk note | trademark review still required before commercial use |

### Why it matters

This is the kind of signal Domens should send: the domain matches the watch query, the name is easy to understand, and the alert can explain why it was selected.

### User reaction

`more`

### Promo use

Use in digest examples, landing proof, and founder CTA.
```

## Bad Example: Generic Noise

```md
## EX-002: Too generic and too long

- Segment: founder
- Niche: AI security SaaS
- Watch query: AI security
- TLD: .io
- Date/window: canary week 1
- Result: skipped

### Domain

| Field | Value |
|---|---|
| Domain | `best-ai-security-platform-online.io` |
| Score | `41` |
| Status | `available` |
| Provider confidence | `provider_checked` |
| Reason | too long, generic, weak brandability |
| Risk note | not worth alerting despite availability |

### Why it matters

Availability alone is not a reason to alert. This example supports the "quiet radar" promise.

### User reaction

Not sent.

### Promo use

Use in negative-example posts: "why we do not send everything".
```

## Trust Example: Provider Confidence Is Not Enough

```md
## EX-003: Interesting name, weak confidence

- Segment: domainer
- Niche: devtools
- Watch query: flow/grid tool names
- TLD: .com,.io
- Date/window: canary week 1
- Result: skipped

### Domain

| Field | Value |
|---|---|
| Domain | `flowgrid.io` |
| Score | `82` |
| Status | `unknown` |
| Provider confidence | `rate_limited` |
| Reason | good pattern, but status cannot be trusted |
| Risk note | do not imply registration readiness |

### Why it matters

A high score should not override weak provider confidence. This protects trust and reduces false urgency.

### User reaction

Not sent or sent only with cautious wording, depending on product mode.

### Promo use

Use in trust content: "why provider confidence matters".
```

## Suppression Example: User Taste Matters

```md
## EX-004: Less like this

- Segment: web_studio
- Niche: fintech onboarding
- Watch query: finance onboarding
- TLD: .io,.com
- Date/window: canary week 1
- Result: feedback_less

### Domain

| Field | Value |
|---|---|
| Domain | `ledgerflow.io` |
| Score | `82` |
| Status | `available` |
| Provider confidence | `provider_checked` |
| Reason | strong fintech/devtool pattern |
| Risk note | user wanted less technical naming |

### Why it matters

The domain can be objectively decent but wrong for a specific client style. Feedback is part of the product, not an afterthought.

### User reaction

`less`

### Promo use

Use in partner messaging: Domens adapts to client taste.
```

## Publishing Rules

- Replace real private watch queries with generalized niche labels.
- Do not publish domains from active private watchlists without approval.
- Do not publish provider payloads, tokens, chat ids, user ids, or exact internal timestamps.
- Keep examples short: one domain, one lesson.
- Mark uncertain status clearly; never imply availability when confidence is weak.
