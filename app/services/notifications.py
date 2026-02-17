import uuid


def build_confirmation_token() -> str:
    return f"cfm_{uuid.uuid4().hex}"


async def send_telegram_alert(chat_id: str, domain: str, token: str) -> dict:
    # MVP stub. Integrate Telegram Bot API sendMessage in production.
    return {
        "chat_id": chat_id,
        "domain": domain,
        "message_id": f"msg_{uuid.uuid4().hex[:8]}",
        "buttons": [f"register:{token}", f"skip:{token}"],
    }
