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

    await send_telegram_text(chat_id, "Вы уже зарегистрированы. Используйте /help для списка команд.")
    return {"ok": True, "action": "start_existing_user"}


async def _handle_help(chat_id: str, user_id: str) -> dict:
    help_text = (
        "Доступные команды:\n"
        "/start - начало работы и условия\n"
        "/help - список команд\n"
        "/profile - профиль и статус\n"
        "/watch add <query> - добавить правило\n"
        "/watch list - список правил\n"
        "/watch pause <id> - пауза правила\n"
        "/watch resume <id> - возобновить правило\n"
        "/watch delete <id> - удалить правило\n"
        "/alerts on|off - включить/выключить алерты\n"
        "/domains now <query> - разовый подбор кандидатов"
    )
    await send_telegram_text(chat_id, help_text)
    store.log_bot_event("command_help", telegram_user_id=user_id, telegram_chat_id=chat_id)
    return {"ok": True, "action": "help_sent"}


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
    profile_text = (
        f"Профиль:\n"
        f"user_id: {user.telegram_user_id}\n"
        f"username: @{user.username or '-'}\n"
        f"chat_id: {user.telegram_chat_id or '-'}\n"
        f"disclaimer: {'accepted' if user.disclaimer_accepted_at else 'not accepted'}\n"
        f"alerts: {'on' if alerts_enabled else 'off'}\n"
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


async def _handle_domains_now(chat_id: str, user_id: str, text: str) -> dict:
    parts = text.split(maxsplit=2)
    if len(parts) < 3 or parts[1].lower() != "now":
        await send_telegram_text(chat_id, "Формат: /domains now <query>")
        return {"ok": True, "action": "domains_now_bad_format"}

    query = _normalize_query(parts[2])
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

    priority = {"available": 0, "pending_delete": 1, "redemption": 2, "client_hold": 3, "registered": 9}
    rows.sort(key=lambda item: (priority.get(item["status"], 8), -float(item["score"])))

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


async def _handle_callback(callback_data: str, user_id: str, chat_id: str, callback_query_id: str | None) -> dict:
    if callback_query_id:
        await answer_telegram_callback(callback_query_id)

    if callback_data == "accept_disclaimer":
        store.mark_disclaimer_accepted(user_id, settings.telegram_disclaimer_version)
        store.log_bot_event("disclaimer_accepted", telegram_user_id=user_id, telegram_chat_id=chat_id)
        if chat_id:
            await send_telegram_text(chat_id, "Условия приняты. Теперь доступны команды: /help, /profile, /watch ...")
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
    store.upsert_telegram_user(user_id, chat_id, username, first_name, locale)
    store.log_bot_event("incoming_message", telegram_user_id=user_id, telegram_chat_id=chat_id, payload={"text": text})

    if text.startswith("/start"):
        return await _handle_start(chat_id, user_id, locale, username, first_name)
    if text.startswith("/help"):
        return await _handle_help(chat_id, user_id)

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

    await send_telegram_text(chat_id, "Не понял команду. Используйте /help")
    return {"ok": True, "action": "unknown_command"}
