# Product backlog

Updated: 2026-06-12

## Product direction

Position the service as a quiet, precise Telegram-first domain radar, not as a generic domain checker.

Core promise:
- user defines themes, TLDs, length/budget preferences, and risk tolerance;
- service expands those ideas into candidates;
- service sends only high-confidence, explainable alerts;
- registration is always explicit and safe.

## Priority TODO

1. Quiet radar mode
- Default to very low alert volume: 1-3 strong alerts per user per day.
- Never repeat the same domain to the same destination unless status or score materially changed.
- Add global and per-destination duplicate suppression that survives restarts.
- Make `MONITOR_ENABLED=false` the safe default for stage/prod until a real watchlist is configured.

2. Alert explanation
- Each alert should explain why it was sent:
  - score;
  - status source/provider;
  - matching watch query or trend;
  - TLD and length;
  - known risks or uncertainty.
- Add "why this domain" data to the alert payload and UI history.

3. Personal watchlists over global monitoring
- Treat user watchlists as the primary product surface.
- Let users configure:
  - themes/keywords;
  - TLD allowlist;
  - min score;
  - max length;
  - max daily alerts;
  - optional budget/registrar preferences.
- Keep global monitoring only as admin/demo mode.

4. Feedback loop
- Add Telegram buttons:
  - "More like this";
  - "Less like this";
  - "Mute this root";
  - "Mute this TLD";
  - "Never repeat".
- Persist feedback and use it in scoring and alert suppression.

5. Trust and safety
- Keep `REGISTRATION_ENABLED=false` by default outside explicitly approved production mode.
- For any registration alert, show availability confidence and provider check time.
- Require fresh availability check immediately before registration.
- Add an explicit warning when provider check is unavailable or stale.

6. Metrics for product quality
- Track alert precision:
  - opened/clicked alerts;
  - "register" intent;
  - muted/dismissed alerts;
  - repeated-domain suppressions;
  - false positive status corrections.
- Build a simple admin report for daily alert volume and precision.

7. Telegram menu UX
- Current command-first flow is not convenient enough for daily use.
- Design a compact `/menu` entry point with the main jobs:
  - watch rules;
  - alerts;
  - profile;
  - help;
  - recent candidates;
  - feedback/settings.
- Add Telegram command list setup for discoverability.
- Prefer short guided flows over asking users to remember command syntax.

## Operational TODO

1. Telegram route recovery
- Routing update from MSK operator: not_RU traffic is now routed through `wg0` to AMS2; expected external IP is `72.56.22.18`.
- Re-check from `domens-api-1`:
  - TCP/TLS to `api.telegram.org:443`;
  - `getWebhookInfo`;
  - `sendMessage` smoke to admin chat.

2. Telegram delivery mode
- Current stage behavior after MSK route recovery: bot works through polling (`TELEGRAM_POLLING_ENABLED=true`), and Telegram webhook URL is empty.
- Decide before launch whether production should use polling or webhook.
- If webhook mode is chosen:
  - ensure Telegram webhook URL is `https://idns.devee.ru/v1/telegram/webhook`;
  - set `TELEGRAM_POLLING_ENABLED=false`;
  - send `/help` and `/profile`;
  - verify fresh `incoming_message`, `command_help`, and `command_profile` rows in `bot_events`.
- If polling mode is chosen:
  - document why polling is preferred for current routing;
  - monitor polling errors in API logs;
  - keep webhook URL empty.

3. Monitoring restart policy
- Keep monitoring disabled on stage until alert suppression and per-user watchlist limits are in place.
- When re-enabling, start with low limits and verify no duplicate alerts for at least 24 hours.

## Success criteria

- Users receive fewer alerts, but each alert is explainable.
- No repeated same-domain spam.
- `/help` and `/profile` work reliably after routing/webhook recovery.
- Stage and production have explicit monitoring settings, never implicit defaults.
