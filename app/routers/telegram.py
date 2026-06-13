from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import ConfirmRegistrationRequest
from app.services.domain_checker import infer_status
from app.services.domain_scoring import score_domain
from app.services.notifications import (
    answer_telegram_callback,
    send_telegram_message,
    send_telegram_text,
)
from app.services.timeweb_api import TimewebApiClient
from app.state import store
from app.routers.copilot import process_copilot_confirm, process_copilot_message

router = APIRouter(prefix="/v1/telegram", tags=["telegram"])

timeweb_client = TimewebApiClient(
    base_url=settings.timeweb_api_base_url,
    api_token=settings.timeweb_api_token,
)

START_DISCLAIMER_TEXT = (
    "Перед началом:\n"
    "- сервис не гарантирует итоговую доступность домена;\n"
    "- решение о регистрации принимаете вы;\n"
    "- возможны задержки/ошибки внешних API.\n\n"
    "Нажмите кнопку ниже, чтобы принять условия и продолжить."
)


def _parse_csv(raw: str) -> list[str]:
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _admin_user_ids() -> set[str]:
    return {item for item in _parse_csv(settings.telegram_admin_user_ids)}


def _is_admin_user(user_id: str) -> bool:
    safe_uid = str(user_id).strip()
    if not safe_uid:
        return False
    if safe_uid in _admin_user_ids():
        return True
    return store.has_permission(safe_uid, "admin.panel.read")


def _can_manage_role(user_id: str, role: str) -> bool:
    safe_role = str(role).strip().lower()
    safe_uid = str(user_id).strip()
    if safe_role in {"admin", "superadmin"}:
        return store.has_permission(safe_uid, "admin.roles.manage.elevated")
    return store.has_permission(safe_uid, "admin.roles.manage.basic")


def _short_rule(rule_id: str) -> str:
    return rule_id.split("-", 1)[0]


def _watch_rules_text(rules: list[dict]) -> str:
    lines: list[str] = ["Ваши watch-правила:"]
    for item in rules[:20]:
        lines.append(f"- [{item['status']}] {item['query']} (id: {_short_rule(item['id'])})")
    return "\n".join(lines)


def _watch_rules_keyboard(rules: list[dict]) -> dict | None:
    keyboard: list[list[dict]] = []
    for item in rules[:10]:
        rid = str(item["id"])
        status = str(item.get("status") or "active")
        action = "pause" if status == "active" else "resume"
        action_label = "Пауза" if action == "pause" else "Резюме"
        keyboard.append(
            [
                {"text": action_label, "callback_data": f"watch:{action}:{rid}"},
                {"text": "Удалить", "callback_data": f"watch:delete:{rid}"},
            ]
        )
    if not keyboard:
        return None
    return {"inline_keyboard": keyboard}


def _reply_keyboard(rows: list[list[str]]) -> dict:
    return {
        "keyboard": [[{"text": text} for text in row] for row in rows],
        "resize_keyboard": True,
    }


def _main_menu_keyboard() -> dict:
    return _reply_keyboard(
        [
            ["Профиль", "Лимиты"],
            ["Watch", "Алерты"],
            ["Найти домены"],
            ["Помощь"],
        ]
    )


def _watch_menu_keyboard() -> dict:
    return _reply_keyboard(
        [
            ["Список watch"],
            ["Добавить правило", "Стартовый набор"],
            ["Фокус core", "Фокус wide"],
            ["Назад"],
        ]
    )


def _alerts_menu_keyboard() -> dict:
    return _reply_keyboard(
        [
            ["Алерты ON", "Алерты OFF"],
            ["Лимиты"],
            ["Назад"],
        ]
    )


def _menu_text_alias(text: str) -> str:
    value = text.strip()
    key = value.lower()
    aliases = {
        "профиль": "/profile",
        "лимиты": "/limits",
        "помощь": "/help",
        "назад": "/menu",
        "список watch": "/watch list",
        "стартовый набор": "/watch seed",
        "фокус core": "/watch focus core",
        "фокус wide": "/watch focus wide",
        "алерты on": "/alerts on",
        "алерты off": "/alerts off",
    }
    specials = {
        "watch": "__watch_menu",
        "алерты": "__alerts_menu",
        "добавить правило": "__watch_add_prompt",
        "найти домены": "__domains_prompt",
    }
    return aliases.get(key) or specials.get(key) or value


def _seed_watch_queries() -> list[str]:
    return [
        "ai tools",
        "agent platform",
        "agent cloud",
        "mcp cloud",
        "prompt stack",
        "llm infra",
        "inference api",
        "voice ai",
        "video ai",
        "dev tools",
        "no code ai",
        "auto call",
        "lead flow",
        "crm ai",
        "fintech ai",
        "payment api",
        "security ai",
        "dns monitor",
        "domain radar",
        "domain catcher",
        "drop catch",
        "name scout",
        "brand lab",
        "growth stack",
        "workflow ai",
        "sales bot",
        "support bot",
        "code assist",
        "data agent",
        "cloud ops",
    ]


