# Product backlog

Updated: 2026-06-14

## Product direction

Position the service as a quiet, precise Telegram-first domain radar, not as a generic domain checker.

Core promise:
- user defines themes, TLDs, length/budget preferences, and risk tolerance;
- service expands those ideas into candidates;
- service sends only high-confidence, explainable alerts;
- registration is always explicit and safe.

## Current shipped baseline

The Telegram-first launch baseline is now implemented and deployed:

- Telegram bot answers `/start`, `/help`, `/profile`, `/limits`, `/watch`, `/alerts`, `/menu`, `/preferences`, and `/commands`.
- Main Telegram menu uses compact human-readable buttons with icons.
- Profile and limits responses are user-facing; technical IDs are not part of the normal profile output.
- Monitoring is watchlist-first in production canary mode:
  - `MONITOR_WATCHLIST_ONLY=true`;
  - `MONITOR_ADMIN_FANOUT_ENABLED=false`;
  - conservative per-run and daily limits;
  - duplicate suppression survives restarts.
- Alerts include explanations and feedback buttons.
- "More like this" creates a quiet personal watch rule.
- "Less like this" creates a user-level suppression.
- "Never repeat" suppresses the domain for the user.
- Telegram preferences let users inspect watch rules and hidden domains, then delete them from inline buttons.
- Watchlist alerts are grouped into a per-chat Telegram digest by default (`MONITOR_DIGEST_ENABLED=true`).
- Watchlist alerts are spaced per destination by `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES` to avoid short bursts.
- Sensitive operational endpoints for manual checks, candidate ingestion, alert triggering, and monitor runs require an admin session.
- Registration remains safe: disabled by default in production, requires explicit confirmation and fresh availability checks before execution.
- Gitea is the primary git remote (`origin`); GitHub is a backup remote (`github`).

## Remaining priority TODO

1. 24h canary report
- First production canary report exists: `docs/canary/2026-06-14-production-canary.md`.
- Result: not passed for broader rollout because three different watchlist alerts reached one destination in about 11 minutes.
- Local remediation adds `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES=360`; deploy and observe a fresh 24h window.
- For each canary, record daily totals:
  - monitor runs;
  - checked candidates;
  - sent digests;
  - skipped/suppressed alerts by reason;
  - Telegram delivery errors;
  - feedback callbacks.
- Confirm no repeated same-domain spam for the same destination.

2. Web cabinet parity with Telegram
- Expose the same daily-use controls in the cabinet:
  - watch rule preferences;
  - hidden domains/suppressions;
  - alert explanations;
  - feedback state;
  - digest/history view.

3. Admin quality dashboard
- Build a simple visible admin report for:
  - daily alert/digest volume;
  - duplicate suppression;
  - skip reasons;
  - feedback precision signals;
  - Telegram delivery errors;
  - registration safety state.

4. Registration launch gate
- Keep `REGISTRATION_ENABLED=false` until an explicit product/ops decision.
- Before enabling:
  - verify provider availability checks;
  - verify stale/unknown availability is blocked;
  - run one manual registration dry-run or approved low-risk real flow;
  - document rollback.

5. Documentation cleanup and launch evidence
- Keep this backlog and runbooks current after each launch-related patch.
- Mark historical implementation plans as superseded when they no longer track shipped state.
- Record the final canary report before broader user rollout.

6. Legal package for public promotion
- Draft privacy policy, offer/agreement, support/disclaimer docs exist in `docs/legal/`.
- Public launch still requires:
  - legal review;
  - legal entity/operator details;
  - production support contacts;
  - final retention periods;
  - final provider/processor list;
  - final responsibility/disclaimer text for domain availability and registration outcomes.

## Operational state

1. Telegram route recovery
- MSK not_RU traffic is routed through `wg0` to AMS2; expected external IP is `72.56.22.18`.
- Telegram API access from `domens-api-1` was restored after the routing/MSS clamp change.
- Bot command smoke has passed in production after deploys.

2. Telegram delivery mode
- Production currently uses polling; Telegram webhook URL is expected to stay empty in this mode.
- Polling is acceptable for launch while Telegram egress depends on the non-RU uplink.
- If switching to webhook later, use `docs/prod_checklist_idns.md` and run command smoke immediately after the switch.

3. Monitoring restart policy
- Monitoring can run only in conservative canary settings until a 24h report is accepted.
- Keep event logging enabled during canary; keep detailed payload logging off unless debugging.
- Roll back by setting `MONITOR_ENABLED=false` and recreating the API service.

## Success criteria

- Users receive fewer alerts, but each alert is explainable.
- No repeated same-domain spam.
- `/help`, `/profile`, `/menu`, `/preferences`, and feedback callbacks work reliably.
- Stage and production have explicit monitoring settings, never implicit defaults.
- Registration is still disabled until explicitly approved.
