# Shared Ollama For Multiple Projects

Updated: 2026-02-18

## Goal
Run one Ollama instance and one model set on server, then connect multiple projects to it with isolated project-specific NLU connectors.

## Conflict Prevention (important)
Use only one Ollama runtime on server:
1. Host/systemd Ollama (as in ChatMarketAI runbook), or
2. Docker `ollama-shared` container.

Do not run both at the same time on `11434`, otherwise port and routing conflicts are expected.

Before changing runtime mode, run preflight from ChatMarketAI ops:
```bash
./scripts/ollama_runtime_preflight.sh
```

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

If host/systemd Ollama is already used by other project:
- skip container deployment above,
- reuse existing host endpoint and keep one shared model store.

## Configure Domens project
In `/opt/domens/.env`:
```env
COPILOT_LLM_NLU_ENABLED=true
COPILOT_LLM_PROVIDER=ollama
COPILOT_LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434
COPILOT_LLM_OLLAMA_MODEL=qwen2.5:0.5b
COPILOT_LLM_CONFIDENCE_THRESHOLD=0.65
```

If API container cannot resolve `host.docker.internal` on Linux, use host gateway:
- add `extra_hosts: ["host.docker.internal:host-gateway"]` in project compose for API service.

Alternative (recommended if using dockerized Ollama):
- place project containers and `ollama-shared` into one custom Docker network and call `http://ollama-shared:11434`.

Alternative (when host bind is `0.0.0.0:11434` and firewall allows docker subnet):
- detect project docker gateway IP and use `http://<gateway-ip>:11434`.
- example:
```bash
DOCKER_GATEWAY_IP="$(docker network inspect domens_default -f '{{(index .IPAM.Config 0).Gateway}}')"
echo "$DOCKER_GATEWAY_IP"
```

If `api` runs directly on host (not inside container), use:
- `COPILOT_LLM_OLLAMA_BASE_URL=http://127.0.0.1:11434`.

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
- `qwen2.5:0.5b` is recommended for MVP on low RAM hosts.
- `qwen2.5:7b-instruct` is recommended when RAM is 8+ GB (better quality for intent parsing).
- Under load, queue requests on project side and cap timeout (`10-15s`).
- If needed later:
  - move to stronger host,
  - pin dedicated model per critical project,
  - or run second Ollama instance for heavy workloads.

## Recommended Single Runtime
Given existing ChatMarketAI setup, preferred approach:
1. Keep host/systemd Ollama as shared runtime.
2. Point Domens and other projects to `http://host.docker.internal:11434` (from containers).
3. Keep per-project connectors isolated in each codebase.