def _focus_core_queries() -> set[str]:
    return {
        "domain radar",
        "domain catcher",
        "drop catch",
        "name scout",
        "dns monitor",
        "agent platform",
        "agent cloud",
        "mcp cloud",
        "llm infra",
        "inference api",
        "dev tools",
        "cloud ops",
    }


def _extract_message(payload: dict) -> tuple[str, str, str, str, str | None, str | None] | None:
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict):
        return None

    text = str(message.get("text") or "").strip()
    chat_id = str((message.get("chat") or {}).get("id") or "")
    from_user = message.get("from") or {}
    user_id = str(from_user.get("id") or "")
    username = str(from_user.get("username") or "") or None
    first_name = str(from_user.get("first_name") or "") or None
    locale = str(from_user.get("language_code") or "") or None

    if not chat_id or not user_id:
        return None

    return text, chat_id, user_id, locale or "", username, first_name


def _extract_callback(payload: dict) -> tuple[str, str, str, str | None] | None:
    callback_query = payload.get("callback_query") if isinstance(payload, dict) else None
    if not isinstance(callback_query, dict):
        return None

    callback_data = str(callback_query.get("data") or "")
    from_user_id = str((callback_query.get("from") or {}).get("id") or "")
    chat_id = str(((callback_query.get("message") or {}).get("chat") or {}).get("id") or "")
    callback_query_id = str(callback_query.get("id") or "") or None

    if not callback_data or not from_user_id:
        return None

    return callback_data, from_user_id, chat_id, callback_query_id


async def _handle_start(chat_id: str, user_id: str, locale: str, username: str | None, first_name: str | None) -> dict:
    user = store.upsert_telegram_user(
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        username=username,
        first_name=first_name,
        locale=locale,
    )
    store.log_bot_event("command_start", telegram_user_id=user_id, telegram_chat_id=chat_id)

    if not user.disclaimer_accepted_at:
        await send_telegram_message(
            chat_id,
            START_DISCLAIMER_TEXT,
            reply_markup={
                "inline_keyboard": [
                    [
                        {
                            "text": "Принять и продолжить",
                            "callback_data": "accept_disclaimer",
                        }
                    ]
                ]
            },
        )
        return {"ok": True, "action": "start_disclaimer_sent"}

    await send_telegram_message(
        chat_id,
        "Вы уже зарегистрированы. Используйте /help для списка команд.",
        reply_markup=_main_menu_keyboard(),
    )
    return {"ok": True, "action": "start_existing_user"}


async def _handle_help(chat_id: str, user_id: str) -> dict:
    help_text = (
        "Быстрые действия:\n"
        "- Профиль: статус, роль, алерты\n"
        "- Watch: правила мониторинга\n"
        "- Алерты: включить или выключить уведомления\n"
        "- Найти домены: разовый подбор кандидатов\n\n"
        "Полный список команд: /commands\n"
        "Главное меню: /menu"
    )
    await send_telegram_message(chat_id, help_text, reply_markup=_main_menu_keyboard())
    store.log_bot_event("command_help", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "help_sent"}


async def _handle_commands(chat_id: str, user_id: str) -> dict:
    commands_text = (
        "Все команды:\n"
        "/start - начало работы и условия\n"
        "/help - краткая помощь\n"
        "/commands - полный список команд\n"
        "/limits - лимиты алертов за 24ч\n"
        "/profile - профиль и статус\n"
        "/watch add <query> - добавить правило\n"
        "/watch seed - добавить стартовый набор (30)\n"
        "/watch focus core|wide|status - профиль watch-правил\n"
        "/watch list - список правил\n"
        "/watch pause <id> - пауза правила\n"
        "/watch resume <id> - возобновить правило\n"
        "/watch delete <id> - удалить правило\n"
        "/alerts on|off - включить/выключить алерты\n"
        "/domains now <query> - разовый подбор кандидатов\n"
        "/menu - показать меню кнопок\n"
        "/ask <text> - вопрос в Copilot\n"
        "/chat <text> - свободный диалог\n"
        "/confirm <cp_token> - подтвердить действие Copilot\n"
        "/cancel <cp_token> - отменить действие Copilot"
    )
    if _is_admin_user(user_id):
        commands_text += (
            "\n\nАдмин-команды:\n"
            "/admin help - помощь по админ-командам\n"
            "/admin roles - список ролей\n"
            "/admin users [search] - пользователи и роли\n"
            "/admin access-events [action] [limit] - аудит доступа\n"
            "/admin grant <telegram_user_id> <role>\n"
            "/admin revoke <telegram_user_id> <role>"
        )
    await send_telegram_message(chat_id, commands_text, reply_markup=_main_menu_keyboard())
    store.log_bot_event("command_commands", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "commands_sent"}


