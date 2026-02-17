from fastapi import APIRouter, HTTPException

from app.schemas import ConfirmRegistrationRequest
from app.services.notifications import send_telegram_text
from app.state import store

router = APIRouter(prefix="/v1/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(payload: dict) -> dict:
    callback_query = payload.get("callback_query", {}) if isinstance(payload, dict) else {}
    callback_data = callback_query.get("data") or payload.get("callback_data")
    from_user_id = (
        str(callback_query.get("from", {}).get("id"))
        if isinstance(callback_query, dict)
        else str(payload.get("from_user", ""))
    )
    chat_id = (
        str(callback_query.get("message", {}).get("chat", {}).get("id"))
        if isinstance(callback_query, dict)
        else ""
    )

    if not callback_data:
        raise HTTPException(status_code=400, detail="invalid callback_data")

    parts = str(callback_data).split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="invalid callback_data")

    action, token = parts
    alert = store.get_alert_by_token(token)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    if action == "skip":
        store.mark_alert_acknowledged(token)
        if chat_id:
            await send_telegram_text(chat_id, f"Пропущено: {alert.domain}")
        return {"ok": True, "action": "skip", "domain": alert.domain}

    if action == "register":
        from app.routers.registrations import confirm_registration

        result = await confirm_registration(
            ConfirmRegistrationRequest(
                confirmation_token=token,
                confirmed_by=f"tg:{from_user_id}",
            )
        )
        if chat_id:
            await send_telegram_text(
                chat_id,
                f"Создан заказ: {result.order_id} для {result.domain}. Запусти execute для завершения регистрации.",
            )
        return {
            "ok": True,
            "action": "register",
            "order_id": result.order_id,
            "domain": result.domain,
            "status": result.status,
        }

    raise HTTPException(status_code=400, detail="unknown callback action")
