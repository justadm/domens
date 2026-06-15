from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import (
    ConfirmRegistrationRequest,
    ConfirmRegistrationResponse,
    ExecuteRegistrationResponse,
)
from app.services.registrar import RegistrarClient
from app.state import store

router = APIRouter(prefix="/v1/registrations", tags=["registrations"])
registrar_client = RegistrarClient(provider=settings.registrar_provider)


@router.post("/confirm", response_model=ConfirmRegistrationResponse)
async def confirm_registration(
    payload: ConfirmRegistrationRequest,
) -> ConfirmRegistrationResponse:
    alert = store.get_alert_by_token(payload.confirmation_token)
    if not alert:
        raise HTTPException(status_code=404, detail="confirmation token not found")

    if alert.acknowledged:
        existing_order = store.get_latest_order_by_domain(alert.domain)
        if existing_order:
            return ConfirmRegistrationResponse(
                order_id=existing_order.order_id,
                domain=existing_order.domain,
                status=existing_order.status,
            )

    store.mark_alert_acknowledged(payload.confirmation_token)
    requested_by = store.get_telegram_user_id_by_chat_id(alert.telegram_chat_id) if alert.telegram_chat_id else None
    order = store.create_order(
        alert.domain,
        requested_by=requested_by,
        request_payload={"source": "confirm_token", "confirmation_token": payload.confirmation_token},
    )
    return ConfirmRegistrationResponse(
        order_id=order.order_id,
        domain=order.domain,
        status=order.status,
    )


@router.post("/{order_id}/execute", response_model=ExecuteRegistrationResponse)
async def execute_registration(order_id: str) -> ExecuteRegistrationResponse:
    order = store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    if not settings.registration_enabled:
        return ExecuteRegistrationResponse(
            order_id=order_id,
            status="blocked",
            registrar_response={
                "result": "blocked_by_config",
                "message": "Registration is disabled. Set REGISTRATION_ENABLED=true to enable.",
                "domain": order.domain,
            },
        )

    if order.status in {"registered", "failed", "canceled"}:
        return ExecuteRegistrationResponse(
            order_id=order_id,
            status=order.status,
            registrar_response={"result": "already_terminal", "domain": order.domain},
        )

    if settings.registration_require_available_check:
        check = await registrar_client.check_availability(order.domain)
        availability_check = {
            "provider": check.get("provider"),
            "available": check.get("available"),
            "status": check.get("status"),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if check.get("available") is not True:
            store.set_order_status(
                order_id,
                "failed",
                response_payload={"availability_check": availability_check},
                error_message="fresh availability check failed",
            )
            return ExecuteRegistrationResponse(
                order_id=order_id,
                status="failed",
                registrar_response={
                    "result": "precheck_unavailable",
                    "domain": order.domain,
                    "check": check,
                    "availability_check": availability_check,
                },
            )

    store.set_order_status(order_id, "sent_to_registrar")
    registrar_response = await registrar_client.register_domain(order.domain)
    if registrar_response.get("result") == "registered":
        store.set_order_status(order_id, "registered")
        status = "registered"
    else:
        error_message = None
        if registrar_response.get("result") == "reserved_dns_zone":
            error_message = "dns zone reserved but domain was not registered"
        store.set_order_status(order_id, "failed", response_payload=registrar_response, error_message=error_message)
        status = "failed"

    return ExecuteRegistrationResponse(
        order_id=order_id,
        status=status,
        registrar_response=registrar_response,
    )