async def _handle_watch_menu(chat_id: str, user_id: str) -> dict:
    await send_telegram_message(chat_id, "Watch-правила:", reply_markup=_watch_menu_keyboard())
    store.log_bot_event("command_watch_menu", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "watch_menu_sent"}


async def _handle_alerts_menu(chat_id: str, user_id: str) -> dict:
    await send_telegram_message(chat_id, "Алерты:", reply_markup=_alerts_menu_keyboard())
    store.log_bot_event("command_alerts_menu", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "alerts_menu_sent"}


async def _handle_watch_add_prompt(chat_id: str, user_id: str) -> dict:
    await send_telegram_message(
        chat_id,
        "Напишите команду:\n/watch add <тема>\n\nПример:\n/watch add ai crm",
        reply_markup=_watch_menu_keyboard(),
    )
    store.log_bot_event("command_watch_add_prompt", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "watch_add_prompt_sent"}


async def _handle_domains_prompt(chat_id: str, user_id: str) -> dict:
    await send_telegram_message(
        chat_id,
        "Напишите команду:\n/domains now <тема>\n\nПример:\n/domains now ai tools",
        reply_markup=_main_menu_keyboard(),
    )
    store.log_bot_event("command_domains_prompt", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "domains_prompt_sent"}


async def _handle_limits(chat_id: str, user_id: str) -> dict:
    usage_24h = store.get_user_alert_usage_24h(
        user_id,
        per_target_daily_limit=settings.monitor_alert_per_target_daily_limit,
    )
    lines = [
        "Лимиты за 24ч:",
        f"- отправлено: {int(usage_24h.get('daily_sent') or 0)}",
        f"- осталось: {int(usage_24h.get('daily_remaining_total') or 0)}",
    ]
    channels = usage_24h.get("channels") or []
    if channels:
        lines.append("Каналы:")
        for item in channels:
            lines.append(
                f"- {item.get('channel_type')}:{item.get('channel_target')} -> "
                f"{item.get('daily_sent')}/{item.get('daily_limit')}"
            )

    await send_telegram_text(chat_id, "\n".join(lines))
    store.log_bot_event("command_limits", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "limits_sent"}


def _is_ready(user_id: str) -> tuple[bool, str | None]:
    user = store.get_telegram_user(user_id)
    if not user:
        return False, "Профиль не найден. Введите /start"
    if not user.disclaimer_accepted_at:
        return False, "Сначала примите условия через /start"
    return True, None


async def _handle_profile(chat_id: str, user_id: str) -> dict:
    user = store.get_telegram_user(user_id)
    if not user:
        await send_telegram_text(chat_id, "Профиль не найден. Введите /start")
        return {"ok": True, "action": "profile_missing"}

    rules_count = store.get_watch_rules_count(user_id)
    alerts_enabled = store.get_telegram_alerts_enabled(user_id)
    usage_24h = store.get_user_alert_usage_24h(
        user_id,
        per_target_daily_limit=settings.monitor_alert_per_target_daily_limit,
    )
    daily_sent = int(usage_24h.get("daily_sent") or 0)
    daily_remaining = int(usage_24h.get("daily_remaining_total") or 0)
    profile_text = (
        f"Профиль:\n"
        f"user_id: {user.telegram_user_id}\n"
        f"role: {'admin' if _is_admin_user(user_id) else 'user'}\n"
        f"username: @{user.username or '-'}\n"
        f"chat_id: {user.telegram_chat_id or '-'}\n"
        f"disclaimer: {'accepted' if user.disclaimer_accepted_at else 'not accepted'}\n"
        f"alerts: {'on' if alerts_enabled else 'off'}\n"
        f"alerts_24h_sent: {daily_sent}\n"
        f"alerts_24h_remaining: {daily_remaining}\n"
        f"active watch rules: {rules_count}"
    )
    await send_telegram_text(chat_id, profile_text)
    store.log_bot_event("command_profile", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "profile_sent"}


