from fastapi import APIRouter

from app.schemas import TriggerAlertRequest, TriggerAlertResponse
from app.services.notifications import build_confirmation_token, send_telegram_alert
from app.state import store

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.post("/trigger", response_model=TriggerAlertResponse, status_code=201)
async def trigger_alert(payload: TriggerAlertRequest) -> TriggerAlertResponse:
    token = build_confirmation_token()
    alert = store.create_alert(payload.domain, payload.telegram_chat_id, token)
    await send_telegram_alert(payload.telegram_chat_id, payload.domain, token)
    return TriggerAlertResponse(
        alert_id=alert.alert_id,
        confirmation_token=token,
        status="sent",
    )
