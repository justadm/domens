# Access control backlog (admin/roles)

## Current state (MVP)
- Admins can be assigned in DB roles: `roles` + `user_roles`.
- Env admins (`TELEGRAM_ADMIN_USER_IDS`) are still supported and synced to DB on startup.
- Monitoring sends admin copy of alerts to configured admin Telegram users.
- Cabinet/API expose admin-only operations for role management.
- Telegram bot supports admin commands: `/admin roles|users|grant|revoke`.
- Audit trail for role operations is persisted in `access_events`.

## Remaining gaps
- Fine-grained permissions matrix is not implemented yet (`permissions`, `role_permissions`).

## Planned DB extensions
1. Add table `permissions`.
2. Add table `role_permissions`.

## Planned API/commands
- `/admin users` - list admins/operators.
- `/admin grant <telegram_user_id> <role>` - grant role.
- `/admin revoke <telegram_user_id> <role>` - revoke role.
- `/admin roles` - show available roles.

## Migration plan
1. Alembic migration with `roles` + `user_roles`.
2. On first deploy, seed base roles.
3. Backfill: map users from `TELEGRAM_ADMIN_USER_IDS` into `user_roles` as `admin`.
4. Keep env fallback for one release, then remove.