async def _handle_watch(chat_id: str, user_id: str, text: str) -> dict:
    parts = text.split()
    if len(parts) < 2:
        await send_telegram_text(chat_id, "Формат: /watch add|list|pause|resume|delete ...")
        return {"ok": True, "action": "watch_bad_format"}

    action = parts[1].lower()

    if action == "seed":
        existing = {str(item.get("query") or "").strip().lower() for item in store.list_watch_rules(user_id)}
        added = 0
        for query in _seed_watch_queries():
            key = query.strip().lower()
            if not key or key in existing:
                continue
            rule_id = store.add_watch_rule(user_id, watch_query=query)
            if rule_id:
                added += 1
                existing.add(key)

        await send_telegram_text(
            chat_id,
            f"Seed готов: добавлено {added} правил. Посмотреть: /watch list",
        )
        store.log_bot_event(
            "watch_seed",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"added": added},
        )
        return {"ok": True, "action": "watch_seed_done", "added": added}

    if action == "focus":
        mode = parts[2].strip().lower() if len(parts) >= 3 else ""
        if mode not in {"core", "wide", "status"}:
            await send_telegram_text(chat_id, "Формат: /watch focus core|wide|status")
            return {"ok": True, "action": "watch_focus_bad_format"}

        rules = store.list_watch_rules(user_id)
        seed_set = {item.strip().lower() for item in _seed_watch_queries()}
        core_set = _focus_core_queries()

        if mode == "status":
            seed_rules = [item for item in rules if str(item.get("query") or "").strip().lower() in seed_set]
            seed_active = sum(1 for item in seed_rules if str(item.get("status")) == "active")
            custom_active = sum(
                1
                for item in rules
                if str(item.get("status")) == "active"
                and str(item.get("query") or "").strip().lower() not in seed_set
            )
            await send_telegram_text(
                chat_id,
                (
                    f"Watch focus status:\n"
                    f"- seed active: {seed_active}/{len(seed_rules)}\n"
                    f"- custom active: {custom_active}\n"
                    f"- core profile size: {len(core_set)}"
                ),
            )
            return {"ok": True, "action": "watch_focus_status"}

        changed = 0
        for item in rules:
            query = str(item.get("query") or "").strip().lower()
            if query not in seed_set:
                continue
            target_status = "active" if (mode == "wide" or query in core_set) else "paused"
            if str(item.get("status")) == target_status:
                continue
            if store.set_watch_rule_status(user_id, str(item.get("id")), target_status):
                changed += 1

        await send_telegram_text(
            chat_id,
            f"Watch focus: {mode}. Обновлено правил: {changed}. Проверка: /watch focus status",
        )
        store.log_bot_event(
            "watch_focus",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"mode": mode, "changed": changed},
        )
        return {"ok": True, "action": "watch_focus_done", "mode": mode, "changed": changed}

    if action == "add":
        query = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
        if not query:
            await send_telegram_text(chat_id, "Формат: /watch add <query>")
            return {"ok": True, "action": "watch_add_bad_format"}

        rule_id = store.add_watch_rule(user_id, watch_query=query)
        if not rule_id:
            await send_telegram_text(chat_id, "Сначала выполните /start")
            return {"ok": True, "action": "watch_add_no_user"}

        await send_telegram_text(
            chat_id,
            f"Правило добавлено: {_short_rule(rule_id)} ({query})\n"
            f"Управление: /watch list или /watch pause {rule_id}",
        )
        store.log_bot_event("watch_add", telegram_user_id=user_id, telegram_chat_id=chat_id, payload={"rule_id": rule_id})
        return {"ok": True, "action": "watch_added", "rule_id": rule_id}

    if action == "list":
        rules = store.list_watch_rules(user_id)
        if not rules:
            await send_telegram_text(chat_id, "Правил нет. Добавьте: /watch add <query>")
            return {"ok": True, "action": "watch_list_empty"}

        await send_telegram_message(
            chat_id,
            _watch_rules_text(rules),
            reply_markup=_watch_rules_keyboard(rules),
        )
        return {"ok": True, "action": "watch_list_sent", "count": len(rules)}

    if action in {"pause", "resume", "delete"}:
        if len(parts) < 3:
            await send_telegram_text(chat_id, f"Формат: /watch {action} <id>")
            return {"ok": True, "action": f"watch_{action}_bad_format"}
        rule_id = parts[2]
        target_status = "paused" if action == "pause" else "active"
        if action == "delete":
            target_status = "deleted"

        ok = store.set_watch_rule_status(user_id, rule_id, target_status)
        if not ok:
            await send_telegram_text(chat_id, "Правило не найдено")
            return {"ok": True, "action": f"watch_{action}_not_found"}

        await send_telegram_text(chat_id, f"Готово: {action} {rule_id}")
        store.log_bot_event(
            f"watch_{action}",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"rule_id": rule_id},
        )
        return {"ok": True, "action": f"watch_{action}_done"}

    await send_telegram_text(chat_id, "Неизвестная команда /watch")
    return {"ok": True, "action": "watch_unknown"}


