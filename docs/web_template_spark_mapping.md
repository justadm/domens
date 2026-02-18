# Spark Template Mapping Draft

Template source: `/Users/just/Sites/meko/html/spark`
Status: prepared mapping only, implementation pending.

## Why this template fits
- Ready sidebar/topbar/admin layout.
- Built-in tables, filters, form pages, auth pages.
- Light/dark styles available (`css/light.css`, `css/dark.css`).
- Compatible with current SPA approach (can extract layout/partials and bind to existing JS/API).

## Route mapping (draft)
- `/` (public landing):
  - base from `pages-blank.php` + sections from dashboard cards.
  - keep CTA: login/signup or go to LK.

- `/lk/`:
  - base from `dashboard-analytics.php`.

- `/lk/my/`:
  - base from `pages-settings.php` + form blocks from `forms-layouts.php`.

- `/lk/domens/`:
  - base from `tables-datatables-column-search.php`.

- `/lk/domens/<ID>/`:
  - base from `pages-blank.php` + details card components.

- `/lk/orders/`:
  - base from `tables-datatables-responsive.php`.

- `/lk/orders/<ID>/`:
  - base from `pages-invoice.php` card/table blocks.

- `/lk/finances/`:
  - base from `pages-invoice.php` + form controls.

- `/lk/finances/history`:
  - base from datatables pages.

- `/lk/documents`:
  - base from `pages-blank.php` + cards/list groups.

- `/admin/`:
  - base from `dashboard-e-commerce.php`.

- `/admin/users/`:
  - base from datatables pages.

- `/admin/users/<ID>/`:
  - base from `pages-settings.php` + custom detail cards.

- `/admin/finances`:
  - base from datatables pages.

## Technical notes
- Remove Google Analytics snippet from template pages.
- Keep only required assets (`css/`, `js/`, `fonts/`, `img/` subsets).
- Convert PHP pages into static HTML fragments for FastAPI static serving.
- Preserve current API contracts and bind controls through existing frontend JS modules.
- Keep current RBAC behavior (`/admin` доступ только с `admin.panel.read`).

## Next implementation phase
1. Extract common shell layout (sidebar + header + content container).
2. Build 3 entry pages first: `/`, `/lk`, `/admin`.
3. Rebind current widgets to new DOM IDs/classes.
4. Then expand to detail/list routes incrementally.

## Implementation Progress
- Done (phase 1):
  - `/` switched to public landing page (`web/landing.html`).
  - `/lk` and `/lk/` now serve the current LK SPA (`web/index.html`).
  - `/admin` kept as dedicated admin UI, link updated to open `/lk`.
- Done:
  - Template source is copied locally into `frontend_templates/spark` and excluded from git.
  - Google Analytics snippet removed from copied template pages.
- Pending (next):
  - Replace current LK/admin layout layer with Spark-derived shell while preserving existing JS IDs and API wiring.
