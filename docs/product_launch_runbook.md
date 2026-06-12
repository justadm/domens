# Product launch runbook

## Pre-launch gates

- Backend tests pass: `PYTHONPATH=. .venv313/bin/pytest -q`
- Frontend build passes: `cd frontend && npm run build`
- Compose config is valid: `docker compose config --quiet`
- `/ready` returns `database=true`
- Telegram smoke script passes on MSK
- `MONITOR_ENABLED=false` until canary watchlist is configured
- `REGISTRATION_ENABLED=false` until manual approval

## Canary setup

1. Enable one admin watchlist.
2. Set daily alert limit to `1`.
3. Keep global monitoring disabled.
4. Observe 24 hours.
5. Confirm:
   - no repeated same-domain spam;
   - alerts include explanation;
   - feedback callbacks work;
   - `/help` and `/profile` work;
   - quality metrics are visible.

## Rollback

1. Set `MONITOR_ENABLED=false`.
2. Recreate API service.
3. Confirm `/ready` and `/health`.
4. Keep frontend running unless UI itself is the incident source.
