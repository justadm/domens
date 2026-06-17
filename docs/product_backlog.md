# Product backlog

Updated: 2026-06-16

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
- Web cabinet radar preferences are available in the LK:
  - watch rules;
  - hidden domains/suppressions;
  - suppression deletion.
- Cabinet preferences require a real user session; guest auth fallback is not accepted for these sensitive routes.
- Web cabinet alert history is available with explanation, feedback, and suppression state.
- Web cabinet digest history is available from monitor digest audit events.
- Cabinet alert history and feedback require a real user session; guest auth fallback is not accepted.
- Watchlist alerts are grouped into a per-chat Telegram digest by default (`MONITOR_DIGEST_ENABLED=true`).
- Watchlist alerts are spaced per destination by `MONITOR_ALERT_TARGET_COOLDOWN_MINUTES` to avoid short bursts.
- Sensitive operational endpoints for manual checks, candidate ingestion, alert triggering, and monitor runs require an admin session.
- Admin quality dashboard/API shows launch canary metrics:
  - alert, feedback, suppression totals;
  - monitor runs, checked candidates, sent alerts/digests;
  - skip reasons and Telegram delivery errors;
  - registration and monitoring safety flags.
- Admin API requires a real session cookie; guest auth fallback is not accepted for admin routes.
- Registration remains safe: disabled by default in production, requires explicit confirmation and fresh availability checks before execution.
- Gitea is the primary git remote (`origin`); GitHub is a backup remote (`github`).

## Remaining priority work

1. 24h canary follow-up
- First production canary report exists: `docs/canary/2026-06-14-production-canary.md`.
- Result: not passed for broader rollout because three different watchlist alerts reached one destination in about 11 minutes.
- Fresh canary report after cooldown/auth/legal/safety fixes exists: `docs/canary/2026-06-16-production-canary-report.md`.
- Result: accepted for continued closed pilot.
- Follow-up:
  - keep conservative monitoring flags for pilot users;
  - keep registration disabled;
  - record a new canary report before changing alert limits or onboarding broader traffic.

2. Web cabinet parity with Telegram
- Baseline radar preferences, alert history, and digest history are shipped in the cabinet.
- Digest items can open all linked alert rows via multi-domain alert filtering.
- Remaining parity: none for the current closed-pilot alert/digest workflow.

3. Admin quality dashboard follow-up
- Baseline admin quality report is shipped.
- Follow-up:
  - add time-series trend view;
  - add explicit duplicate/same-domain grouping;
  - add feedback precision ratios;
  - add export/share link for auditor reports.

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
- Record a fresh canary report before broader user rollout or less conservative alert limits.

6. Trust and source transparency from competitive audit
- Do not compete on broad auction search. Keep the product promise focused on Telegram-first explainable radar.
- Add public "no front-running" wording before paid or public promotion.
- Add a visible data deletion path for:
  - watch rules;
  - Telegram account link;
  - alert/query history where legally and operationally allowed.
- Add provider confidence tiers and source health status to alerts or cabinet views.
- Build a canary examples library showing why alerts were sent and how feedback changed future alerts.
- Map promo/product metrics to actual DB or log events before reporting them externally.

7. Legal package for public promotion
- Draft privacy policy, offer/agreement, support/disclaimer docs exist in `docs/legal/`.
- Legal package index exists: `docs/legal/README.md`.
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
