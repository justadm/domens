import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Alert:
    alert_id: str
    domain: str
    telegram_chat_id: str
    confirmation_token: str
    acknowledged: bool = False


@dataclass
class RegistrationOrder:
    order_id: str
    domain: str
    status: str
    created_at: datetime


class InMemoryStore:
    def __init__(self) -> None:
        self.alerts_by_token: dict[str, Alert] = {}
        self.orders_by_id: dict[str, RegistrationOrder] = {}

    def create_alert(self, domain: str, telegram_chat_id: str, token: str) -> Alert:
        alert = Alert(
            alert_id=f"alrt_{uuid.uuid4().hex[:10]}",
            domain=domain,
            telegram_chat_id=telegram_chat_id,
            confirmation_token=token,
        )
        self.alerts_by_token[token] = alert
        return alert

    def get_alert_by_token(self, token: str) -> Alert | None:
        return self.alerts_by_token.get(token)

    def mark_alert_acknowledged(self, token: str) -> None:
        alert = self.alerts_by_token[token]
        alert.acknowledged = True

    def create_order(self, domain: str) -> RegistrationOrder:
        order = RegistrationOrder(
            order_id=f"ord_{uuid.uuid4().hex[:10]}",
            domain=domain,
            status="queued",
            created_at=datetime.now(timezone.utc),
        )
        self.orders_by_id[order.order_id] = order
        return order

    def get_order(self, order_id: str) -> RegistrationOrder | None:
        return self.orders_by_id.get(order_id)

    def set_order_status(self, order_id: str, status: str) -> None:
        order = self.orders_by_id[order_id]
        order.status = status
