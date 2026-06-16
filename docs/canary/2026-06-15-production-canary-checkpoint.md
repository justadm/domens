# Production Canary Checkpoint: 2026-06-15

Status: in progress.

Scope: production `idns.devee.ru`, MSK host, `domens` compose project.

This checkpoint tracks the fresh quiet-radar canary window started after the cooldown/auth/legal/safety fixes were deployed.

## Window

- Canary start: 2026-06-15 07:06:40 UTC.
- Initial checkpoint time: 2026-06-15 07:39:31 UTC.
- Post-deploy verification time: 2026-06-15 07:43 UTC.
- Follow-up checkpoint time: 2026-06-15 09:48 UTC.
- Production revision at post-deploy verification: `f6faf9b`.
- Production code revision at follow-up checkpoint: `6d7a895`.

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

## Follow-Up Checkpoint

Read-only production DB snapshot for events since `2026-06-15 07:06:40 UTC`:

```text
alert_feedback            6
monitor_candidates_built  26
monitor_run_finished      25
monitor_run_started       26
monitor_alert_sent        0
monitor_digest_sent       0
telegram_delivery_error   0
```

Aggregated `monitor_run_finished` payloads:

```text
runs_finished   25
checked_total   22000
alerts_sent     0
digests_sent    0
last_finished   2026-06-15 09:48:40 UTC
```

Aggregated skip reasons:

```text
status_not_interesting  20704
watch_daily_limit        1296
```

Latest `monitor_run_finished` payload:

```text
checked=880
alerts_sent=0
skip_reasons={"watch_daily_limit": 52, "status_not_interesting": 828}
status_counts={"available": 52, "registered": 828}
```

No API log lines matching `error|exception|traceback|telegram|monitor` were found in the two-hour window before the checkpoint.

## Multi-Account Follow-Up

Read-only production DB snapshot on 2026-06-16 after adding extra Telegram accounts:

```text
username           roles  active_rules  telegram_subscription
AlekseyTeplinsky  user   26            paused
artem_teplinskiy  user   2             active
kons_tep          user   2             active
JustAdm           admin  31            active
```

The extra accounts now exercise both onboarding/profile/menu paths and multi-user watchlist delivery.

Canary watch rules were seeded with one-alert daily limits:

```text
artem_teplinskiy  ai tools    tlds=.io,.ai,.ru  daily_limit=1
artem_teplinskiy  assist lab  tlds=.io,.ru      daily_limit=1
kons_tep          crm tools   tlds=.io,.ai,.ru  daily_limit=1
kons_tep          catch hub   tlds=.ru,.com     daily_limit=1
```

Initial canary rule seeding passed TLDs without leading dots, which produced invalid candidate names such as `assistio` and `catchru`. The production rows were corrected to dotted TLDs and the codebase now normalizes watch-rule TLDs at Store boundaries.

Read-only production DB snapshot for events since `2026-06-15 07:06:40 UTC`:

```text
monitor_run_finished      200
monitor_run_started       202
monitor_candidates_built  202
monitor_alert_sent        2
monitor_digest_sent       2
alert_feedback            10
checked_total             176000
```

Monitor deliveries since canary start:

```text
2026-06-15 17:44 UTC  JustAdm  assistlab.io    digest items=1
2026-06-15 23:44 UTC  JustAdm  catcherlab.com  digest items=1
```

The two monitor deliveries to the same destination were spaced by about six hours, matching `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES=360`.

Aggregated skip reasons since canary start:

```text
status_not_interesting  165622
target_cooldown           5395
watch_daily_limit         4880
global_run_limit            91
suppressed                    7
recent_alert                  3
```

No API log lines matching `error|exception|traceback|telegram|monitor` were found in the twelve-hour window before this checkpoint.

## Multi-Account Delivery Verification

After TLD correction, two consecutive production monitor runs delivered one digest to each new active account, constrained by `MONITOR_ALERT_GLOBAL_RUN_LIMIT=1`:

```text
2026-06-16 06:04 UTC  artem_teplinskiy  assistlab.io  score=70  provider=timeweb  digest message_id=613
2026-06-16 06:11 UTC  kons_tep          catchhub.ru   score=74  provider=timeweb  digest message_id=614
```

Both alerts carried explainable payloads:

```text
status=available
risk=provider_checked
matched_query=assist lab | catch hub
buttons=why, more, less, never
items_count=1
```

No API log lines matching `error|exception|traceback|telegram|monitor` were found in the 45-minute window around the multi-account delivery test.

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
