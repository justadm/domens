# Product launch runbook

## Pre-launch gates

- Backend tests pass: `PYTHONPATH=. .venv313/bin/pytest -q`
- Frontend build passes: `cd frontend && npm run build`
- Compose config is valid: `docker compose config --quiet`
- `/ready` returns `database=true`
- Telegram smoke script passes on MSK
- `MONITOR_ENABLED=false` until canary watchlist is configured
- `MONITOR_WATCHLIST_ONLY=true` for the first canary
- `MONITOR_ADMIN_FANOUT_ENABLED=false` for the first canary
- `MONITOR_EVENT_LOGGING_ENABLED=true` while canary is under observation
- `MONITOR_EVENT_LOGGING_DETAIL=false` by default; enable only for short diagnostics
- `MONITOR_DIGEST_ENABLED=true` unless intentionally testing the legacy one-alert-per-message mode
- `REGISTRATION_ENABLED=false` until manual approval
- Primary git remote is Gitea `origin`; GitHub remote is backup-only.

## Canary setup

1. Enable one admin watchlist.
2. Set daily alert limit to `1`.
3. Keep global registration disabled.
4. Run the first canary in watchlist-only mode:
   - `MONITOR_ENABLED=true`;
   - `MONITOR_WATCHLIST_ONLY=true`;
   - `MONITOR_ADMIN_FANOUT_ENABLED=false`;
   - `MONITOR_EVENT_LOGGING_ENABLED=true`;
   - `MONITOR_EVENT_LOGGING_DETAIL=false`;
   - `MONITOR_DIGEST_ENABLED=true`;
   - `MONITOR_ALERT_GLOBAL_RUN_LIMIT=1`;
   - `MONITOR_ALERT_PER_TARGET_RUN_LIMIT=1`;
   - `MONITOR_ALERT_PER_TARGET_DAILY_LIMIT=1`;
   - `MONITOR_ALERT_COOLDOWN_MINUTES=1440`;
   - `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES=360`.
5. Observe 24 hours.
6. Confirm:
   - no repeated same-domain spam;
   - alerts include explanation;
   - feedback callbacks work;
   - `/help` and `/profile` work;
   - quality metrics are visible.
7. Inspect monitor audit events:

```bash
ssh msk 'docker exec -i domens-postgres-1 psql -U domens -d domens -c "select created_at,event_type,telegram_chat_id,payload from bot_events where event_type like '\''monitor_%'\'' order by created_at desc limit 50;"'
```

Expected event types include:
- `monitor_run_started`;
- `monitor_candidates_built`;
- `monitor_candidate_checked`;
- `monitor_alert_skipped`;
- `monitor_alert_sent`;
- `monitor_digest_sent`;
- `monitor_run_finished`.

## 24h canary report

After a full day in canary mode, capture enough evidence to decide whether the radar can stay on.

Run on MSK:

```bash
ssh msk 'docker exec -i domens-postgres-1 psql -U domens -d domens -c "select event_type, count(*) from bot_events where created_at >= now() - interval '\''24 hours'\'' and event_type like '\''monitor_%'\'' group by event_type order by event_type;"'
```

Check latest skipped/sent details:

```bash
ssh msk 'docker exec -i domens-postgres-1 psql -U domens -d domens -c "select created_at,event_type,telegram_chat_id,payload from bot_events where created_at >= now() - interval '\''24 hours'\'' and event_type like '\''monitor_%'\'' order by created_at desc limit 100;"'
```

Acceptance criteria:
- no repeated same-domain spam for one user/chat;
- no burst of multiple watchlist alerts to the same destination inside `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES`;
- `monitor_digest_sent` count is low and expected for configured watch rules;
- skip reasons are understandable (`same_domain`, `daily_limit`, `recent_alert`, `user_less`, `user_never`, low score, provider status);
- Telegram command smoke still passes;
- feedback callbacks create visible store changes;
- no unexpected registration execution attempts while `REGISTRATION_ENABLED=false`.

Save the canary result in the project notes or MemLayer with:
- observed window;
- env flags;
- event counts;
- notable domains sent or suppressed;
- decision: keep on, tune limits, or rollback.

## Rollback

1. Set `MONITOR_ENABLED=false`.
2. Recreate API service.
3. Confirm `/ready` and `/health`.
4. Keep frontend running unless UI itself is the incident source.
5. If digest-specific behavior is the incident source, set `MONITOR_DIGEST_ENABLED=false` and recreate the API service as a narrower rollback.
