# LLM NLU Runbook

Updated: 2026-02-18

## Purpose
Use a free/low-cost LLM to parse free-form user messages into structured intents for Copilot, while keeping execution safety on backend.

## Safety Model
- LLM is used only for intent/entity extraction.
- Real action execution is still performed only by backend.
- Mutating actions (`create_watch`, `toggle_alerts`, `register_domain`) still require explicit confirmation token.
- If LLM fails or low confidence is returned, service falls back to deterministic rule-based parser.

## Providers
1. Primary: `ollama` (local model, no per-request cost).
2. Optional fallback: `openrouter` (free-tier models if configured).

For multi-project setup with one shared Ollama instance, see:
- `docs/shared_ollama_multi_project.md`

## Supported intents
- `create_watch`
- `toggle_alerts`
- `register_domain`
- `domain_check`
- `domain_suggest`
- `help`
- `qa`
- `chat`

## Env setup
```env
COPILOT_LLM_NLU_ENABLED=true
COPILOT_LLM_PROVIDER=ollama
COPILOT_LLM_TIMEOUT_SECONDS=12
COPILOT_LLM_CONFIDENCE_THRESHOLD=0.65
COPILOT_LLM_OLLAMA_BASE_URL=http://localhost:11434
COPILOT_LLM_OLLAMA_MODEL=qwen2.5:7b-instruct

COPILOT_LLM_FALLBACK_ENABLED=false
COPILOT_LLM_FALLBACK_BASE_URL=https://openrouter.ai/api/v1
COPILOT_LLM_FALLBACK_API_KEY=
COPILOT_LLM_FALLBACK_MODEL=qwen/qwen2.5-7b-instruct:free
```

## Quick local check
1. Start Ollama and pull model:
```bash
ollama pull qwen2.5:7b-instruct
```
2. Enable `COPILOT_LLM_NLU_ENABLED=true` in `.env`.
3. Restart API container/service.
4. Send Copilot message and verify `copilot_events` payload includes:
- `intent_source: llm` (when confidence >= threshold), or
- `intent_source: rules_llm_*` (fallback path).

## Observability
Every Copilot message logs:
- selected source (`llm` or fallback variant),
- LLM provider/model/confidence metadata,
- final intent/entities used for backend decision.
