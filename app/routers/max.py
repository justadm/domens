from fastapi import APIRouter, HTTPException

from app.schemas import ConfirmRegistrationRequest
from app.services.notifications import send_max_text
from app.state import store
from app.routers.copilot import process_copilot_confirm, process_copilot_message

router = APIRouter(prefix="/v1/max", tags=["max"])


def _extract_callback(payload: dict) -> tuple[str, str, str]:
    callback = payload.get("callback", {}) if isinstance(payload, dict) else {}
    callback_data = callback.get("payload") or callback.get("data") or payload.get("callback_data")
    chat_id = (
        str(callback.get("chat_id"))
        if callback.get("chat_id") is not None
        else str(payload.get("chat_id") or "")
    )
    user_id = str((callback.get("sender") or {}).get("user_id") or payload.get("from_user") or "")

    if not callback_data:
        raise HTTPException(status_code=400, detail="invalid callback payload")

    return str(callback_data), chat_id, user_id


@router.post("/webhook")
async def max_webhook(payload: dict) -> dict:
    message_text = str(((payload.get("message") or {}).get("text") if isinstance(payload, dict) else "") or "").strip()
    chat_id_text = str((payload.get("chat_id") if isinstance(payload, dict) else "") or "")
    sender_text = str((((payload.get("message") or {}).get("sender") or {}).get("user_id") if isinstance(payload, dict) else "") or "")
    if message_text and sender_text:
        lowered = message_text.lower()
        if lowered.startswith("/ask "):
            data = await process_copilot_message(
                user_id=f"max:{sender_text}",
                message=message_text[5:].strip(),
                mode="assistant",
                channel="max",
            )
            reply = data.reply
            if data.requires_confirmation and data.confirmation_token:
                reply += f"\n\nConfirm: /confirm {data.confirmation_token}\nCancel: /cancel {data.confirmation_token}"
            if chat_id_text:
                await send_max_text(chat_id_text, reply)
            return {"ok": True, "action": "copilot_ask"}
        if lowered.startswith("/chat "):
            data = await process_copilot_message(
                user_id=f"max:{sender_text}",
                message=message_text[6:].strip(),
                mode="chat",
                channel="max",
            )
            if chat_id_text:
                await send_max_text(chat_id_text, data.reply)
            return {"ok": True, "action": "copilot_chat"}
        if lowered.startswith("/confirm "):
            token = message_text[9:].strip()
            result = await process_copilot_confirm(user_id=f"max:{sender_text}", confirmation_token=token, decision="confirm")
            if chat_id_text:
                await send_max_text(chat_id_text, f"{result.status}: {result.message}")
            return {"ok": True, "action": "copilot_confirm"}
        if lowered.startswith("/cancel "):
            token = message_text[8:].strip()
            result = await process_copilot_confirm(user_id=f"max:{sender_text}", confirmation_token=token, decision="cancel")
            if chat_id_text:
                await send_max_text(chat_id_text, f"{result.status}: {result.message}")
            return {"ok": True, "action": "copilot_cancel"}

    callback_data, chat_id, user_id = _extract_callback(payload)
    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="invalid callback_data")

    action, token = parts
    alert = store.get_alert_by_token(token)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    if action == "skip":
        store.mark_alert_acknowledged(token)
        if chat_id:
            await send_max_text(chat_id, f"Пропущено: {alert.domain}")
        return {"ok": True, "action": "skip", "domain": alert.domain}

    if action == "register":
        from app.routers.registrations import confirm_registration, execute_registration

        result = await confirm_registration(
            ConfirmRegistrationRequest(
                confirmation_token=token,
                confirmed_by=f"max:{user_id}",
            )
        )
        execute_result = await execute_registration(result.order_id)
        if chat_id:
            await send_max_text(chat_id, f"Заказ {result.order_id}: {execute_result.status} ({result.domain})")
        return {
            "ok": True,
            "action": "register",
            "order_id": result.order_id,
            "domain": result.domain,
            "status": execute_result.status,
            "registrar_response": execute_result.registrar_response,
        }

    raise HTTPException(status_code=400, detail="unknown callback action")