async def _handle_alerts(chat_id: str, user_id: str, text: str) -> dict:
    parts = text.split()
    if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
        await send_telegram_text(chat_id, "Формат: /alerts on|off")
        return {"ok": True, "action": "alerts_bad_format"}

    enabled = parts[1].lower() == "on"
    ok = store.set_telegram_alerts_enabled(user_id, chat_id, enabled)
    if not ok:
        await send_telegram_text(chat_id, "Сначала выполните /start")
        return {"ok": True, "action": "alerts_no_user"}

    status_text = "включены" if enabled else "выключены"
    await send_telegram_text(chat_id, f"Алерты {status_text}.")
    store.log_bot_event(
        "alerts_toggle",
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        payload={"enabled": enabled},
    )
    return {"ok": True, "action": "alerts_toggled", "enabled": enabled}


def _normalize_query(raw: str) -> str:
    value = raw.strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "", value)
    return value[:24]


def _query_terms(raw: str) -> list[str]:
    return [item for item in re.split(r"[^a-z0-9]+", raw.lower()) if len(item) >= 2][:4]


def _domains_now_rank(item: dict, query_terms: list[str]) -> tuple:
    status_weight = {"available": 100, "pending_delete": 90, "redemption": 75, "client_hold": 70, "registered": 20}
    domain = str(item.get("domain") or "").lower()
    name = domain.split(".", 1)[0]
    base = float(item.get("score") or 0)
    status_bonus = status_weight.get(str(item.get("status") or "registered"), 10)
    term_bonus = 0
    if query_terms:
        hits = sum(1 for term in query_terms if term in name)
        term_bonus = hits * 8
        if name.startswith(query_terms[0]):
            term_bonus += 5
    length_penalty = max(0, len(name) - 11) * 1.5
    final_score = base + status_bonus + term_bonus - length_penalty
    return (-final_score, name)


async def _handle_domains_now(chat_id: str, user_id: str, text: str) -> dict:
    parts = text.split(maxsplit=2)
    if len(parts) < 3 or parts[1].lower() != "now":
        await send_telegram_text(chat_id, "Формат: /domains now <query>")
        return {"ok": True, "action": "domains_now_bad_format"}

    raw_query = parts[2]
    query_terms = _query_terms(raw_query)
    query = _normalize_query(raw_query)
    if len(query) < 2:
        await send_telegram_text(chat_id, "Слишком короткий запрос. Пример: /domains now fintech")
        return {"ok": True, "action": "domains_now_short_query"}

    tlds = _parse_csv(settings.monitor_tlds)[:6] or [".com", ".io", ".ai", ".ru"]
    seeds = {
        query,
        f"{query}lab",
        f"{query}hub",
        f"my{query}",
        f"go{query}",
        f"{query}ai",
    }
    candidates = [f"{seed}{tld}" for seed in sorted(seeds) for tld in tlds][:18]

    sem = asyncio.Semaphore(8)

    async def check_one(fqdn: str) -> dict:
        async with sem:
            status, eta = await infer_status(fqdn, timeweb_client=timeweb_client)
            return {
                "domain": fqdn,
                "status": status,
                "score": score_domain(fqdn),
                "eta": eta.isoformat() if eta else None,
            }

    rows = await asyncio.gather(*(check_one(name) for name in candidates))

    rows.sort(key=lambda item: _domains_now_rank(item, query_terms))

    top = rows[:8]
    lines = [
        f"{item['domain']} | {item['status']} | score {item['score']}"
        + (f" | eta {item['eta']}" if item["eta"] else "")
        for item in top
    ]

    await send_telegram_text(chat_id, "Подбор по запросу:\n" + "\n".join(lines))
    store.log_bot_event(
        "domains_now",
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        payload={"query": query, "count": len(top)},
    )
    return {"ok": True, "action": "domains_now_done", "count": len(top)}


