# Privacy Policy Draft

Status: draft for closed pilot. Requires legal review before public launch.

Updated: 2026-06-14

## Scope

Domens Radar is a Telegram-first domain monitoring service. The service helps users maintain watch rules, receive explainable domain alerts, provide feedback, and explicitly confirm registration actions.

## Data We May Process

- Telegram identifiers: user ID, chat ID, username, first name, locale.
- Account state: roles, permissions, disclaimer acceptance, alert preferences, watch rules.
- Product data: domain candidates, scores, alert explanations, feedback actions, suppression preferences, registration orders.
- Technical logs: authentication events, bot events, delivery status, monitoring audit events, errors.
- Contact data: support requests and communication history if the user contacts support.

## Processing Purposes

- Provide domain watchlists and alert delivery.
- Prevent repeated or unwanted alerts.
- Execute explicit user actions, including registration confirmation when registration is enabled.
- Keep security, access, audit, and abuse-prevention logs.
- Improve alert quality during the closed pilot.
- Respond to support requests.

## Registration Safety

Registration is disabled by default unless explicitly enabled by operators. Availability checks can be stale or inconclusive, so the service must not present a DNS zone reserve as a completed domain registration.

## Storage And Retention

Operational data is stored in PostgreSQL. Retention periods must be finalized before public launch. Draft defaults for review:

- security and access audit: 12 months;
- alert history and feedback: 12 months;
- support communications: 24 months;
- technical error logs: 90 days.

## User Requests

Before public launch, define a support channel for:

- data export;
- data correction;
- data deletion;
- consent withdrawal;
- questions about domain registration orders.

## Third-Party Services

The service may interact with:

- Telegram Bot API for bot messages and callbacks;
- registrar/provider APIs for availability checks and registration operations;
- hosting, database, and monitoring infrastructure.

Finalize the exact list of processors and provider links before public launch.

## Required Before Public Launch

- Add legal entity or operator details.
- Add support email or support bot.
- Add final retention periods.
- Add processor/provider list.
- Add personal data processing basis and jurisdiction-specific language.
- Complete legal review.
