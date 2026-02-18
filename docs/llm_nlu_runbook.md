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

## Runtime mode (to avoid conflicts)
Choose one shared Ollama runtime on server:
1. Host/systemd Ollama (recommended if already used by other projects), or
2. Dockerized Ollama service.

Do not run both on the same `11434` endpoint.

Before switching mode, run runtime preflight from shared ops repo:
```bash
./scripts/ollama_runtime_preflight.sh
```

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
COPILOT_LLM_MAX_PARALLEL=1
COPILOT_LLM_CHAT_CONTEXT_MESSAGES=5
COPILOT_LLM_REPLY_MAX_CHARS=700
COPILOT_LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434
COPILOT_LLM_OLLAMA_MODEL=qwen2.5:0.5b

COPILOT_LLM_FALLBACK_ENABLED=false
COPILOT_LLM_FALLBACK_BASE_URL=https://openrouter.ai/api/v1
COPILOT_LLM_FALLBACK_API_KEY=
COPILOT_LLM_FALLBACK_MODEL=qwen/qwen2.5-7b-instruct:free
COPILOT_RATE_LIMIT_WINDOW_SECONDS=60
COPILOT_RATE_LIMIT_REQUESTS=12
COPILOT_DEGRADE_INFLIGHT_THRESHOLD=4
```

Endpoint notes:
- API in Docker container -> `http://host.docker.internal:11434` (+ `extra_hosts: host-gateway`).
- API in Docker container (gateway mode) -> `http://<docker-gateway-ip>:11434`.
- API on host machine -> `http://127.0.0.1:11434`.
- Same docker network with ollama container -> `http://ollama-shared:11434`.

## Quick local check
1. Start Ollama and pull model:
```bash
ollama pull qwen2.5:0.5b
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
- conversational answer metadata (`reply_style`, `answer_source`, `context_used`, `trim_reason`).

Admin runtime snapshot:
- `GET /v1/admin/copilot-runtime`
- includes `enabled/model/fallback`, rate-limit settings and current inflight/degrade counters.

## Deploy smoke (after each push)
1. `GET /health` -> `200`.
2. `GET /v1/admin/copilot-runtime` (admin auth) -> verify model + limits.
3. Send 1-2 normal Copilot requests -> `200`.
4. Send burst above limit -> expect `429`.
5. Check `copilot_events` for `message_received`, `assistant_reply`, and overload events (`rate_limited`, `degraded_mode` if triggered).

## Model profile
- Low RAM MVP: `qwen2.5:0.5b`.
- Better intent quality (8+ GB RAM): `qwen2.5:7b-instruct`.
