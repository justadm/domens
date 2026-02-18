# Copilot Feature (Free-Form Requests)

Updated: 2026-02-18

## Goal
Allow client to write requests in free form:
- ask a question,
- chat in natural language,
- request functional actions (watch rules, alerts, registration),
while enforcing explicit confirmation before any state-changing action.

## User Flows
1. User sends free-form message via web widget:
   - `Задать вопрос` (assistant mode),
   - `Просто поговорить` (chat mode).
2. System detects intent + entities + confidence.
3. If action is mutating:
   - system creates action preview,
   - issues one-time confirmation token (`cp_*`, TTL 5 min),
   - waits for user decision.
4. User confirms/cancels.
5. System executes action and returns structured result.

Parity channels:
- Web LK: buttons `Задать вопрос` / `Просто поговорить`.
- Telegram: `/ask`, `/chat`, `/confirm <cp_token>`, `/cancel <cp_token>`.
- MAX: `/ask`, `/chat`, `/confirm <cp_token>`, `/cancel <cp_token>` in incoming text.

## API
- `POST /v1/copilot/message`
  - input: `message`, `mode`, `conversation_id`, `channel`
  - output: `reply`, `intent`, `confidence`, optional `confirmation_token`, `action_preview`
- `POST /v1/copilot/confirm`
  - input: `confirmation_token`, `decision=confirm|cancel`
  - output: final `status` + `execution_result`

## Current Intent Set (MVP)
- `create_watch` -> add watch rule (requires confirm)
- `toggle_alerts` -> on/off telegram alerts (requires confirm)
- `register_domain` -> create+execute registration flow (requires confirm)
- `domain_check` -> status check with provider inference (no confirm)
- `domain_suggest` -> generate candidate names by topic+TLD, filter noisy names, prioritize actionable statuses (`available/pending_delete/redemption/client_hold`) before reply (no confirm)
- `help|qa|chat` -> conversational answer (no confirm)

## Language handling
- Response language is derived from stored user `locale` (`en*` -> English, otherwise Russian).
- Web UI language auto-switches from profile `locale` unless user manually overrides language selector.

## Detailed Logging (High Verbosity)
All copilot steps are persisted:
- raw incoming message,
- parsed intent/entities/confidence,
- assistant response,
- confirmation request/decision,
- action execution result/failure.

DB tables:
- `conversations`
- `conversation_messages`
- `copilot_action_confirmations`
- `copilot_events`

This is in addition to existing `bot_events` and `access_events`.

## Safety Rules
- No mutating action runs without explicit confirmation.
- Confirmation token is one-time and TTL-bound.
- Expired or already processed token cannot be re-executed.
- Real domain purchase still respects existing env guards (`REGISTRATION_ENABLED`, provider checks).
