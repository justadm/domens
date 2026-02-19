# Frontend Migration Plan (Vue)

## Goal
Move from embedded static frontend (`web/index.html + web/app.js`) to a separate Vue SPA while keeping backend API and RBAC model intact.

## Principles
- One UI shell for LK and Admin.
- Differences only by capabilities/roles.
- Backend remains source of truth for permissions.
- Incremental migration with fallback to old frontend during rollout.

## New frontend root
- `frontend/`

## Phase map
1. Bootstrap
- Create Vue app with Router + Pinia.
- Add shared shell and RBAC menu filtering.
- Add route guards by capability.

2. Core auth/session
- Implement `/v1/auth/me` hydration on app start.
- Implement logout and capability state in store.

3. LK migration
- Migrate pages in order:
  - `/lk` dashboard
  - `/lk/watch`
  - `/lk/alerts`
  - `/lk/registrations`
  - `/lk/history`

4. Admin migration
- Migrate pages in order:
  - `/admin` dashboard
  - `/admin/users`
  - `/admin/events`

5. Cleanup
- Remove duplicated logic from old `web/app.js`.
- Keep static landing in backend (`/`) or migrate it to Vue route as needed.

## RBAC matrix source
Use backend capabilities from `/v1/auth/me` and endpoint-level checks already implemented.
Primary capabilities used by frontend menu and route guards:
- `cabinet.read`
- `watch.manage`
- `alerts.manage`
- `copilot.register_domain`
- `admin.panel.read`

## Deployment model
- Option A (simple): build Vue and serve via existing nginx as static files.
- Option B (clean split): separate frontend container + nginx upstream.

## Current status
- Bootstrap created in `frontend/` with:
  - shared shell,
  - auth store,
  - capability-based menu,
  - lk/admin route trees,
  - starter pages for migration.
