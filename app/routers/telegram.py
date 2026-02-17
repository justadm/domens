from fastapi import APIRouter, HTTPException

from app.schemas import ConfirmRegistrationRequest, TelegramWebhookRequest
from app.state import store

router = APIRouter(prefix="/v1/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(payload: TelegramWebhookRequest) -> dict:
    parts = payload.callback_data.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="invalid callback_data")

    action, token = parts
    alert = store.get_alert_by_token(token)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    if action == "skip":
        store.mark_alert_acknowledged(token)
        return {"ok": True, "action": "skip", "domain": alert.domain}

    if action == "register":
        from app.routers.registrations import confirm_registration

        result = await confirm_registration(
            ConfirmRegistrationRequest(
                confirmation_token=token,
                confirmed_by=f"tg:{payload.from_user}",
            )
        )
        return {
            "ok": True,
            "action": "register",
            "order_id": result.order_id,
            "domain": result.domain,
            "status": result.status,
        }

    raise HTTPException(status_code=400, detail="unknown callback action")
