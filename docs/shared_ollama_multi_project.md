# Shared Ollama For Multiple Projects

Updated: 2026-02-18

## Goal
Run one Ollama instance and one model set on server, then connect multiple projects to it with isolated project-specific NLU connectors.

## Architecture
- Shared service:
  - `ollama-shared` on host `127.0.0.1:11434`
  - model cache stored once (`ollama_data`)
- Per-project service:
  - own API/backend
  - own prompt, intent schema, dictionaries, confirmation logic
  - own confidence threshold and fallback policy

This gives shared compute + strict behavior isolation.

## Deploy Shared Ollama
From this repository:
```bash
cd /opt/domens/deploy
docker compose -f docker-compose.shared-ollama.yml up -d
docker exec -it ollama-shared ollama pull qwen2.5:7b-instruct
docker exec -it ollama-shared ollama list
```

## Configure Domens project
In `/opt/domens/.env`:
```env
COPILOT_LLM_NLU_ENABLED=true
COPILOT_LLM_PROVIDER=ollama
COPILOT_LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434
COPILOT_LLM_OLLAMA_MODEL=qwen2.5:7b-instruct
COPILOT_LLM_CONFIDENCE_THRESHOLD=0.65
```

If API container cannot resolve `host.docker.internal` on Linux, use host gateway:
- add `extra_hosts: ["host.docker.internal:host-gateway"]` in project compose for API service.

Alternative:
- place project containers and `ollama-shared` into one custom Docker network and call `http://ollama:11434`.

## Configure Other Projects
For each project:
1. Point connector to the same `COPILOT_LLM_OLLAMA_BASE_URL`.
2. Keep project-specific prompt/schema/intents only in that project codebase.
3. Keep separate logs/metrics and strict action confirmation.

## Isolation Rules (must keep)
- Never execute side effects directly from model output.
- Validate intent/entity JSON against project allowlist.
- Use project-specific confidence thresholds.
- Keep fallback parser enabled.

## Capacity Notes
- One 7B model is good for MVP and small traffic.
- Under load, queue requests on project side and cap timeout (`10-15s`).
- If needed later:
  - move to stronger host,
  - pin dedicated model per critical project,
  - or run second Ollama instance for heavy workloads.
