import uuid

import httpx

from app.config import settings


def build_confirmation_token() -> str:
    return f"cfm_{uuid.uuid4().hex}"


def build_alert_explanation_text(domain: str, explanation: dict | None = None) -> str:
    lines = [f"Почему прислал {domain}:"]
    if not explanation:
        lines.append("- найден мониторингом как домен-кандидат")
        return "\n".join(lines)

    if explanation.get("score") is not None:
        lines.append(f"- score: {explanation.get('score')}")
    if explanation.get("status"):
        lines.append(f"- статус: {explanation.get('status')}")
    if explanation.get("tld"):
        tld = str(explanation.get("tld") or "").lstrip(".")
        lines.append(f"- TLD: .{tld}")
    if explanation.get("matched_query"):
        lines.append(f"- watch: {explanation.get('matched_query')}")
    if explanation.get("risk"):
        lines.append(f"- риск: {explanation.get('risk')}")
    return "\n".join(lines)


def _build_alert_text(domain: str, explanation: dict | None = None) -> str:
    why_lines = build_alert_explanation_text(domain, explanation).splitlines()
    lines = [
        f"Домен-кандидат: {domain}",
        "",
        "Почему интересно:",
        *[line.replace("- ", "", 1) if line.startswith("- ") else line for line in why_lines[1:]],
        "",
    ]
    if settings.registration_enabled:
        lines.append("Регистрация доступна после явного подтверждения.")
    else:
        lines.append("Регистрация сейчас выключена. Можно оценить домен и настроить радар.")
    return "\n".join(lines)


def _alert_button_rows(token: str) -> list[list[dict]]:
    rows: list[list[dict]] = []
    if settings.registration_enabled:
        rows.append(
            [
                {"text": "🛒 Зарегистрировать", "callback_data": f"register:{token}"},
                {"text": "⏭ Пропустить", "callback_data": f"skip:{token}"},
            ]
        )
    else:
        rows.append([{"text": "⏭ Пропустить", "callback_data": f"skip:{token}"}])
    rows.extend(
        [
            [
                {"text": "👍 Больше таких", "callback_data": f"feedback:more:{token}"},
                {"text": "👎 Меньше таких", "callback_data": f"feedback:less:{token}"},
            ],
            [
                {"text": "❓ Почему", "callback_data": f"feedback:why:{token}"},
                {"text": "🚫 Не повторять", "callback_data": f"feedback:never:{token}"},
            ],
        ]
    )
    return rows


def _alert_button_callbacks(token: str) -> list[str]:
    callbacks = [button["callback_data"] for row in _alert_button_rows(token) for button in row]
    return [str(item) for item in callbacks]


def _digest_button_rows(items: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for item in items:
        domain = str(item.get("domain") or "domain")
        token = str(item.get("token") or "")
        if not token:
            continue
        rows.append(
            [
                {"text": f"❓ {domain[:22]}", "callback_data": f"feedback:why:{token}"},
                {"text": "👍", "callback_data": f"feedback:more:{token}"},
                {"text": "👎", "callback_data": f"feedback:less:{token}"},
                {"text": "🚫", "callback_data": f"feedback:never:{token}"},
            ]
        )
    return rows


def _build_digest_text(items: list[dict]) -> str:
    lines = ["Дайджест радара:"]
    for index, item in enumerate(items, start=1):
        explanation = item.get("explanation") if isinstance(item.get("explanation"), dict) else {}
        score = explanation.get("score") if explanation else item.get("score")
        status = explanation.get("status") if explanation else item.get("status")
        tld = str(explanation.get("tld") or "").lstrip(".") if explanation else ""
        watch = explanation.get("matched_query") if explanation else None
        details = [str(item.get("domain") or "-")]
        if score is not None:
            details.append(f"score {score}")
        if status:
            details.append(str(status))
        if tld:
            details.append(f".{tld}")
        lines.append(f"{index}. " + " | ".join(details))
        if watch:
            lines.append(f"   watch: {watch}")
    lines.append("")
    lines.append("Кнопки под сообщением: почему, больше таких, меньше таких, не повторять.")
    return "\n".join(lines)


async def send_telegram_alert(chat_id: str, domain: str, token: str, explanation: dict | None = None) -> dict:
    bot_token = settings.telegram_bot_token
    text = _build_alert_text(domain, explanation)
    buttons = _alert_button_callbacks(token)
    if not bot_token:
        return {
            "mode": "mock",
            "chat_id": chat_id,
            "domain": domain,
            "text": text,
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "buttons": buttons,
        }

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": _alert_button_rows(token)
        },
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "mode": "telegram_error",
                "chat_id": chat_id,
                "domain": domain,
                "error": str(exc),
                "buttons": buttons,
            }

    return {
        "mode": "telegram",
        "chat_id": chat_id,
        "domain": domain,
        "message_id": str(data.get("result", {}).get("message_id", "")),
        "buttons": buttons,
    }