async def _handle_admin(chat_id: str, user_id: str, text: str) -> dict:
    if not _is_admin_user(user_id):
        await send_telegram_text(chat_id, "Недостаточно прав. Команда доступна только admin/superadmin.")
        return {"ok": True, "action": "admin_forbidden"}

    parts = text.split(maxsplit=3)
    if len(parts) < 2:
        await send_telegram_text(chat_id, "Формат: /admin roles|users|access-events|grant|revoke ...")
        return {"ok": True, "action": "admin_bad_format"}

    action = parts[1].strip().lower()

    if action == "help":
        await send_telegram_text(
            chat_id,
            (
                "Админ-команды:\n"
                "/admin roles - список ролей\n"
                "/admin users [search] - пользователи и роли\n"
                "/admin access-events [action] [limit] - аудит доступа\n"
                "/admin grant <telegram_user_id> <role>\n"
                "/admin revoke <telegram_user_id> <role>"
            ),
        )
        store.log_bot_event("admin_help", telegram_user_id=user_id, telegram_chat_id=chat_id)
        return {"ok": True, "action": "admin_help"}

    if action == "roles":
        roles = store.list_roles()
        lines = ["Роли:"]
        for item in roles:
            lines.append(f"- {item.get('code')} ({item.get('title')})")
        await send_telegram_text(chat_id, "\n".join(lines))
        store.log_bot_event("admin_roles", telegram_user_id=user_id, telegram_chat_id=chat_id)
        return {"ok": True, "action": "admin_roles", "count": len(roles)}

    if action == "users":
        search = parts[2].strip() if len(parts) >= 3 else None
        rows = store.list_users_with_roles(search=search, limit=20)
        if not rows:
            await send_telegram_text(chat_id, "Пользователи не найдены.")
            return {"ok": True, "action": "admin_users_empty"}

        lines = ["Пользователи (до 20):"]
        for row in rows:
            uid = str(row.get("telegram_user_id") or "-")
            username = str(row.get("username") or "-")
            roles = row.get("roles") or []
            roles_text = ",".join(roles) if roles else "no-role"
            lines.append(f"- {uid} | @{username} | {roles_text}")
        await send_telegram_text(chat_id, "\n".join(lines))
        store.log_bot_event(
            "admin_users",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"search": search or ""},
        )
        return {"ok": True, "action": "admin_users", "count": len(rows)}

    if action == "access-events":
        action_filter = parts[2].strip().lower() if len(parts) >= 3 else None
        limit_raw = parts[3].strip() if len(parts) >= 4 else "10"
        try:
            limit = max(1, min(int(limit_raw), 30))
        except ValueError:
            await send_telegram_text(chat_id, "Лимит должен быть числом. Пример: /admin access-events grant_role 10")
            return {"ok": True, "action": "admin_access_events_bad_limit"}

        rows = store.list_access_events(limit=limit, action=action_filter or None)
        if not rows:
            await send_telegram_text(chat_id, "События не найдены.")
            return {"ok": True, "action": "admin_access_events_empty"}

        lines = [f"Аудит доступа (до {len(rows)}):"]
        for row in rows:
            created_at = str(row.get("created_at") or "")[:19].replace("T", " ")
            actor = str(row.get("actor_telegram_user_id") or "-")
            target = str(row.get("target_telegram_user_id") or "-")
            role = str(row.get("role_code") or "-")
            event_action = str(row.get("action") or "-")
            lines.append(f"- {created_at} | {event_action} | {actor}->{target} | role={role}")
        await send_telegram_text(chat_id, "\n".join(lines))
        store.log_bot_event(
            "admin_access_events",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"action": action_filter or "", "limit": limit},
        )
        return {"ok": True, "action": "admin_access_events", "count": len(rows)}

    if action in {"grant", "revoke"}:
        if len(parts) < 4:
            await send_telegram_text(chat_id, f"Формат: /admin {action} <telegram_user_id> <role>")
            return {"ok": True, "action": f"admin_{action}_bad_format"}

        target_uid = parts[2].strip()
        role = parts[3].strip().lower()
        allowed = {"viewer", "viewer_admin", "operator", "manager_admin", "admin", "superadmin"}
        if not target_uid or role not in allowed:
            await send_telegram_text(
                chat_id,
                "Роль должна быть одной из: viewer, viewer_admin, operator, manager_admin, admin, superadmin.",
            )
            return {"ok": True, "action": f"admin_{action}_invalid_role"}
        if not _can_manage_role(user_id, role):
            await send_telegram_text(chat_id, "Только superadmin может выдавать/снимать роли admin/superadmin.")
            return {"ok": True, "action": f"admin_{action}_forbidden_role_manage"}

        if action == "grant":
            ok = store.grant_role(target_uid, role, granted_by=f"tg_admin:{user_id}")
            if not ok:
                await send_telegram_text(chat_id, "Не удалось выдать роль.")
                return {"ok": True, "action": "admin_grant_failed"}
            store.log_bot_event(
                "admin_grant_role",
                telegram_user_id=user_id,
                telegram_chat_id=chat_id,
                payload={"target": target_uid, "role": role},
            )
            store.log_access_event(
                action="grant_role",
                actor_telegram_user_id=user_id,
                target_telegram_user_id=target_uid,
                role_code=role,
                payload={"source": "telegram"},
            )
            await send_telegram_text(chat_id, f"Готово: выдана роль {role} пользователю {target_uid}.")
            return {"ok": True, "action": "admin_grant_done"}

        ok = store.revoke_role(target_uid, role)
        if not ok:
            await send_telegram_text(chat_id, "Связка user+role не найдена.")
            return {"ok": True, "action": "admin_revoke_not_found"}
        store.log_bot_event(
            "admin_revoke_role",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"target": target_uid, "role": role},
        )
        store.log_access_event(
            action="revoke_role",
            actor_telegram_user_id=user_id,
            target_telegram_user_id=target_uid,
            role_code=role,
            payload={"source": "telegram"},
        )
        await send_telegram_text(chat_id, f"Готово: роль {role} отозвана у пользователя {target_uid}.")
        return {"ok": True, "action": "admin_revoke_done"}

    await send_telegram_text(chat_id, "Неизвестная команда /admin")
    return {"ok": True, "action": "admin_unknown"}


