from fastapi import APIRouter, Request

from app.config import settings
from app.routers.guards import require_admin_user
from app.schemas import TriggerAlertRequest, TriggerAlertResponse
from app.services.notifications import build_confirmation_token, send_max_alert, send_telegram_alert
from app.state import store

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.post("/trigger", response_model=TriggerAlertResponse, status_code=201)
async def trigger_alert(payload: TriggerAlertRequest, request: Request) -> TriggerAlertResponse:
    require_admin_user(request)
    token = build_confirmation_token()
    alert = store.create_alert(payload.domain, payload.telegram_chat_id, token)
    await send_telegram_alert(payload.telegram_chat_id, payload.domain, token)
    if settings.max_chat_id:
        await send_max_alert(settings.max_chat_id, payload.domain, token)
    return TriggerAlertResponse(
        alert_id=alert.alert_id,
        confirmation_token=token,
        status="sent",
    )
