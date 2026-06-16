# Production Canary Report: 2026-06-15/16

Status: accepted for continued closed pilot.

Scope: production `idns.devee.ru`, MSK host, `domens` compose project.

This report closes the fresh quiet-radar canary started after the cooldown, auth, legal, and safety fixes were deployed.

## Window

- Start: 2026-06-15 07:06:40 UTC.
- Last inspected monitor event: 2026-06-16 11:03:52 UTC.
- Duration covered by DB evidence: about 27h 57m.
- Production revision at final verification: `4e0c821`.

## Runtime Flags

```text
monitor_enabled=True
monitor_watchlist_only=True
monitor_admin_fanout_enabled=False
monitor_event_logging_enabled=True
monitor_event_logging_detail=False
monitor_digest_enabled=True
monitor_alert_global_run_limit=1
monitor_alert_per_target_run_limit=1
monitor_alert_per_target_daily_limit=1
monitor_alert_cooldown_minutes=1440
monitor_alert_target_cooldown_minutes=360
registration_enabled=False
```

Runtime health at final verification:

```text
/health  {"status":"ok"}
/ready   {"status":"ok","database":true,"telegram_configured":true,"monitoring_enabled":true,"registration_enabled":false}
```

## Event Counts

Read-only production DB counts since `2026-06-15 07:06:40 UTC`:

```text
alert_feedback            13
monitor_alert_sent         5
monitor_candidates_built 251
monitor_digest_sent        5
monitor_run_finished     249
monitor_run_started      251
telegram_delivery_error    0
```

Aggregated `monitor_run_finished` totals:

```text
runs_finished  249
checked_total  219670
alerts_sent    5
```

Aggregated skip reasons:

```text
status_not_interesting  206749
watch_daily_limit         7400
target_cooldown           5447
global_run_limit           232
suppressed                  13
recent_alert                 4
```

Latest finished monitor runs show no new sends after the configured daily limits were reached:

```text
checked=890
alerts_sent=0
skip_reasons={"watch_daily_limit": 56, "status_not_interesting": 838}
status_counts={"available": 52, "registered": 838}
```

## Delivered Alerts

All production deliveries were Telegram digests with one item and feedback buttons.

```text
2026-06-15 17:44 UTC  chat 13903713    assistlab.io    score=70  provider=timeweb  message_id=596
2026-06-15 23:44 UTC  chat 13903713    catcherlab.com  score=66  provider=timeweb  message_id=597
2026-06-16 05:46 UTC  chat 13903713    catchhub.ru     score=74  provider=timeweb  message_id=612
2026-06-16 06:06 UTC  chat 7951273850  assistlab.io    score=70  provider=timeweb  message_id=613
2026-06-16 06:13 UTC  chat 7646078001  catchhub.ru     score=74  provider=timeweb  message_id=614
```

Each alert had an explainable payload:

```text
status=available
risk=provider_checked
provider=timeweb
buttons=why, more, less, never
items_count=1
```

## Acceptance Checks

- No repeated same-domain spam for the same destination: passed.
- No burst of multiple watchlist alerts to the same destination inside `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES=360`: passed.
- Main destination alert gaps:

```text
13903713  2026-06-15 17:42 -> 2026-06-15 23:43  gap 06:00:29
13903713  2026-06-15 23:43 -> 2026-06-16 05:44  gap 06:01:48
```

- Digest count is low and expected for configured watch rules: passed.
- Feedback callbacks produced audit events: passed.
- Telegram delivery errors: 0.
- Registration stayed disabled: passed.
- Fresh API logs for the final 24h window did not contain lines matching `error|exception|traceback|telegram_delivery_error`.

## Notes

- One earlier canary setup issue created TLDs without leading dots. Production rows were corrected and the code now normalizes watch-rule TLDs at store boundaries.
- Broad seed rules for the extra accounts were paused after verification. Exact canary rules remain active with one-alert daily limits.
- Monitoring can stay enabled for the closed pilot in the current conservative settings.

## Decision

GO for continued closed pilot with 1-5 trusted users.

NO-GO for broad public promotion until the legal/trust blockers are closed:

- legal review;
- legal entity/operator details;
- production support contacts;
- final retention periods;
- final provider/processor list;
- registration launch approval if registration is advertised.
