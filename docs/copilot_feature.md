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
   - `Отправить` (assistant mode).
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
  - Supports explicit mode in prompt:
    - `только свободные` / `only available` -> return only actionable statuses
    - `все с приоритетом` / `all with priority` -> include fallback but rank actionable first
- `help|qa|chat` -> conversational answer (no confirm)

## LLM NLU (optional)
- Added optional NLU layer before rule-based parser.
- Expected model output is strict JSON (`intent`, `confidence`, `entities`).
- If model confidence is below threshold or provider fails, parser falls back to current rule-based intent detection.
- Even with LLM enabled, mutating actions still require explicit confirmation token.
- For `help|qa|chat`, optional conversational reply generation is enabled via the same LLM stack with short context window.

Env flags:
- `COPILOT_LLM_NLU_ENABLED` - enable/disable LLM NLU layer.
- `COPILOT_LLM_PROVIDER` - `ollama` or `openrouter`.
- `COPILOT_LLM_TIMEOUT_SECONDS` - timeout for model call.
- `COPILOT_LLM_CONFIDENCE_THRESHOLD` - minimum confidence to trust LLM output.
- `COPILOT_LLM_MAX_PARALLEL` - max concurrent LLM calls (CPU protection).
- `COPILOT_LLM_CHAT_CONTEXT_MESSAGES` - recent messages count used for conversational replies.
- `COPILOT_LLM_REPLY_MAX_CHARS` - max response length before trimming.
- `COPILOT_LLM_OLLAMA_BASE_URL`, `COPILOT_LLM_OLLAMA_MODEL` - local Ollama settings.
- `COPILOT_LLM_FALLBACK_ENABLED` - enable provider fallback.
- `COPILOT_LLM_FALLBACK_BASE_URL`, `COPILOT_LLM_FALLBACK_API_KEY`, `COPILOT_LLM_FALLBACK_MODEL` - fallback provider settings.
- `COPILOT_RATE_LIMIT_WINDOW_SECONDS`, `COPILOT_RATE_LIMIT_REQUESTS` - overload protection per user.
- `COPILOT_DEGRADE_INFLIGHT_THRESHOLD` - inflight threshold to switch into soft-degrade mode (template/rules-first).

## Overload protection
- Per-user rate-limit is applied to `POST /v1/copilot/message` (HTTP `429` on excess).
- Under high inflight load Copilot switches to fast mode:
  - intent parsing falls back to rules,
  - conversational reply falls back to template.
- Degrade mode is reflected in logs (`degrade_reason`) and admin runtime endpoint.

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
- conversational metadata:
  - `reply_style` (`natural|template`)
  - `answer_source` (`llm:*|template*`)
  - `context_used` (history messages count)
  - `trim_reason` (if response was shortened)

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
