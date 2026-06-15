# Production Canary Checkpoint: 2026-06-15

Status: in progress.

Scope: production `idns.devee.ru`, MSK host, `domens` compose project.

This checkpoint tracks the fresh quiet-radar canary window started after the cooldown/auth/legal/safety fixes were deployed.

## Window

- Canary start: 2026-06-15 07:06:40 UTC.
- Initial checkpoint time: 2026-06-15 07:39:31 UTC.
- Post-deploy verification time: 2026-06-15 07:43 UTC.
- Production revision at post-deploy verification: `f6faf9b`.

## Runtime Health

- `/health`: `{"status":"ok"}`.
- `/ready`: `{"status":"ok","database":true,"telegram_configured":true,"monitoring_enabled":true,"registration_enabled":false}`.

Runtime flags inspected from `domens-api-1`:

```text
monitor_enabled=True
monitor_watchlist_only=True
monitor_admin_fanout_enabled=False
monitor_alert_target_cooldown_minutes=360
registration_enabled=False
monitor_event_logging_enabled=True
monitor_event_logging_detail=False
```

## Monitor Event Counts Since Canary Start

```text
monitor_candidates_built  4
monitor_run_finished      5
monitor_run_started       4
monitor_alert_sent        0
monitor_alert_skipped     0
```

Compact `monitor_run_finished` payloads show:

```text
checked=880
alerts_sent=0
skip_reasons={"watch_daily_limit": 52, "status_not_interesting": 828}
status_counts={"available": 52, "registered": 828}
```

## Finding

No new Telegram alert noise was observed in the first checkpoint interval.

This does not yet prove the new per-destination cooldown on a real alert send, because the available candidates are currently suppressed by the per-watch daily limit from the previous canary activity. Continue observing until the previous 24h daily-limit window ages out or a new eligible candidate appears.

## Post-Deploy Logging Verification

Revision `f6faf9b` adds `target_cooldown_minutes` to the `monitor_run_started` audit payload. This makes canary evidence self-contained in `bot_events` instead of requiring a separate container config probe.

First monitor run after deploy:

```text
monitor_run_started  2026-06-15 07:41:07 UTC
target_cooldown      360
monitor_run_finished 2026-06-15 07:42:55 UTC
checked              880
alerts_sent          0
skip_reasons         {"watch_daily_limit": 52, "status_not_interesting": 828}
```

No Telegram or monitor errors were found in the API logs since the deploy.

Unauthenticated operational endpoint checks after deploy:

```text
POST /v1/domains/check   401 unauthorized
POST /v1/alerts/trigger  401 unauthorized
```

## Admin Quality Baseline

Revision `aa817e4` added admin-visible canary metrics to `GET /v1/admin/quality` and the admin dashboard:

- alert, feedback, and suppression totals;
- monitor runs, checked candidates, sent alerts, and sent digests;
- aggregated monitor skip reasons;
- Telegram delivery error count;
- registration and monitoring safety flags.

Revision `e9c54fd` closed the admin guest-auth gap: admin routes now require a real session cookie and reject guest auth fallback.

Revisions `86c20f1` and `6d7a895` added cabinet radar preferences and closed the equivalent guest-auth gap for sensitive LK preference routes:

- `GET /v1/cabinet/preferences`;
- `DELETE /v1/cabinet/preferences/suppressions/{suppression_id}`.

Post-hotfix unauthenticated checks:

```text
GET /v1/admin/quality?days=7  401 unauthorized
GET /v1/admin/dashboard       401 unauthorized
GET /v1/cabinet/preferences   401 unauthorized
DELETE /v1/cabinet/preferences/suppressions/test  401 unauthorized
```

Verification before this checkpoint:

- `PYTHONPATH=. .venv313/bin/pytest tests/test_alert_suppression.py::test_monitoring_run_writes_compact_summary_without_per_candidate_events -q`: passed;
- `PYTHONPATH=. .venv313/bin/pytest -q`: `103 passed`;
- `git diff --check`: passed.

## Continue Criteria

- Keep monitoring enabled in watchlist-only mode.
- Keep registration disabled.
- Continue checking for:
  - no Telegram delivery errors;
  - no repeated same-domain alerts;
  - no more than one destination alert inside the target cooldown window;
  - expected `target_cooldown` skip reason once eligible alerts resume.
