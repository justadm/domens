# 24h Canary Report Template

Use this after a full day of production canary monitoring. The report decides whether to keep the radar on, tune limits, or roll back.

## Summary

- Report date:
- Observation window:
- Environment:
- Git revision:
- Operator:
- Decision: `keep_on` / `tune_limits` / `rollback`

## Runtime Flags

```env
MONITOR_ENABLED=true
MONITOR_WATCHLIST_ONLY=true
MONITOR_ADMIN_FANOUT_ENABLED=false
MONITOR_EVENT_LOGGING_ENABLED=true
MONITOR_EVENT_LOGGING_DETAIL=false
MONITOR_DIGEST_ENABLED=true
MONITOR_ALERT_GLOBAL_RUN_LIMIT=
MONITOR_ALERT_PER_TARGET_RUN_LIMIT=
MONITOR_ALERT_PER_TARGET_DAILY_LIMIT=
MONITOR_ALERT_COOLDOWN_MINUTES=1440
REGISTRATION_ENABLED=false
REGISTRATION_REQUIRE_AVAILABLE_CHECK=true
```

## Event Counts

Source query:

```bash
ssh msk 'docker exec -i domens-postgres-1 psql -U domens -d domens -c "select event_type, count(*) from bot_events where created_at >= now() - interval '\''24 hours'\'' and event_type like '\''monitor_%'\'' group by event_type order by event_type;"'
```

| Event | Count |
|---|---:|
| `monitor_run_started` |  |
| `monitor_candidates_built` |  |
| `monitor_candidate_checked` |  |
| `monitor_alert_skipped` |  |
| `monitor_alert_sent` |  |
| `monitor_digest_sent` |  |
| `monitor_run_finished` |  |
| Telegram delivery errors |  |
| Feedback callbacks |  |
| Registration attempts while disabled |  |
| Provider `rate_limited` |  |
| Provider `unknown` |  |
| Provider `stale` |  |

## Quality Checks

| Check | Result | Evidence |
|---|---|---|
| Repeated same-domain spam for same destination | `pass` / `fail` |  |
| Digest volume low and expected | `pass` / `fail` |  |
| Alert explanations present | `pass` / `fail` |  |
| Skip reasons understandable | `pass` / `fail` |  |
| Feedback callbacks persisted | `pass` / `fail` |  |
| `/help`, `/profile`, `/menu`, `/preferences` smoke passed | `pass` / `fail` |  |
| No unexpected registration execution attempts | `pass` / `fail` |  |
| Provider/source health acceptable | `pass` / `fail` |  |
| Promo metrics map to real events | `pass` / `fail` |  |

## Feedback Rate

| Metric | Value |
|---|---:|
| Digests sent |  |
| Users/chats reached |  |
| Feedback callbacks |  |
| `more` |  |
| `less` |  |
| `never` |  |
| Feedback rate |  |

Formula:

```text
feedback_rate = feedback_callbacks / max(digests_sent, 1)
```

## Top Complaints

List real user complaints or operator observations:

1.
2.
3.

Classify each:

- `too_many_alerts`
- `wrong_tld`
- `bad_name_quality`
- `unclear_explanation`
- `provider_status_uncertain`
- `source_unhealthy`
- `missing_metric_mapping`
- `telegram_ux`
- `other`

## Notable Domains

| Domain | Sent or skipped | Reason | User reaction |
|---|---|---|---|
|  |  |  |  |

## Go/No-Go Decision

Go conditions:

- repeated same-domain spam: `0`;
- unexpected registration execution attempts while disabled: `0`;
- digest volume matches configured limits;
- skip reasons are explainable;
- no unresolved Telegram delivery errors;
- provider/source errors are understood and not hidden as confident alerts;
- promotion metrics can be traced to bot events, watch rules, feedback rows, or manual canary rows;
- at least one meaningful feedback signal was captured, or no users were reached and the result is explicitly inconclusive.

Decision:

```text
keep_on / tune_limits / rollback
```

Next action:

```text
Describe the exact env/config/docs/product action.
```
