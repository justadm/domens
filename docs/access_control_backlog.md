# Access control backlog (admin/roles)

## Current state (MVP)
- Admins can be assigned in DB roles: `roles` + `user_roles`.
- Env admins (`TELEGRAM_ADMIN_USER_IDS`) are still supported and synced to DB on startup.
- Monitoring sends admin copy of alerts to configured admin Telegram users.
- Cabinet/API expose admin-only operations for role management.
- Telegram bot supports admin commands: `/admin roles|users|access-events|grant|revoke`.
- Audit trail for role operations is persisted in `access_events`.
- Role hierarchy guard is active:
  - only `superadmin` can grant/revoke `admin` and `superadmin`;
  - `admin` can manage only `viewer|operator`.

## Remaining gaps
- In-code permission matrix is implemented (`ROLE_PERMISSIONS` + `has_permission`), and key checks already use permission keys:
  - `admin.panel.read`
  - `admin.roles.manage.basic`
  - `admin.roles.manage.elevated`
  - `copilot.register_domain`
- DB-backed `permissions/role_permissions` tables are still not implemented (next phase).

## Planned DB extensions
1. Add table `permissions`.
2. Add table `role_permissions`.
3. Move from in-code map to DB-backed mapping with cache.

## Planned API/commands
- `/admin users` - list admins/operators.
- `/admin grant <telegram_user_id> <role>` - grant role.
- `/admin revoke <telegram_user_id> <role>` - revoke role.
- `/admin roles` - show available roles.
- `/admin access-events [action] [limit]` - latest access audit events.

## Migration plan
1. Alembic migration with `roles` + `user_roles`.
2. On first deploy, seed base roles.
3. Backfill: map users from `TELEGRAM_ADMIN_USER_IDS` into `user_roles` as `admin`.
4. Keep env fallback for one release, then remove.