async def _handle_copilot_telegram(chat_id: str, user_id: str, text: str) -> dict:
    if text.startswith("/ask"):
        payload = text[4:].strip()
        if not payload:
            await send_telegram_text(chat_id, "Формат: /ask <text>")
            return {"ok": True, "action": "copilot_ask_bad_format"}
        data = await process_copilot_message(
            user_id=user_id,
            message=payload,
            mode="assistant",
            channel="telegram",
        )
        msg = data.reply
        if data.requires_confirmation and data.confirmation_token:
            msg += f"\n\nПодтверждение: /confirm {data.confirmation_token}\nОтмена: /cancel {data.confirmation_token}"
        await send_telegram_text(chat_id, msg)
        return {"ok": True, "action": "copilot_ask_done"}

    if text.startswith("/chat"):
        payload = text[5:].strip()
        if not payload:
            await send_telegram_text(chat_id, "Формат: /chat <text>")
            return {"ok": True, "action": "copilot_chat_bad_format"}
        data = await process_copilot_message(
            user_id=user_id,
            message=payload,
            mode="chat",
            channel="telegram",
        )
        await send_telegram_text(chat_id, data.reply)
        return {"ok": True, "action": "copilot_chat_done"}

    if text.startswith("/confirm"):
        token = text.replace("/confirm", "", 1).strip()
        if not token:
            await send_telegram_text(chat_id, "Формат: /confirm <cp_token>")
            return {"ok": True, "action": "copilot_confirm_bad_format"}
        result = await process_copilot_confirm(user_id=user_id, confirmation_token=token, decision="confirm")
        await send_telegram_text(chat_id, f"{result.status}: {result.message}")
        return {"ok": True, "action": "copilot_confirm_done"}

    if text.startswith("/cancel"):
        token = text.replace("/cancel", "", 1).strip()
        if not token:
            await send_telegram_text(chat_id, "Формат: /cancel <cp_token>")
            return {"ok": True, "action": "copilot_cancel_bad_format"}
        result = await process_copilot_confirm(user_id=user_id, confirmation_token=token, decision="cancel")
        await send_telegram_text(chat_id, f"{result.status}: {result.message}")
        return {"ok": True, "action": "copilot_cancel_done"}

    return {"ok": True, "action": "copilot_unknown"}


async def _handle_callback(callback_data: str, user_id: str, chat_id: str, callback_query_id: str | None) -> dict:
    if callback_data.startswith("feedback:"):
        parts = callback_data.split(":", 2)
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="invalid feedback callback_data")
        _, feedback_type, token = parts
        if feedback_type not in {"more", "less", "never"}:
            raise HTTPException(status_code=400, detail="invalid feedback type")

        ok = store.record_alert_feedback(token, user_id, feedback_type)
        if feedback_type == "never":
            alert = store.get_alert_by_token(token)
            if alert:
                store.suppress_alert(alert.domain, alert.telegram_chat_id, reason="user_never", days=365)
        store.log_bot_event(
            "alert_feedback",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"token": token, "feedback_type": feedback_type, "ok": ok},
        )
        if callback_query_id:
            await answer_telegram_callback(callback_query_id, "Принято")
        return {"ok": ok, "action": "feedback", "feedback_type": feedback_type}

    if callback_query_id:
        await answer_telegram_callback(callback_query_id)

    if callback_data == "accept_disclaimer":
        store.mark_disclaimer_accepted(user_id, settings.telegram_disclaimer_version)
        store.log_bot_event("disclaimer_accepted", telegram_user_id=user_id, telegram_chat_id=chat_id)
        if chat_id:
            await send_telegram_message(
                chat_id,
                "Условия приняты. Теперь доступны команды: /help, /profile, /watch ...",
                reply_markup=_main_menu_keyboard(),
            )
        return {"ok": True, "action": "disclaimer_accepted"}

    if callback_data.startswith("watch:"):
        parts = callback_data.split(":", 2)
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="invalid watch callback_data")
        _, action, rule_id = parts
        if action not in {"pause", "resume", "delete"}:
            raise HTTPException(status_code=400, detail="invalid watch callback action")
        target_status = "paused" if action == "pause" else "active"
        if action == "delete":
            target_status = "deleted"
        ok = store.set_watch_rule_status(user_id, rule_id, target_status)
        if not ok:
            if chat_id:
                await send_telegram_text(chat_id, "Правило не найдено")
            return {"ok": True, "action": "watch_callback_not_found"}

        store.log_bot_event(
            f"watch_{action}_callback",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"rule_id": rule_id},
        )
        rules = store.list_watch_rules(user_id)
        if chat_id:
            await send_telegram_message(
                chat_id,
                f"Готово: {action} {_short_rule(rule_id)}",
                reply_markup=_watch_rules_keyboard(rules),
            )
        return {"ok": True, "action": f"watch_{action}_callback_done"}

    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="invalid callback_data")

    action, token = parts
    alert = store.get_alert_by_token(token)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    if action == "skip":
        store.mark_alert_acknowledged(token)
        store.log_bot_event("alert_skip", telegram_user_id=user_id, telegram_chat_id=chat_id, payload={"token": token})
        if chat_id:
            await send_telegram_text(chat_id, f"Пропущено: {alert.domain}")
        return {"ok": True, "action": "skip", "domain": alert.domain}

    if action == "register":
        from app.routers.registrations import confirm_registration, execute_registration

        result = await confirm_registration(
            ConfirmRegistrationRequest(
                confirmation_token=token,
                confirmed_by=f"tg:{user_id}",
            )
        )
        execute_result = await execute_registration(result.order_id)
        store.log_bot_event(
            "alert_register",
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            payload={"token": token, "order_id": result.order_id},
        )
        if chat_id:
            await send_telegram_text(chat_id, f"Заказ {result.order_id}: {execute_result.status} ({result.domain})")
        return {
            "ok": True,
            "action": "register",
            "order_id": result.order_id,
            "domain": result.domain,
            "status": execute_result.status,
            "registrar_response": execute_result.registrar_response,
        }

    raise HTTPException(status_code=400, detail="unknown callback action")


