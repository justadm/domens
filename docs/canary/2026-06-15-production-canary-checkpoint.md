# Production Canary Checkpoint: 2026-06-15

Status: in progress.

Scope: production `idns.devee.ru`, MSK host, `domens` compose project.

This checkpoint tracks the fresh quiet-radar canary window started after the cooldown/auth/legal/safety fixes were deployed.

## Window

- Canary start: 2026-06-15 07:06:40 UTC.
- Checkpoint time: 2026-06-15 07:39:31 UTC.
- Production revision at checkpoint: `9a4e255`.
- Latest repository revision at checkpoint: `94a37cf`.

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

## Logging Follow-Up

Local code now adds `target_cooldown_minutes` to the `monitor_run_started` audit payload. This makes canary evidence self-contained in `bot_events` instead of requiring a separate container config probe.

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
