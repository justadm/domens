# Port Registry (Domens)

Last updated: 2026-02-19

Источник хоста: `/Users/just/projects/ChatMarketAI/docs/PORT_REGISTRY.md`.

## Assigned / reserved for domens

| Port | Bind | Owner | Service | Status |
|---|---|---|---|---|
| 28080 | 127.0.0.1 | domens | backend api (container:8080) | active |
| 28200 | 127.0.0.1 | domens | frontend spa (container:80/3000) | reserved |

## Shared host constraints (important)

- `28100` reserved by ChatMarketAI frontend (do not use).
- `28000` occupied by ChatMarketAI backend (do not use).
- `19001-19015`, `19100-19101` occupied by internal deploy/mcp toolchain.
- Public entrypoints must remain on nginx (`80/443`), app containers only loopback binds.

## Nginx routing target (planned split FE/BE)

- `/v1/*`, `/docs`, `/openapi.json`, `/health` -> `127.0.0.1:28080` (backend)
- `/`, `/lk/*`, `/admin/*` -> `127.0.0.1:28200` (frontend SPA)

## Rules

1. Before any new bind: check `ss -ltnp` on server.
2. Update this file in the same commit as infra/nginx port changes.
3. Keep all project app ports on `127.0.0.1` only.