async def send_telegram_digest(chat_id: str, items: list[dict]) -> dict:
    bot_token = settings.telegram_bot_token
    safe_items = sorted(
        items,
        key=lambda item: float((item.get("explanation") or {}).get("score") or item.get("score") or 0),
        reverse=True,
    )[:5]
    text = _build_digest_text(safe_items)
    buttons = [button["callback_data"] for row in _digest_button_rows(safe_items) for button in row]
    if not bot_token:
        return {
            "mode": "mock",
            "chat_id": chat_id,
            "text": text,
            "items_count": len(safe_items),
            "items": safe_items,
            "buttons": buttons,
        }

    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": _digest_button_rows(safe_items)},
    }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "mode": "telegram_error",
                "chat_id": chat_id,
                "items_count": len(safe_items),
                "error": str(exc),
                "buttons": buttons,
            }

    return {
        "mode": "telegram",
        "chat_id": chat_id,
        "items_count": len(safe_items),
        "message_id": str(data.get("result", {}).get("message_id", "")),
        "buttons": buttons,
    }


async def send_telegram_text(chat_id: str, text: str) -> dict:
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return {"mode": "mock", "chat_id": chat_id, "text": text}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, json={"chat_id": chat_id, "text": text})
            response.raise_for_status()
            return {"mode": "telegram", "ok": True}
        except Exception as exc:
            return {"mode": "telegram_error", "ok": False, "error": str(exc)}


async def send_telegram_message(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return {"mode": "mock", "chat_id": chat_id, "text": text}

    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return {"mode": "telegram", "ok": True}
        except Exception as exc:
            return {"mode": "telegram_error", "ok": False, "error": str(exc)}


async def answer_telegram_callback(callback_query_id: str, text: str | None = None) -> dict:
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return {"mode": "mock", "ok": True}

    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return {"mode": "telegram", "ok": True}
        except Exception as exc:
            return {"mode": "telegram_error", "ok": False, "error": str(exc)}


async def send_max_alert(chat_id: str, domain: str, token: str) -> dict:
    max_token = settings.max_token
    if not max_token:
        return {
            "mode": "max_mock",
            "chat_id": chat_id,
            "domain": domain,
            "buttons": [f"register:{token}", f"skip:{token}"],
        }

    base_url = settings.max_base_url.rstrip("/")
    url = f"{base_url}/messages"
    payload = {
        "text": f"Домен-кандидат: {domain}\nПодтверди регистрацию:",
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {"type": "callback", "text": "Зарегистрировать", "payload": f"register:{token}"},
                            {"type": "callback", "text": "Пропустить", "payload": f"skip:{token}"},
                        ]
                    ]
                },
            }
        ],
    }
    headers = {"Authorization": max_token, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, params={"chat_id": chat_id}, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json() if response.content else {}
        except Exception as exc:
            return {"mode": "max_error", "ok": False, "error": str(exc)}

    return {
        "mode": "max",
        "ok": True,
        "chat_id": chat_id,
        "domain": domain,
        "message_id": str(data.get("message_id") or data.get("id") or ""),
    }


async def send_max_text(chat_id: str, text: str) -> dict:
    max_token = settings.max_token
    if not max_token:
        return {"mode": "max_mock", "chat_id": chat_id, "text": text}

    base_url = settings.max_base_url.rstrip("/")
    url = f"{base_url}/messages"
    headers = {"Authorization": max_token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(url, params={"chat_id": chat_id}, headers=headers, json={"text": text})
            response.raise_for_status()
            return {"mode": "max", "ok": True}
        except Exception as exc:
            return {"mode": "max_error", "ok": False, "error": str(exc)}
