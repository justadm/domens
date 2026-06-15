# Production Canary Report: 2026-06-14

Status: not passed for broader rollout.

Scope: production `idns.devee.ru`, MSK host, `domens` compose project.

## Snapshot

- Checked at: 2026-06-14 17:27 UTC.
- Production revision: `17069a5`.
- Compose services:
  - `domens-api-1`: healthy;
  - `domens-frontend-1`: running;
  - `domens-postgres-1`: healthy;
  - `domens-redis-1`: healthy.
- `/health`: `{"status":"ok"}`.
- `/ready`: `{"status":"ok","database":true,"telegram_configured":true,"monitoring_enabled":true,"registration_enabled":false}`.

## Safety Flags

- `REGISTRATION_ENABLED=false`.
- `REGISTRATION_REQUIRE_AVAILABLE_CHECK=true`.
- `MONITOR_ENABLED=true`.
- `MONITOR_WATCHLIST_ONLY=true`.
- `MONITOR_ADMIN_FANOUT_ENABLED=false`.
- `MONITOR_EVENT_LOGGING_ENABLED=true`.
- `MONITOR_EVENT_LOGGING_DETAIL=false`.
- `MONITOR_ALERT_GLOBAL_RUN_LIMIT=1`.
- `MONITOR_ALERT_PER_TARGET_RUN_LIMIT=1`.
- `MONITOR_ALERT_PER_TARGET_DAILY_LIMIT=1`.
- `MONITOR_ALERT_COOLDOWN_MINUTES=1440`.
- `TELEGRAM_POLLING_ENABLED=true`.
- `WEBHOOK_URL=https://idns.devee.ru/v1/telegram/webhook`.

Note: production revision `17069a5` does not include the later local fixes for protected operational endpoints, legal draft page, Selectel DNS reserve status, or target alert cooldown.

## 24h Monitor Event Counts

```text
monitor_alert_sent        3
monitor_alert_skipped     46197
monitor_candidate_checked 46200
monitor_candidates_built  250
monitor_run_finished      244
monitor_run_skipped       1
monitor_run_started       250
```

Skip reasons:

```text
status_not_interesting 42422
watch_daily_limit      3709
global_run_limit       63
recent_alert           3
```

Telegram/API logs did not show Telegram or monitor errors in the inspected 24h tail.

## Sent Alerts

All three alerts went to `13903713` from the same watch rule:

```text
2026-06-13 17:36 UTC catcherai.ru  score 70  matched_query "domain catcher"
2026-06-13 17:41 UTC catcherhub.ru score 66  matched_query "domain catcher"
2026-06-13 17:47 UTC catcherlab.ru score 66  matched_query "domain catcher"
```

No repeated same-domain alert was found for the same chat in the 24h window.

## Finding

The canary did not produce same-domain spam, but it did produce a short burst: three different watchlist alerts to one Telegram destination within about 11 minutes.

This is not acceptable for the quiet radar launch promise. The existing same-domain cooldown and daily limits prevent many repeats after the fact, but they did not prevent multiple different domains from reaching the same destination in a short interval when a watch rule allows more than one daily alert.

## Remediation

Local code now adds `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES=360`.

Expected effect:

- a destination can still receive a digest/run alert;
- additional watchlist alerts to the same destination are suppressed during the target cooldown window;
- digest behavior inside a single monitor run is preserved;
- short bursts across consecutive monitor runs are suppressed with `target_cooldown`.

Verification before this report:

- `PYTHONPATH=. .venv313/bin/pytest -q`: `102 passed`;
- `npm run build`: passed;
- `docker compose config --quiet`: passed;
- `docker compose -f deploy/docker-compose.nginx.yml config --quiet`: passed.

## Decision

NO-GO for public promotion or broader onboarding from this canary.

GO for continued closed pilot after deploying the local cooldown/auth/legal/safety fixes and observing another 24h canary window.

## Next Canary Acceptance Criteria

- zero repeated same-domain alerts per destination;
- no more than one watchlist alert/digest per destination inside `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES`;
- `monitor_alert_skipped` includes expected `target_cooldown` entries after the first alert;
- no Telegram delivery errors;
- registration remains disabled;
- `/health` and `/ready` stay green;
- feedback callbacks still work.
