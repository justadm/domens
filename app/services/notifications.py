import uuid

import httpx

from app.config import settings


def build_confirmation_token() -> str:
    return f"cfm_{uuid.uuid4().hex}"


async def send_telegram_alert(chat_id: str, domain: str, token: str) -> dict:
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return {
            "mode": "mock",
            "chat_id": chat_id,
            "domain": domain,
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "buttons": [f"register:{token}", f"skip:{token}"],
        }

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": (
            f"Домен-кандидат: {domain}\n"
            "Нажми «Зарегистрировать», чтобы создать заказ на регистрацию."
        ),
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "Зарегистрировать", "callback_data": f"register:{token}"},
                    {"text": "Пропустить", "callback_data": f"skip:{token}"},
                ]
            ]
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
                "buttons": [f"register:{token}", f"skip:{token}"],
            }

    return {
        "mode": "telegram",
        "chat_id": chat_id,
        "domain": domain,
        "message_id": str(data.get("result", {}).get("message_id", "")),
        "buttons": [f"register:{token}", f"skip:{token}"],
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
