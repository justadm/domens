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
    order = store.create_order(alert.domain)
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

    if order.status in {"registered", "failed", "canceled"}:
        return ExecuteRegistrationResponse(
            order_id=order_id,
            status=order.status,
            registrar_response={"result": "already_terminal", "domain": order.domain},
        )

    store.set_order_status(order_id, "sent_to_registrar")
    registrar_response = await registrar_client.register_domain(order.domain)
    if registrar_response.get("result") in {"registered", "reserved_dns_zone"}:
        store.set_order_status(order_id, "registered")
        status = "registered"
    else:
        store.set_order_status(order_id, "failed")
        status = "failed"

    return ExecuteRegistrationResponse(
        order_id=order_id,
        status=status,
        registrar_response=registrar_response,
    )