@router.post("/webhook")
async def telegram_webhook(payload: dict) -> dict:
    return await process_telegram_update(payload)


async def process_telegram_update(payload: dict) -> dict:
    callback = _extract_callback(payload)
    if callback:
        callback_data, from_user_id, chat_id, callback_query_id = callback
        store.upsert_telegram_user(from_user_id, chat_id, None, None, None)
        return await _handle_callback(callback_data, from_user_id, chat_id, callback_query_id)

    message = _extract_message(payload)
    if not message:
        return {"ok": True, "action": "ignored"}

    text, chat_id, user_id, locale, username, first_name = message
    text = _menu_text_alias(text)
    store.upsert_telegram_user(user_id, chat_id, username, first_name, locale)
    store.log_bot_event("incoming_message", telegram_user_id=user_id, telegram_chat_id=chat_id, payload={"text": text})

    if text == "__watch_menu":
        return await _handle_watch_menu(chat_id, user_id)
    if text == "__alerts_menu":
        return await _handle_alerts_menu(chat_id, user_id)
    if text == "__watch_add_prompt":
        return await _handle_watch_add_prompt(chat_id, user_id)
    if text == "__domains_prompt":
        return await _handle_domains_prompt(chat_id, user_id)

    if text.startswith("/start"):
        return await _handle_start(chat_id, user_id, locale, username, first_name)
    if text.startswith("/commands") or text.startswith("/help full"):
        return await _handle_commands(chat_id, user_id)
    if text.startswith("/help"):
        return await _handle_help(chat_id, user_id)
    if text.startswith("/menu"):
        await send_telegram_message(chat_id, "Главное меню:", reply_markup=_main_menu_keyboard())
        store.log_bot_event("command_menu", telegram_user_id=user_id, telegram_chat_id=chat_id)
        return {"ok": True, "action": "menu_sent"}
    if text.startswith("/limits"):
        return await _handle_limits(chat_id, user_id)

    ready, reason = _is_ready(user_id)
    if not ready:
        await send_telegram_text(chat_id, reason or "Сначала выполните /start")
        return {"ok": True, "action": "user_not_ready"}

    if text.startswith("/profile"):
        return await _handle_profile(chat_id, user_id)
    if text.startswith("/watch"):
        return await _handle_watch(chat_id, user_id, text)
    if text.startswith("/alerts"):
        return await _handle_alerts(chat_id, user_id, text)
    if text.startswith("/domains"):
        return await _handle_domains_now(chat_id, user_id, text)
    if text.startswith("/ask") or text.startswith("/chat") or text.startswith("/confirm") or text.startswith("/cancel"):
        return await _handle_copilot_telegram(chat_id, user_id, text)
    if text.startswith("/admin"):
        return await _handle_admin(chat_id, user_id, text)

    await send_telegram_text(chat_id, "Не понял команду. Используйте /help")
    return {"ok": True, "action": "unknown_command"}
