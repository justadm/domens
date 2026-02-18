# Notes For Discussion

Updated: 2026-02-18

## Questions
- Local shell profile: `/Users/just/.bash_profile` is owned by `root`, so PATH auto-fix for Homebrew Python needs either ownership change or sudo edit.
- For admin history UI: should we show all `access_events` to admins by default, or only events where they are actor/target unless `superadmin`?

## Proposals
- Copilot: добавить Telegram-режим для тех же intent/action confirm-циклов (сейчас веб-first API).
- Copilot: ввести role-based guard для интентов (`register_domain` только operator+).
- Copilot: добавить rate-limit на free-form сообщения и подтверждения (anti-spam/anti-bruteforce).
- Language: add full i18n coverage for all Telegram/MAX fixed texts (currently copilot is localized, legacy command texts are mostly RU).
- Add `/admin access-events` command in Telegram for quick audit access from bot.
- Add permission matrix tables (`permissions`, `role_permissions`) after role hierarchy guard, then switch checks from role-name matching to permission keys.
- Add dedicated Cabinet tab “Access Audit” with server-side pagination/filters by actor/target/action/date.

## Done recently
- Added Telegram admin command `/admin access-events [action] [limit]`.
- Added role hierarchy guard in API/Telegram:
  - only `superadmin` can grant/revoke `admin|superadmin`;
  - `admin` can manage only `viewer|operator`.
- Cabinet admin "Access Audit" now supports server-side filters and pagination:
  - filters: `action`, `actor_telegram_user_id`, `target_telegram_user_id`, `created_from`, `created_to`;
  - pagination: `limit`, `offset`, `next_offset`, `prev_offset`.
- Added hybrid LLM MVP architecture (documented):
  - intent parsing -> `0.5b`,
  - chat/qa replies -> `7b`,
  - dedicated plan: `docs/hybrid_llm_mvp_plan.md`.
