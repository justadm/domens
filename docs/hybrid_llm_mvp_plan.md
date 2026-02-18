# Hybrid LLM MVP Plan (0.5b + 7b)

Updated: 2026-02-18

## Goal
Make assistant behavior stable and predictable for operations, while keeping better conversational quality.

Target architecture:
- Intent parsing (commands/actions): `qwen2.5:0.5b` + rules-first.
- Chat/QA (free-form answers): `qwen2.5:7b-instruct`.
- All mutating actions remain behind explicit confirmation.

## Why this split
- `0.5b` is faster and more stable for intent classification and entity extraction.
- `7b` is better for language quality and less robotic conversational output.
- Rules-first prevents dangerous drift and random intent changes.

## Runtime config
Required env:
- `COPILOT_LLM_NLU_ENABLED=true`
- `COPILOT_LLM_PROVIDER=ollama`
- `COPILOT_LLM_INTENT_MODEL=qwen2.5:0.5b`
- `COPILOT_LLM_REPLY_MODEL=qwen2.5:7b-instruct`
- `COPILOT_LLM_INTENT_TIMEOUT_SECONDS=12`
- `COPILOT_LLM_REPLY_TIMEOUT_SECONDS=35`
- `COPILOT_LLM_OLLAMA_BASE_URL=<reachable from api container>`

Knowledge context:
- `COPILOT_LLM_KNOWLEDGE_ENABLED=true`
- `COPILOT_LLM_KNOWLEDGE_FILES=README.md,docs/copilot_feature.md,docs/api_contracts.md,docs/telegram_bot_scope.md`
- `COPILOT_LLM_KNOWLEDGE_MAX_CHARS=2400`

## State machine constraints
Assistant states:
- `chat`: normal conversation.
- `qa`: direct question/answer mode.
- `action_intent`: intent recognized, action candidate prepared.
- `await_confirm`: confirmation token issued.
- `done`: action executed/canceled/expired.

Rules:
- No action execution without `await_confirm`.
- If required entities are missing, ask deterministic clarifying question.
- If intent confidence is below threshold, fallback to strict format hint.

## Quality gates
Before deploy:
1. Regression pack for intents:
   - real user phrases,
   - typo-heavy phrases,
   - slang variants.
2. Safety pack:
   - register/watch/alerts cannot run without confirmation.
3. Language pack:
   - no broken RU/EN templates,
   - no repetitive loops.

Metrics to monitor:
- intent mismatch rate,
- clarification rate,
- confirmation-to-execution conversion,
- timeout/error rate by model,
- p95 latency for intent/reply separately.

## Rollout plan
1. Local:
   - enable split models,
   - run regression tests.
2. Staging/prod canary:
   - small period with active observation,
   - compare with current baseline.
3. Full rollout:
   - keep rollback profile ready:
     - disable LLM entirely (`COPILOT_LLM_NLU_ENABLED=false`) if needed.

## Known risks
- `7b` reply latency can spike on cold start or concurrent calls.
- bad prompts can still cause repetitive answers.
- overly broad knowledge snippets can reduce precision.

Mitigations:
- separate timeouts for intent vs reply,
- strict fallback behavior,
- keep snippets short and curated.
