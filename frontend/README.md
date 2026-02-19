# Domens Frontend (Vue 3)

Отдельный SPA-фронт для портала Domens.

## Stack
- Vue 3 + TypeScript
- Vite
- Pinia
- Vue Router

## Run locally
1. Install Node.js 22+
2. Install deps:
   - `npm install`
3. Start dev server:
   - `npm run dev`

Optional env:
- `VITE_API_BASE_URL=https://idns.devee.ru`

Если `VITE_API_BASE_URL` не задан, фронт использует относительные URL (`/v1/...`).

## Architecture
- Единый shell (`src/layouts/AppShell.vue`) для LK/Admin.
- Отличия по меню и доступам через RBAC (`src/stores/auth.ts`).
- Page-level guards в роутере (`src/router/index.ts`).

## Status
Это bootstrap-версия: каркас, роутинг, RBAC-база и стартовые страницы.
Перенос рабочей логики со старого `web/app.js` выполняется поэтапно.
