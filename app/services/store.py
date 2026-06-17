from __future__ import annotations

import uuid
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    and_,
    asc,
    case,
    create_engine,
    desc,
    exists,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, aliased, declarative_base, mapped_column, relationship, sessionmaker


Base = declarative_base()


def _normalize_watch_rule_tlds(tlds: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in tlds or []:
        value = str(item).strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _build_alert_suppression_state(rows: list[dict], now: datetime | None = None) -> dict | None:
    current = now or datetime.now(timezone.utc)
    active_rows = [
        row
        for row in rows
        if row.get("reason") in {"user_less", "user_never"}
        and (row.get("expires_at") is None or row["expires_at"] > current)
    ]
    if not active_rows:
        return None

    priority = {"user_never": 0, "user_less": 1}
    selected = sorted(
        active_rows,
        key=lambda row: (
            priority.get(str(row.get("reason")), 99),
            -(row.get("created_at") or current).timestamp(),
        ),
    )[0]
    return {
        "active": True,
        "reason": selected.get("reason"),
        "created_at": selected.get("created_at").isoformat() if selected.get("created_at") else None,
        "expires_at": selected.get("expires_at").isoformat() if selected.get("expires_at") else None,
    }


def _build_cabinet_digest_item(event, channel: str | None = None) -> dict:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        payload = {}
    delivery = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
    domains = payload.get("domains") if isinstance(payload.get("domains"), list) else []
    items_count = payload.get("items_count") or delivery.get("items_count") or len(domains)

    return {
        "id": str(event.id),
        "channel": channel or "telegram",
        "channel_target": str(payload.get("destination") or delivery.get("chat_id") or event.telegram_chat_id or ""),
        "created_at": event.created_at.isoformat(),
        "domains": [str(item) for item in domains],
        "items_count": int(items_count or 0),
        "message_id": str(delivery["message_id"]) if delivery.get("message_id") is not None else None,
        "delivery": delivery,
    }


def summarize_monitor_quality_events(events: list[dict]) -> dict:
    monitor_runs_total = 0
    monitor_alerts_sent = 0
    monitor_digests_sent = 0
    monitor_checked_total = 0
    monitor_skip_reasons: dict[str, int] = {}
    telegram_errors_total = 0
    duplicate_groups: dict[tuple[str, str], dict] = {}

    for event in events:
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        if event_type == "monitor_run_finished":
            monitor_runs_total += 1
            monitor_checked_total += int(payload.get("checked") or 0)
            for reason, count in (payload.get("skip_reasons") or {}).items():
                safe_reason = str(reason)
                monitor_skip_reasons[safe_reason] = monitor_skip_reasons.get(safe_reason, 0) + int(count or 0)
        elif event_type == "monitor_alert_sent":
            monitor_alerts_sent += 1
            fqdn = str(payload.get("fqdn") or "").strip().lower()
            destination = str(payload.get("destination") or event.get("telegram_chat_id") or "").strip()
            created_at = event.get("created_at")
            if fqdn and destination:
                key = (destination, fqdn)
                group = duplicate_groups.setdefault(
                    key,
                    {
                        "destination": destination,
                        "fqdn": fqdn,
                        "count": 0,
                        "first_sent_at": None,
                        "last_sent_at": None,
                    },
                )
                group["count"] += 1
                if created_at:
                    created_text = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
                    if group["first_sent_at"] is None or created_text < group["first_sent_at"]:
                        group["first_sent_at"] = created_text
                    if group["last_sent_at"] is None or created_text > group["last_sent_at"]:
                        group["last_sent_at"] = created_text
        elif event_type == "monitor_digest_sent":
            monitor_digests_sent += 1

        lowered = event_type.lower()
        if "telegram" in lowered and "error" in lowered:
            telegram_errors_total += 1
        elif isinstance(payload.get("delivery"), dict) and payload["delivery"].get("mode") == "telegram_error":
            telegram_errors_total += 1

    duplicate_alert_groups = sorted(
        (group for group in duplicate_groups.values() if int(group["count"]) > 1),
        key=lambda group: (-int(group["count"]), str(group["destination"]), str(group["fqdn"])),
    )

    return {
        "monitor_runs_total": monitor_runs_total,
        "monitor_alerts_sent": monitor_alerts_sent,
        "monitor_digests_sent": monitor_digests_sent,
        "monitor_checked_total": monitor_checked_total,
        "monitor_skip_reasons": dict(sorted(monitor_skip_reasons.items())),
        "monitor_duplicate_alert_groups": duplicate_alert_groups[:20],
        "monitor_duplicate_alert_groups_total": len(duplicate_alert_groups),
        "telegram_errors_total": telegram_errors_total,
    }

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {
        "cabinet.read",
    },
    "viewer_admin": {
        "admin.panel.read",
    },
    "operator": {
        "cabinet.read",
        "watch.manage",
        "alerts.manage",
        "copilot.register_domain",
    },
    "manager_admin": {
        "admin.panel.read",
        "admin.roles.manage.basic",
    },
    "admin": {
        "cabinet.read",
        "watch.manage",
        "alerts.manage",
        "copilot.register_domain",
        "admin.panel.read",
        "admin.roles.manage.basic",
    },
    "superadmin": {
        "cabinet.read",
        "watch.manage",
        "alerts.manage",
        "copilot.register_domain",
        "admin.panel.read",
        "admin.roles.manage.basic",
        "admin.roles.manage.elevated",
    },
}

CAPABILITY_PERMISSIONS: dict[str, str] = {
    "cabinet_read": "cabinet.read",
    "watch_manage": "watch.manage",
    "alerts_manage": "alerts.manage",
    "copilot_register_domain": "copilot.register_domain",
    "admin_panel_read": "admin.panel.read",
    "admin_roles_manage_basic": "admin.roles.manage.basic",
    "admin_roles_manage_elevated": "admin.roles.manage.elevated",
}


def _permissions_from_roles(role_codes: list[str]) -> list[str]:
    roles = {item.lower() for item in role_codes}
    permissions: set[str] = set()
    for role in roles:
        permissions |= ROLE_PERMISSIONS.get(role, set())
    return sorted(permissions)


def _capabilities_from_permissions(permissions: list[str]) -> dict[str, bool]:
    granted = set(permissions)
    return {key: (permission in granted) for key, permission in CAPABILITY_PERMISSIONS.items()}


class DomainStatus(str, Enum):
    UNKNOWN = "unknown"
    REGISTERED = "registered"
    AVAILABLE = "available"
    PENDING_DELETE = "pending_delete"
    REDEMPTION = "redemption"
    CLIENT_HOLD = "client_hold"
    INACTIVE = "inactive"


class RegistrationStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    SENT_TO_REGISTRAR = "sent_to_registrar"
    REGISTERED = "registered"
    FAILED = "failed"
    CANCELED = "canceled"


class DomainModel(Base):
    __tablename__ = "domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fqdn: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    sld: Mapped[str] = mapped_column(Text, nullable=False)
    tld: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_status: Mapped[DomainStatus] = mapped_column(
        SAEnum(
            DomainStatus,
            name="domain_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=DomainStatus.UNKNOWN,
    )
    status_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    drop_time_estimated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    alerts: Mapped[list["AlertModel"]] = relationship(back_populates="domain")
    status_history: Mapped[list["DomainStatusHistoryModel"]] = relationship(back_populates="domain")
    registration_orders: Mapped[list["RegistrationOrderModel"]] = relationship(back_populates="domain")


class AlertModel(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual_trigger")
    confirmation_token: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    explanation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    delivery_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    domain: Mapped[DomainModel] = relationship(back_populates="alerts")


class AlertFeedbackModel(Base):
    __tablename__ = "alert_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False)
    telegram_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class AlertSuppressionModel(Base):
    __tablename__ = "alert_suppressions"
    __table_args__ = (UniqueConstraint("fqdn", "destination", "reason", name="uq_alert_suppressions_target_reason"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fqdn: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class RegistrationOrderModel(Base):
    __tablename__ = "registration_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[RegistrationStatus] = mapped_column(
        SAEnum(
            RegistrationStatus,
            name="registration_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=RegistrationStatus.CREATED,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    domain: Mapped[DomainModel] = relationship(back_populates="registration_orders")


class DomainStatusHistoryModel(Base):
    __tablename__ = "domain_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    status: Mapped[DomainStatus] = mapped_column(
        SAEnum(
            DomainStatus,
            name="domain_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    domain: Mapped[DomainModel] = relationship(back_populates="status_history")


class TelegramUserModel(Base):
    __tablename__ = "telegram_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    disclaimer_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disclaimer_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class UserWatchRuleModel(Base):
    __tablename__ = "user_watch_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("telegram_users.id"), nullable=False)
    watch_query: Mapped[str] = mapped_column(Text, nullable=False)
    tlds: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    min_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_price_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_length: Mapped[int | None] = mapped_column(nullable=True)
    daily_alert_limit: Mapped[int] = mapped_column(nullable=False, default=3)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class UserSubscriptionModel(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("telegram_users.id"), nullable=False)
    channel_type: Mapped[str] = mapped_column(Text, nullable=False, default="telegram")
    channel_target: Mapped[str] = mapped_column(Text, nullable=False)
    alert_types: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class RoleModel(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class UserRoleModel(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("telegram_users.id"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class BotEventModel(Base):
    __tablename__ = "bot_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id"), nullable=True
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class AccessEventModel(Base):
    __tablename__ = "access_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id"), nullable=True
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    role_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="web")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ConversationMessageModel(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    telegram_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class CopilotActionConfirmationModel(Base):
    __tablename__ = "copilot_action_confirmations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    telegram_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    action_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    confirmation_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class CopilotEventModel(Base):
    __tablename__ = "copilot_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    confirmation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_action_confirmations.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Alert:
    alert_id: str
    domain: str
    telegram_chat_id: str
    confirmation_token: str
    acknowledged: bool = False
    explanation: dict | None = None


@dataclass
class RegistrationOrder:
    order_id: str
    domain: str
    status: str
    created_at: datetime


@dataclass
class TelegramUser:
    telegram_user_id: str
    telegram_chat_id: str | None
    username: str | None
    first_name: str | None
    locale: str | None
    disclaimer_accepted_at: datetime | None
    disclaimer_version: str | None


class PostgresStore:
    def __init__(self, postgres_dsn: str) -> None:
        dsn = self._normalize_dsn(postgres_dsn)
        self.engine = create_engine(dsn, future=True, pool_pre_ping=True)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    @staticmethod
    def _normalize_dsn(postgres_dsn: str) -> str:
        if postgres_dsn.startswith("postgresql://"):
            return postgres_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        return postgres_dsn

    def _session(self) -> Session:
        return self.session_factory()

    def ping(self) -> bool:
        try:
            with self._session() as session:
                session.execute(select(1))
            return True
        except Exception:
            return False

    @staticmethod
    def _split_domain(fqdn: str) -> tuple[str, str]:
        cleaned = fqdn.strip().lower()
        parts = cleaned.split(".")
        if len(parts) < 2:
            return cleaned, ""
        return ".".join(parts[:-1]), parts[-1]

    def _get_or_create_domain(self, session: Session, fqdn: str) -> DomainModel:
        domain = session.execute(
            select(DomainModel).where(DomainModel.fqdn == fqdn.strip().lower())
        ).scalar_one_or_none()
        if domain:
            return domain

        sld, tld = self._split_domain(fqdn)
        domain = DomainModel(
            fqdn=fqdn.strip().lower(),
            sld=sld,
            tld=tld,
            current_status=DomainStatus.UNKNOWN,
            source="manual",
        )
        session.add(domain)
        session.flush()
        return domain

    @staticmethod
    def _normalize_domain_status(status: str) -> DomainStatus:
        try:
            return DomainStatus(status)
        except ValueError:
            return DomainStatus.UNKNOWN

    def create_alert(
        self,
        domain: str,
        telegram_chat_id: str,
        token: str,
        alert_type: str = "manual_trigger",
        explanation: dict | None = None,
        delivery_payload: dict | None = None,
    ) -> Alert:
        with self._session() as session:
            domain_model = self._get_or_create_domain(session, domain)
            alert = AlertModel(
                domain_id=domain_model.id,
                telegram_chat_id=telegram_chat_id,
                alert_type=alert_type,
                confirmation_token=token,
                explanation=explanation or {},
                delivery_payload=delivery_payload or {},
                acknowledged=False,
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            return Alert(
                alert_id=str(alert.id),
                domain=domain_model.fqdn,
                telegram_chat_id=alert.telegram_chat_id,
                confirmation_token=token,
                acknowledged=alert.acknowledged,
            )

    def get_alert_by_token(self, token: str) -> Alert | None:
        with self._session() as session:
            row = session.execute(
                select(AlertModel, DomainModel)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .where(AlertModel.confirmation_token == token)
                .limit(1)
            ).first()
            if not row:
                return None
            alert, domain = row
            return Alert(
                alert_id=str(alert.id),
                domain=domain.fqdn,
                telegram_chat_id=alert.telegram_chat_id,
                confirmation_token=token,
                acknowledged=alert.acknowledged,
                explanation=alert.explanation or {},
            )

    def mark_alert_acknowledged(self, token: str) -> None:
        with self._session() as session:
            alert = session.execute(
                select(AlertModel).where(AlertModel.confirmation_token == token).limit(1)
            ).scalar_one_or_none()
            if not alert:
                return
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now(timezone.utc)
            session.commit()

    def create_order(
        self,
        domain: str,
        requested_by: str | None = None,
        request_payload: dict | None = None,
    ) -> RegistrationOrder:
        with self._session() as session:
            domain_model = self._get_or_create_domain(session, domain)
            order = RegistrationOrderModel(
                domain_id=domain_model.id,
                requested_by=str(requested_by).strip() if requested_by else None,
                status=RegistrationStatus.QUEUED,
                request_payload=request_payload or {},
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            return RegistrationOrder(
                order_id=str(order.id),
                domain=domain_model.fqdn,
                status=order.status.value,
                created_at=order.created_at,
            )

    def list_user_registration_orders_page(
        self,
        telegram_user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
    ) -> dict:
        safe_uid = str(telegram_user_id).strip()
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        target_status = (status or "").strip().lower()
        q = (search or "").strip().lower()

        if not safe_uid:
            return {
                "items": [],
                "total": 0,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": None,
                "prev_offset": None,
            }

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return {
                    "items": [],
                    "total": 0,
                    "limit": safe_limit,
                    "offset": safe_offset,
                    "next_offset": None,
                    "prev_offset": None,
                }

            ownership_filters = [RegistrationOrderModel.requested_by == safe_uid]
            if user.telegram_chat_id:
                ownership_filters.append(
                    exists(
                        select(AlertModel.id)
                        .where(AlertModel.domain_id == RegistrationOrderModel.domain_id)
                        .where(AlertModel.telegram_chat_id == user.telegram_chat_id)
                    )
                )
            filters = [or_(*ownership_filters)]
            if target_status:
                filters.append(func.lower(func.cast(RegistrationOrderModel.status, Text)) == target_status)
            if q:
                filters.append(
                    or_(
                        func.lower(DomainModel.fqdn).contains(q),
                        func.lower(func.coalesce(RegistrationOrderModel.requested_by, "")).contains(q),
                        func.lower(func.coalesce(RegistrationOrderModel.error_message, "")).contains(q),
                    )
                )

            base_query = (
                select(RegistrationOrderModel, DomainModel)
                .join(DomainModel, DomainModel.id == RegistrationOrderModel.domain_id)
                .where(and_(*filters))
            )
            total_query = (
                select(func.count())
                .select_from(RegistrationOrderModel)
                .join(DomainModel, DomainModel.id == RegistrationOrderModel.domain_id)
                .where(and_(*filters))
            )

            total = int(session.execute(total_query).scalar() or 0)
            rows = session.execute(
                base_query.order_by(desc(RegistrationOrderModel.created_at)).offset(safe_offset).limit(safe_limit)
            ).all()

            items: list[dict] = []
            for order, domain in rows:
                items.append(
                    {
                        "id": str(order.id),
                        "domain": domain.fqdn,
                        "status": order.status.value,
                        "requested_by": order.requested_by,
                        "error_message": order.error_message,
                        "created_at": order.created_at.isoformat(),
                        "updated_at": order.updated_at.isoformat(),
                        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
                    }
                )

            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def list_user_alerts_page(
        self,
        telegram_user_id: str,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        feedback: str | None = None,
        domains: list[str] | None = None,
    ) -> dict:
        safe_uid = str(telegram_user_id).strip()
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        q = (search or "").strip().lower()
        target_feedback = (feedback or "").strip().lower()
        target_domains = sorted(
            {
                str(domain).strip().lower()
                for domain in domains or []
                if str(domain).strip()
            }
        )

        empty = {
            "items": [],
            "total": 0,
            "limit": safe_limit,
            "offset": safe_offset,
            "next_offset": None,
            "prev_offset": None,
        }
        if not safe_uid:
            return empty

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return empty

            subscriptions = list(
                session.execute(
                    select(UserSubscriptionModel)
                    .where(UserSubscriptionModel.user_id == user.id)
                    .order_by(desc(UserSubscriptionModel.updated_at))
                ).scalars()
            )
            destination_channels: dict[str, str] = {}
            if user.telegram_chat_id:
                destination_channels[str(user.telegram_chat_id)] = "telegram"
            for sub in subscriptions:
                if sub.channel_target:
                    destination_channels[str(sub.channel_target)] = sub.channel_type

            destinations = sorted(destination_channels)
            if not destinations:
                return empty

            filters = [AlertModel.telegram_chat_id.in_(destinations)]
            if target_domains:
                filters.append(func.lower(DomainModel.fqdn).in_(target_domains))
            if q:
                filters.append(
                    or_(
                        func.lower(DomainModel.fqdn).contains(q),
                        func.lower(AlertModel.alert_type).contains(q),
                        func.lower(AlertModel.telegram_chat_id).contains(q),
                        func.lower(func.cast(AlertModel.explanation, Text)).contains(q),
                    )
                )
            if target_feedback:
                filters.append(
                    exists(
                        select(AlertFeedbackModel.id)
                        .where(AlertFeedbackModel.alert_id == AlertModel.id)
                        .where(AlertFeedbackModel.telegram_user_id == safe_uid)
                        .where(func.lower(AlertFeedbackModel.feedback_type) == target_feedback)
                    )
                )

            total_query = (
                select(func.count())
                .select_from(AlertModel)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .where(and_(*filters))
            )
            total = int(session.execute(total_query).scalar() or 0)

            rows = session.execute(
                select(AlertModel, DomainModel)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .where(and_(*filters))
                .order_by(desc(AlertModel.created_at))
                .offset(safe_offset)
                .limit(safe_limit)
            ).all()
            alert_ids = [alert.id for alert, _domain in rows]
            alert_domains = sorted({domain.fqdn for _alert, domain in rows})

            feedback_rows = []
            if alert_ids:
                feedback_rows = session.execute(
                    select(AlertFeedbackModel)
                    .where(AlertFeedbackModel.alert_id.in_(alert_ids))
                    .where(AlertFeedbackModel.telegram_user_id == safe_uid)
                    .order_by(desc(AlertFeedbackModel.created_at))
                ).scalars()

            latest_feedback_by_alert: dict[uuid.UUID, dict] = {}
            feedback_counts_by_alert: dict[uuid.UUID, dict[str, int]] = {}
            for row in feedback_rows:
                counts = feedback_counts_by_alert.setdefault(row.alert_id, {})
                counts[row.feedback_type] = counts.get(row.feedback_type, 0) + 1
                latest_feedback_by_alert.setdefault(
                    row.alert_id,
                    {
                        "type": row.feedback_type,
                        "created_at": row.created_at.isoformat(),
                        "payload": row.payload or {},
                    },
                )

            suppression_rows_by_target: dict[tuple[str, str], list[dict]] = {}
            if alert_domains:
                now = datetime.now(timezone.utc)
                suppression_rows = session.execute(
                    select(AlertSuppressionModel)
                    .where(AlertSuppressionModel.fqdn.in_(alert_domains))
                    .where(AlertSuppressionModel.destination.in_(destinations))
                    .where(AlertSuppressionModel.reason.in_(["user_less", "user_never"]))
                    .where(
                        or_(
                            AlertSuppressionModel.expires_at.is_(None),
                            AlertSuppressionModel.expires_at > now,
                        )
                    )
                    .order_by(desc(AlertSuppressionModel.created_at))
                ).scalars()
                for row in suppression_rows:
                    suppression_rows_by_target.setdefault((row.fqdn, row.destination), []).append(
                        {
                            "reason": row.reason,
                            "created_at": row.created_at,
                            "expires_at": row.expires_at,
                        }
                    )

            items: list[dict] = []
            for alert, domain in rows:
                channel_target = str(alert.telegram_chat_id)
                items.append(
                    {
                        "id": str(alert.id),
                        "domain_id": str(domain.id),
                        "domain": domain.fqdn,
                        "alert_type": alert.alert_type,
                        "channel": destination_channels.get(channel_target, "telegram"),
                        "channel_target": channel_target,
                        "acknowledged": bool(alert.acknowledged),
                        "created_at": alert.created_at.isoformat(),
                        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                        "explanation": alert.explanation or {},
                        "latest_feedback": latest_feedback_by_alert.get(alert.id),
                        "feedback_counts": feedback_counts_by_alert.get(alert.id, {}),
                        "suppression_state": _build_alert_suppression_state(
                            suppression_rows_by_target.get((domain.fqdn, channel_target), [])
                        ),
                    }
                )

            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def list_user_digests_page(
        self,
        telegram_user_id: str,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> dict:
        safe_uid = str(telegram_user_id).strip()
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        q = (search or "").strip().lower()

        empty = {
            "items": [],
            "total": 0,
            "limit": safe_limit,
            "offset": safe_offset,
            "next_offset": None,
            "prev_offset": None,
        }
        if not safe_uid:
            return empty

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return empty

            subscriptions = list(
                session.execute(
                    select(UserSubscriptionModel)
                    .where(UserSubscriptionModel.user_id == user.id)
                    .order_by(desc(UserSubscriptionModel.updated_at))
                ).scalars()
            )
            destination_channels: dict[str, str] = {}
            if user.telegram_chat_id:
                destination_channels[str(user.telegram_chat_id)] = "telegram"
            for sub in subscriptions:
                if sub.channel_target:
                    destination_channels[str(sub.channel_target)] = sub.channel_type

            destinations = sorted(destination_channels)
            if not destinations:
                return empty

            filters = [
                BotEventModel.event_type == "monitor_digest_sent",
                BotEventModel.telegram_chat_id.in_(destinations),
            ]
            if q:
                filters.append(
                    or_(
                        func.lower(BotEventModel.telegram_chat_id).contains(q),
                        func.lower(func.cast(BotEventModel.payload, Text)).contains(q),
                    )
                )

            total_query = select(func.count()).select_from(BotEventModel).where(and_(*filters))
            total = int(session.execute(total_query).scalar() or 0)

            rows = session.execute(
                select(BotEventModel)
                .where(and_(*filters))
                .order_by(desc(BotEventModel.created_at))
                .offset(safe_offset)
                .limit(safe_limit)
            ).scalars()

            items = [
                _build_cabinet_digest_item(event, channel=destination_channels.get(str(event.telegram_chat_id), "telegram"))
                for event in rows
            ]
            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def record_user_alert_feedback(
        self,
        alert_id: str,
        telegram_user_id: str,
        feedback_type: str,
        payload: dict | None = None,
    ) -> dict | None:
        safe_uid = str(telegram_user_id).strip()
        safe_feedback = str(feedback_type).strip().lower()
        if not safe_uid or safe_feedback not in {"more", "less", "why", "never"}:
            return None
        try:
            safe_alert_id = uuid.UUID(str(alert_id))
        except ValueError:
            return None

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return None

            destinations: set[str] = set()
            if user.telegram_chat_id:
                destinations.add(str(user.telegram_chat_id))
            subscription_targets = session.execute(
                select(UserSubscriptionModel.channel_target).where(UserSubscriptionModel.user_id == user.id)
            ).scalars()
            destinations.update(str(target) for target in subscription_targets if target)
            if not destinations:
                return None

            row = session.execute(
                select(AlertModel, DomainModel)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .where(AlertModel.id == safe_alert_id)
                .where(AlertModel.telegram_chat_id.in_(sorted(destinations)))
                .limit(1)
            ).first()
            if not row:
                return None

            alert, domain = row
            feedback = AlertFeedbackModel(
                alert_id=alert.id,
                telegram_user_id=safe_uid,
                feedback_type=safe_feedback,
                payload=payload or {},
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)
            return {
                "alert_id": str(alert.id),
                "domain": domain.fqdn,
                "channel_target": str(alert.telegram_chat_id),
                "explanation": alert.explanation or {},
                "feedback": {
                    "type": feedback.feedback_type,
                    "created_at": feedback.created_at.isoformat(),
                    "payload": feedback.payload or {},
                },
            }

    def list_user_domains_page(
        self,
        telegram_user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        tld: str | None = None,
    ) -> dict:
        safe_uid = str(telegram_user_id).strip()
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        target_status = (status or "").strip().lower()
        target_tld = (tld or "").strip().lower().lstrip(".")
        q = (search or "").strip().lower()

        if not safe_uid:
            return {
                "items": [],
                "total": 0,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": None,
                "prev_offset": None,
            }

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return {
                    "items": [],
                    "total": 0,
                    "limit": safe_limit,
                    "offset": safe_offset,
                    "next_offset": None,
                    "prev_offset": None,
                }

            ownership_filters = [
                exists(
                    select(RegistrationOrderModel.id)
                    .where(RegistrationOrderModel.domain_id == DomainModel.id)
                    .where(RegistrationOrderModel.requested_by == safe_uid)
                )
            ]
            if user.telegram_chat_id:
                ownership_filters.append(
                    exists(
                        select(AlertModel.id)
                        .where(AlertModel.domain_id == DomainModel.id)
                        .where(AlertModel.telegram_chat_id == user.telegram_chat_id)
                    )
                )
            filters = [or_(*ownership_filters)]
            if target_status:
                filters.append(func.lower(func.cast(DomainModel.current_status, Text)) == target_status)
            if target_tld:
                filters.append(func.lower(DomainModel.tld) == target_tld)
            if q:
                filters.append(
                    or_(
                        func.lower(DomainModel.fqdn).contains(q),
                        func.lower(func.coalesce(DomainModel.source, "")).contains(q),
                    )
                )

            total_query = select(func.count()).select_from(DomainModel).where(and_(*filters))
            total = int(session.execute(total_query).scalar() or 0)

            rows = session.execute(
                select(DomainModel)
                .where(and_(*filters))
                .order_by(desc(DomainModel.updated_at))
                .offset(safe_offset)
                .limit(safe_limit)
            ).scalars()
            domain_rows = list(rows)

            if not domain_rows:
                return {
                    "items": [],
                    "total": total,
                    "limit": safe_limit,
                    "offset": safe_offset,
                    "next_offset": None,
                    "prev_offset": None,
                }

            domain_ids = [item.id for item in domain_rows]
            latest_order_rows = session.execute(
                select(RegistrationOrderModel.domain_id, RegistrationOrderModel.status, RegistrationOrderModel.created_at)
                .where(RegistrationOrderModel.domain_id.in_(domain_ids))
                .order_by(desc(RegistrationOrderModel.created_at))
            ).all()
            latest_order_map: dict[uuid.UUID, tuple[str, datetime] | None] = {}
            for domain_id, order_status, created_at in latest_order_rows:
                if domain_id in latest_order_map:
                    continue
                latest_order_map[domain_id] = (order_status.value, created_at)

            items: list[dict] = []
            for domain in domain_rows:
                latest_order = latest_order_map.get(domain.id)
                items.append(
                    {
                        "id": str(domain.id),
                        "fqdn": domain.fqdn,
                        "tld": domain.tld,
                        "score": float(domain.score) if domain.score is not None else None,
                        "current_status": domain.current_status.value,
                        "source": domain.source,
                        "status_checked_at": domain.status_checked_at.isoformat() if domain.status_checked_at else None,
                        "drop_time_estimated_at": domain.drop_time_estimated_at.isoformat()
                        if domain.drop_time_estimated_at
                        else None,
                        "updated_at": domain.updated_at.isoformat(),
                        "latest_order_status": latest_order[0] if latest_order else None,
                        "latest_order_created_at": latest_order[1].isoformat() if latest_order else None,
                    }
                )

            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def get_user_order_details(self, telegram_user_id: str, order_id: str) -> dict | None:
        safe_uid = str(telegram_user_id).strip()
        if not safe_uid:
            return None
        try:
            order_uuid = uuid.UUID(str(order_id).strip())
        except ValueError:
            return None

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return None

            row = session.execute(
                select(RegistrationOrderModel, DomainModel)
                .join(DomainModel, DomainModel.id == RegistrationOrderModel.domain_id)
                .where(RegistrationOrderModel.id == order_uuid)
                .limit(1)
            ).first()
            if not row:
                return None
            order, domain = row

            owned = bool(order.requested_by and str(order.requested_by).strip() == safe_uid)
            if not owned and user.telegram_chat_id:
                owned = (
                    session.execute(
                        select(AlertModel.id)
                        .where(AlertModel.domain_id == order.domain_id)
                        .where(AlertModel.telegram_chat_id == user.telegram_chat_id)
                        .limit(1)
                    ).scalar_one_or_none()
                    is not None
                )
            if not owned:
                return None

            status_history_rows = session.execute(
                select(DomainStatusHistoryModel)
                .where(DomainStatusHistoryModel.domain_id == domain.id)
                .order_by(desc(DomainStatusHistoryModel.observed_at))
                .limit(20)
            ).scalars()
            status_history = [
                {
                    "status": item.status.value,
                    "provider": item.provider,
                    "observed_at": item.observed_at.isoformat(),
                }
                for item in status_history_rows
            ]

            bot_events_rows = session.execute(
                select(BotEventModel)
                .where(BotEventModel.user_id == user.id)
                .where(
                    or_(
                        func.lower(func.cast(BotEventModel.payload, Text)).contains(str(order.id).lower()),
                        func.lower(func.cast(BotEventModel.payload, Text)).contains(domain.fqdn.lower()),
                    )
                )
                .order_by(desc(BotEventModel.created_at))
                .limit(20)
            ).scalars()
            events = [
                {
                    "id": str(event.id),
                    "event_type": event.event_type,
                    "payload": event.payload or {},
                    "created_at": event.created_at.isoformat(),
                }
                for event in bot_events_rows
            ]

            return {
                "id": str(order.id),
                "domain_id": str(domain.id),
                "domain": domain.fqdn,
                "status": order.status.value,
                "requested_by": order.requested_by,
                "request_payload": order.request_payload or {},
                "response_payload": order.response_payload or {},
                "error_message": order.error_message,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                "completed_at": order.completed_at.isoformat() if order.completed_at else None,
                "domain_snapshot": {
                    "current_status": domain.current_status.value,
                    "score": float(domain.score) if domain.score is not None else None,
                    "drop_time_estimated_at": domain.drop_time_estimated_at.isoformat()
                    if domain.drop_time_estimated_at
                    else None,
                    "updated_at": domain.updated_at.isoformat(),
                },
                "domain_status_history": status_history,
                "events": events,
            }

    def get_user_domain_details(self, telegram_user_id: str, domain_id: str) -> dict | None:
        safe_uid = str(telegram_user_id).strip()
        if not safe_uid:
            return None
        try:
            domain_uuid = uuid.UUID(str(domain_id).strip())
        except ValueError:
            return None

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return None

            domain = session.execute(select(DomainModel).where(DomainModel.id == domain_uuid).limit(1)).scalar_one_or_none()
            if not domain:
                return None

            owned_by_order = (
                session.execute(
                    select(RegistrationOrderModel.id)
                    .where(RegistrationOrderModel.domain_id == domain.id)
                    .where(RegistrationOrderModel.requested_by == safe_uid)
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            )
            owned_by_alert = False
            if user.telegram_chat_id:
                owned_by_alert = (
                    session.execute(
                        select(AlertModel.id)
                        .where(AlertModel.domain_id == domain.id)
                        .where(AlertModel.telegram_chat_id == user.telegram_chat_id)
                        .limit(1)
                    ).scalar_one_or_none()
                    is not None
                )
            if not (owned_by_order or owned_by_alert):
                return None

            history_rows = session.execute(
                select(DomainStatusHistoryModel)
                .where(DomainStatusHistoryModel.domain_id == domain.id)
                .order_by(desc(DomainStatusHistoryModel.observed_at))
                .limit(30)
            ).scalars()
            status_history = [
                {
                    "id": str(item.id),
                    "status": item.status.value,
                    "provider": item.provider,
                    "raw_payload": item.raw_payload or {},
                    "observed_at": item.observed_at.isoformat(),
                }
                for item in history_rows
            ]

            order_rows = session.execute(
                select(RegistrationOrderModel)
                .where(RegistrationOrderModel.domain_id == domain.id)
                .where(or_(RegistrationOrderModel.requested_by == safe_uid, RegistrationOrderModel.requested_by.is_(None)))
                .order_by(desc(RegistrationOrderModel.created_at))
                .limit(30)
            ).scalars()
            orders = [
                {
                    "id": str(item.id),
                    "status": item.status.value,
                    "requested_by": item.requested_by,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                }
                for item in order_rows
            ]

            return {
                "id": str(domain.id),
                "fqdn": domain.fqdn,
                "sld": domain.sld,
                "tld": domain.tld,
                "score": float(domain.score) if domain.score is not None else None,
                "source": domain.source,
                "current_status": domain.current_status.value,
                "status_checked_at": domain.status_checked_at.isoformat() if domain.status_checked_at else None,
                "drop_time_estimated_at": domain.drop_time_estimated_at.isoformat() if domain.drop_time_estimated_at else None,
                "created_at": domain.created_at.isoformat(),
                "updated_at": domain.updated_at.isoformat(),
                "status_history": status_history,
                "orders": orders,
            }

    def get_latest_order_by_domain(self, domain: str) -> RegistrationOrder | None:
        with self._session() as session:
            row = session.execute(
                select(RegistrationOrderModel, DomainModel)
                .join(DomainModel, DomainModel.id == RegistrationOrderModel.domain_id)
                .where(DomainModel.fqdn == domain.strip().lower())
                .order_by(RegistrationOrderModel.created_at.desc())
                .limit(1)
            ).first()
            if not row:
                return None
            order, domain_model = row
            return RegistrationOrder(
                order_id=str(order.id),
                domain=domain_model.fqdn,
                status=order.status.value,
                created_at=order.created_at,
            )

    def get_order(self, order_id: str) -> RegistrationOrder | None:
        with self._session() as session:
            try:
                order_uuid = uuid.UUID(order_id)
            except ValueError:
                return None

            row = session.execute(
                select(RegistrationOrderModel, DomainModel)
                .join(DomainModel, DomainModel.id == RegistrationOrderModel.domain_id)
                .where(RegistrationOrderModel.id == order_uuid)
                .limit(1)
            ).first()
            if not row:
                return None
            order, domain_model = row
            return RegistrationOrder(
                order_id=str(order.id),
                domain=domain_model.fqdn,
                status=order.status.value,
                created_at=order.created_at,
            )

    def set_order_status(
        self,
        order_id: str,
        status: str,
        response_payload: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._session() as session:
            try:
                order_uuid = uuid.UUID(order_id)
            except ValueError:
                return

            order = session.execute(
                select(RegistrationOrderModel).where(RegistrationOrderModel.id == order_uuid).limit(1)
            ).scalar_one_or_none()
            if not order:
                return

            order.status = RegistrationStatus(status)
            if response_payload is not None:
                order.response_payload = response_payload
            if error_message is not None:
                order.error_message = error_message
            order.updated_at = datetime.now(timezone.utc)
            if status in {"registered", "failed", "canceled"}:
                order.completed_at = datetime.now(timezone.utc)
            session.commit()

    def upsert_domain_snapshot(
        self,
        fqdn: str,
        status: str,
        score: float | None,
        drop_time_estimated_at: datetime | None,
        source: str = "monitor",
        provider: str | None = None,
        raw_payload: dict | None = None,
    ) -> None:
        with self._session() as session:
            domain = self._get_or_create_domain(session, fqdn)
            domain.source = source
            domain.score = score
            domain.current_status = self._normalize_domain_status(status)
            domain.status_checked_at = datetime.now(timezone.utc)
            domain.drop_time_estimated_at = drop_time_estimated_at
            domain.updated_at = datetime.now(timezone.utc)

            history = DomainStatusHistoryModel(
                domain_id=domain.id,
                status=domain.current_status,
                provider=provider,
                raw_payload=raw_payload,
            )
            session.add(history)
            session.commit()

    def has_recent_alert(self, fqdn: str, within_minutes: int = 60) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        with self._session() as session:
            row = session.execute(
                select(AlertModel.created_at)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .where(DomainModel.fqdn == fqdn.strip().lower())
                .where(AlertModel.created_at >= threshold)
                .order_by(desc(AlertModel.created_at))
                .limit(1)
            ).scalar_one_or_none()
            return row is not None

    def should_suppress_alert(self, fqdn: str, destination: str, reason: str) -> bool:
        now = datetime.now(timezone.utc)
        with self._session() as session:
            row = session.execute(
                select(AlertSuppressionModel)
                .where(AlertSuppressionModel.fqdn == fqdn.strip().lower())
                .where(AlertSuppressionModel.destination == str(destination))
                .where(AlertSuppressionModel.reason == reason)
                .where(or_(AlertSuppressionModel.expires_at.is_(None), AlertSuppressionModel.expires_at > now))
                .limit(1)
            ).scalar_one_or_none()
            return row is not None

    def suppress_alert(self, fqdn: str, destination: str, reason: str, days: int = 30) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, days))
        with self._session() as session:
            existing = session.execute(
                select(AlertSuppressionModel)
                .where(AlertSuppressionModel.fqdn == fqdn.strip().lower())
                .where(AlertSuppressionModel.destination == str(destination))
                .where(AlertSuppressionModel.reason == reason)
                .limit(1)
            ).scalar_one_or_none()
            if existing:
                existing.expires_at = expires_at
            else:
                session.add(
                    AlertSuppressionModel(
                        fqdn=fqdn.strip().lower(),
                        destination=str(destination),
                        reason=reason,
                        expires_at=expires_at,
                    )
                )
            session.commit()

    def list_user_preferences(self, telegram_user_id: str) -> dict:
        safe_uid = str(telegram_user_id).strip()
        watch_rules = [item for item in self.list_watch_rules(safe_uid) if str(item.get("status") or "") != "deleted"]
        now = datetime.now(timezone.utc)
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return {"watch_rules": [], "suppressions": []}

            destinations = {str(user.telegram_chat_id)} if user.telegram_chat_id else set()
            subscription_targets = session.execute(
                select(UserSubscriptionModel.channel_target).where(UserSubscriptionModel.user_id == user.id)
            ).scalars()
            destinations.update(str(item) for item in subscription_targets if item)
            if not destinations:
                return {"watch_rules": watch_rules, "suppressions": []}

            rows = list(
                session.execute(
                    select(AlertSuppressionModel)
                    .where(AlertSuppressionModel.destination.in_(sorted(destinations)))
                    .where(AlertSuppressionModel.reason.in_(["user_less", "user_never"]))
                    .where(or_(AlertSuppressionModel.expires_at.is_(None), AlertSuppressionModel.expires_at > now))
                    .order_by(desc(AlertSuppressionModel.created_at))
                    .limit(20)
                ).scalars()
            )
            return {
                "watch_rules": watch_rules,
                "suppressions": [
                    {
                        "id": str(row.id),
                        "fqdn": row.fqdn,
                        "reason": row.reason,
                        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                    }
                    for row in rows
                ],
            }

    def delete_alert_suppression(self, telegram_user_id: str, suppression_id: str) -> bool:
        safe_uid = str(telegram_user_id).strip()
        try:
            safe_id = uuid.UUID(str(suppression_id))
        except ValueError:
            return False

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            destinations = {str(user.telegram_chat_id)} if user.telegram_chat_id else set()
            subscription_targets = session.execute(
                select(UserSubscriptionModel.channel_target).where(UserSubscriptionModel.user_id == user.id)
            ).scalars()
            destinations.update(str(item) for item in subscription_targets if item)
            if not destinations:
                return False

            row = session.execute(
                select(AlertSuppressionModel)
                .where(AlertSuppressionModel.id == safe_id)
                .where(AlertSuppressionModel.destination.in_(sorted(destinations)))
                .where(AlertSuppressionModel.reason.in_(["user_less", "user_never"]))
                .limit(1)
            ).scalar_one_or_none()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def record_alert_feedback(
        self,
        token: str,
        telegram_user_id: str,
        feedback_type: str,
        payload: dict | None = None,
    ) -> bool:
        with self._session() as session:
            alert = session.execute(
                select(AlertModel).where(AlertModel.confirmation_token == token).limit(1)
            ).scalar_one_or_none()
            if not alert:
                return False
            session.add(
                AlertFeedbackModel(
                    alert_id=alert.id,
                    telegram_user_id=str(telegram_user_id),
                    feedback_type=feedback_type,
                    payload=payload or {},
                )
            )
            session.commit()
            return True

    def has_recent_alert_for_destination(self, fqdn: str, destination: str, within_minutes: int = 60) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        with self._session() as session:
            row = session.execute(
                select(AlertModel.created_at)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .where(DomainModel.fqdn == fqdn.strip().lower())
                .where(AlertModel.telegram_chat_id == str(destination))
                .where(AlertModel.created_at >= threshold)
                .order_by(desc(AlertModel.created_at))
                .limit(1)
            ).scalar_one_or_none()
            return row is not None

    def count_recent_alerts_for_destination(
        self,
        destination: str,
        within_hours: int = 24,
        alert_type_prefix: str | None = None,
    ) -> int:
        threshold = datetime.now(timezone.utc) - timedelta(hours=max(1, within_hours))
        with self._session() as session:
            query = (
                select(AlertModel.id)
                .where(AlertModel.telegram_chat_id == str(destination))
                .where(AlertModel.created_at >= threshold)
            )
            if alert_type_prefix:
                query = query.where(AlertModel.alert_type.like(f"{alert_type_prefix}%"))
            rows = session.execute(query).all()
            return len(rows)

    def has_recent_alert_for_destination_type(
        self,
        destination: str,
        within_minutes: int = 60,
        alert_type_prefix: str | None = None,
    ) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=max(1, within_minutes))
        with self._session() as session:
            query = (
                select(AlertModel.id)
                .where(AlertModel.telegram_chat_id == str(destination))
                .where(AlertModel.created_at >= threshold)
                .limit(1)
            )
            if alert_type_prefix:
                query = query.where(AlertModel.alert_type.like(f"{alert_type_prefix}%"))
            row = session.execute(query).scalar_one_or_none()
            return row is not None

    def get_user_alert_usage_24h(self, telegram_user_id: str, per_target_daily_limit: int) -> dict:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return {
                    "daily_sent": 0,
                    "daily_remaining_total": 0,
                    "channels": [],
                }

            subs = session.execute(
                select(UserSubscriptionModel)
                .where(UserSubscriptionModel.user_id == user.id)
                .where(UserSubscriptionModel.status == "active")
                .where(UserSubscriptionModel.channel_type.in_(["telegram", "max"]))
            ).scalars()
            subs_list = list(subs)

            channels: list[dict] = []
            daily_sent_total = 0
            for sub in subs_list:
                sent = self.count_recent_alerts_for_destination(
                    destination=sub.channel_target,
                    within_hours=24,
                )
                remaining = max(0, int(per_target_daily_limit) - sent)
                daily_sent_total += sent
                channels.append(
                    {
                        "channel_type": sub.channel_type,
                        "channel_target": sub.channel_target,
                        "daily_sent": sent,
                        "daily_remaining": remaining,
                        "daily_limit": int(per_target_daily_limit),
                    }
                )

            return {
                "daily_sent": daily_sent_total,
                "daily_remaining_total": sum(item["daily_remaining"] for item in channels),
                "channels": channels,
            }

    def list_recent_alerts(self, limit: int = 20) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(AlertModel, DomainModel)
                .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                .order_by(desc(AlertModel.created_at))
                .limit(limit)
            ).all()

            result: list[dict] = []
            for alert, domain in rows:
                result.append(
                    {
                        "kind": "alert",
                        "id": str(alert.id),
                        "domain": domain.fqdn,
                        "status": "acknowledged" if alert.acknowledged else "sent",
                        "alert_type": alert.alert_type,
                        "created_at": alert.created_at.isoformat(),
                    }
                )
            return result

    def list_recent_orders(self, limit: int = 20) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(RegistrationOrderModel, DomainModel)
                .join(DomainModel, DomainModel.id == RegistrationOrderModel.domain_id)
                .order_by(desc(RegistrationOrderModel.created_at))
                .limit(limit)
            ).all()

            result: list[dict] = []
            for order, domain in rows:
                result.append(
                    {
                        "kind": "order",
                        "id": str(order.id),
                        "domain": domain.fqdn,
                        "status": order.status.value,
                        "created_at": order.created_at.isoformat(),
                    }
                )
            return result

    def list_recent_activity(self, limit: int = 20) -> list[dict]:
        alerts = self.list_recent_alerts(limit=limit)
        orders = self.list_recent_orders(limit=limit)
        merged = alerts + orders
        merged.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return merged[:limit]

    def upsert_telegram_user(
        self,
        telegram_user_id: str,
        telegram_chat_id: str | None,
        username: str | None,
        first_name: str | None,
        locale: str | None,
    ) -> TelegramUser:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()

            if not user:
                user = TelegramUserModel(
                    telegram_user_id=str(telegram_user_id),
                    telegram_chat_id=telegram_chat_id,
                    username=username,
                    first_name=first_name,
                    locale=locale,
                    is_active=True,
                )
                session.add(user)
                session.flush()
            else:
                user.telegram_chat_id = telegram_chat_id or user.telegram_chat_id
                user.username = username or user.username
                user.first_name = first_name or user.first_name
                user.locale = locale or user.locale
                user.updated_at = datetime.now(timezone.utc)

            if telegram_chat_id:
                sub = session.execute(
                    select(UserSubscriptionModel)
                    .where(UserSubscriptionModel.user_id == user.id)
                    .where(UserSubscriptionModel.channel_type == "telegram")
                    .where(UserSubscriptionModel.channel_target == str(telegram_chat_id))
                    .limit(1)
                ).scalar_one_or_none()
                if not sub:
                    session.add(
                        UserSubscriptionModel(
                            user_id=user.id,
                            channel_type="telegram",
                            channel_target=str(telegram_chat_id),
                            alert_types={"default": True},
                            status="active",
                        )
                    )

            session.commit()
            return TelegramUser(
                telegram_user_id=user.telegram_user_id,
                telegram_chat_id=user.telegram_chat_id,
                username=user.username,
                first_name=user.first_name,
                locale=user.locale,
                disclaimer_accepted_at=user.disclaimer_accepted_at,
                disclaimer_version=user.disclaimer_version,
            )

    def get_telegram_user(self, telegram_user_id: str) -> TelegramUser | None:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return None
            return TelegramUser(
                telegram_user_id=user.telegram_user_id,
                telegram_chat_id=user.telegram_chat_id,
                username=user.username,
                first_name=user.first_name,
                locale=user.locale,
                disclaimer_accepted_at=user.disclaimer_accepted_at,
                disclaimer_version=user.disclaimer_version,
            )

    def get_telegram_user_id_by_chat_id(self, telegram_chat_id: str) -> str | None:
        safe_chat_id = str(telegram_chat_id).strip()
        if not safe_chat_id:
            return None
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel)
                .where(TelegramUserModel.telegram_chat_id == safe_chat_id)
                .order_by(desc(TelegramUserModel.updated_at))
                .limit(1)
            ).scalar_one_or_none()
            return user.telegram_user_id if user else None

    def ensure_base_roles(self) -> None:
        base_roles = {
            "viewer": "Viewer",
            "viewer_admin": "Viewer Admin",
            "operator": "Operator",
            "manager_admin": "Manager Admin",
            "admin": "Admin",
            "superadmin": "Superadmin",
        }
        with self._session() as session:
            existing_rows = session.execute(select(RoleModel.code, RoleModel.id)).all()
            existing = {str(code): str(role_id) for code, role_id in existing_rows}
            changed = False
            for code, title in base_roles.items():
                if code in existing:
                    continue
                session.add(RoleModel(code=code, title=title))
                changed = True
            if changed:
                session.commit()

    def list_roles(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute(select(RoleModel).order_by(RoleModel.code.asc())).scalars().all()
            return [{"id": str(r.id), "code": r.code, "title": r.title, "created_at": r.created_at.isoformat()} for r in rows]

    def list_user_role_codes(self, telegram_user_id: str) -> list[str]:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel.id).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return []
            rows = session.execute(
                select(RoleModel.code)
                .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
                .where(UserRoleModel.user_id == user)
                .order_by(RoleModel.code.asc())
            ).all()
            return [str(item[0]) for item in rows]

    def has_any_role(self, telegram_user_id: str, role_codes: list[str]) -> bool:
        requested = {str(code).strip().lower() for code in role_codes if str(code).strip()}
        if not requested:
            return False
        roles = {item.lower() for item in self.list_user_role_codes(telegram_user_id)}
        return bool(roles & requested)

    def list_user_permissions(self, telegram_user_id: str) -> list[str]:
        return _permissions_from_roles(self.list_user_role_codes(telegram_user_id))

    def has_permission(self, telegram_user_id: str, permission: str) -> bool:
        target = str(permission).strip().lower()
        if not target:
            return False
        return target in set(self.list_user_permissions(telegram_user_id))

    def list_user_capabilities(self, telegram_user_id: str) -> dict[str, bool]:
        return _capabilities_from_permissions(self.list_user_permissions(telegram_user_id))

    def grant_role(self, telegram_user_id: str, role_code: str, granted_by: str | None = None) -> bool:
        safe_uid = str(telegram_user_id).strip()
        safe_code = str(role_code).strip().lower()
        if not safe_uid or not safe_code:
            return False

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                user = TelegramUserModel(
                    telegram_user_id=safe_uid,
                    telegram_chat_id=None,
                    username=None,
                    first_name=None,
                    locale=None,
                    is_active=True,
                )
                session.add(user)
                session.flush()

            role = session.execute(select(RoleModel).where(RoleModel.code == safe_code).limit(1)).scalar_one_or_none()
            if not role:
                return False

            exists = session.execute(
                select(UserRoleModel.id)
                .where(UserRoleModel.user_id == user.id)
                .where(UserRoleModel.role_id == role.id)
                .limit(1)
            ).scalar_one_or_none()
            if exists:
                return True

            session.add(
                UserRoleModel(
                    user_id=user.id,
                    role_id=role.id,
                    granted_by=granted_by.strip() if granted_by else None,
                )
            )
            session.commit()
            return True

    def revoke_role(self, telegram_user_id: str, role_code: str) -> bool:
        safe_uid = str(telegram_user_id).strip()
        safe_code = str(role_code).strip().lower()
        if not safe_uid or not safe_code:
            return False

        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == safe_uid).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False
            role = session.execute(select(RoleModel).where(RoleModel.code == safe_code).limit(1)).scalar_one_or_none()
            if not role:
                return False

            rows = session.execute(
                select(UserRoleModel)
                .where(UserRoleModel.user_id == user.id)
                .where(UserRoleModel.role_id == role.id)
            ).scalars().all()
            if not rows:
                return False
            for row in rows:
                session.delete(row)
            session.commit()
            return True

    def list_users_with_roles(self, search: str | None = None, limit: int = 100) -> list[dict]:
        safe_limit = max(1, min(500, int(limit)))
        q = (search or "").strip().lower()
        with self._session() as session:
            users = session.execute(
                select(TelegramUserModel).order_by(desc(TelegramUserModel.updated_at)).limit(safe_limit * 2)
            ).scalars().all()

            role_rows = session.execute(
                select(UserRoleModel.user_id, RoleModel.code)
                .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
            ).all()
            role_map: dict[uuid.UUID, list[str]] = {}
            for user_id, code in role_rows:
                role_map.setdefault(user_id, []).append(str(code))

            items: list[dict] = []
            for user in users:
                roles = sorted({item for item in role_map.get(user.id, [])})
                permissions = _permissions_from_roles(roles)
                if q:
                    hay = " ".join(
                        [
                            user.telegram_user_id or "",
                            user.username or "",
                            user.first_name or "",
                            user.telegram_chat_id or "",
                            " ".join(roles),
                        ]
                    ).lower()
                    if q not in hay:
                        continue
                items.append(
                    {
                        "telegram_user_id": user.telegram_user_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "chat_id": user.telegram_chat_id,
                        "is_active": bool(user.is_active),
                        "roles": roles,
                        "permissions": permissions,
                        "capabilities": _capabilities_from_permissions(permissions),
                        "updated_at": user.updated_at.isoformat(),
                    }
                )
                if len(items) >= safe_limit:
                    break
            return items

    def sync_admin_roles_from_env(self, admin_user_ids: list[str], granted_by: str = "system:env_sync") -> int:
        if not admin_user_ids:
            return 0
        changed = 0
        for user_id in {str(item).strip() for item in admin_user_ids if str(item).strip()}:
            ok = self.grant_role(user_id, "admin", granted_by=granted_by)
            if ok:
                changed += 1
        return changed

    def mark_disclaimer_accepted(self, telegram_user_id: str, version: str) -> None:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return
            user.disclaimer_accepted_at = datetime.now(timezone.utc)
            user.disclaimer_version = version
            user.updated_at = datetime.now(timezone.utc)
            session.commit()

    def get_watch_rules_count(self, telegram_user_id: str) -> int:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return 0
            rows = session.execute(
                select(UserWatchRuleModel.id)
                .where(UserWatchRuleModel.user_id == user.id)
                .where(UserWatchRuleModel.status == "active")
            ).all()
            return len(rows)

    def add_watch_rule(
        self,
        telegram_user_id: str,
        watch_query: str,
        tlds: list[str] | None = None,
        min_score: float | None = None,
        max_price_usd: float | None = None,
        max_length: int | None = None,
        daily_alert_limit: int = 3,
    ) -> str | None:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return None

            rule = UserWatchRuleModel(
                user_id=user.id,
                watch_query=watch_query.strip(),
                tlds={"items": _normalize_watch_rule_tlds(tlds)},
                min_score=min_score,
                max_price_usd=max_price_usd,
                max_length=max_length,
                daily_alert_limit=daily_alert_limit,
                status="active",
            )
            session.add(rule)
            session.commit()
            return str(rule.id)

    def list_watch_rules(self, telegram_user_id: str) -> list[dict]:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return []

            rows = list(
                session.execute(
                    select(UserWatchRuleModel)
                    .where(UserWatchRuleModel.user_id == user.id)
                    .order_by(desc(UserWatchRuleModel.created_at))
                ).scalars()
            )
            if not rows:
                return []

            rule_alert_types = {str(r.id): f"watch_rule_match:{r.id}" for r in rows}
            destinations = {str(user.telegram_chat_id)} if user.telegram_chat_id else set()
            subscription_targets = session.execute(
                select(UserSubscriptionModel.channel_target).where(UserSubscriptionModel.user_id == user.id)
            ).scalars()
            destinations.update(str(item) for item in subscription_targets if item)

            count_by_type: dict[str, int] = {}
            latest_by_type: dict[str, dict] = {}
            alert_types = list(rule_alert_types.values())
            if destinations:
                threshold = datetime.now(timezone.utc) - timedelta(hours=24)
                count_rows = session.execute(
                    select(AlertModel.alert_type, func.count(AlertModel.id))
                    .where(AlertModel.alert_type.in_(alert_types))
                    .where(AlertModel.telegram_chat_id.in_(sorted(destinations)))
                    .where(AlertModel.created_at >= threshold)
                    .group_by(AlertModel.alert_type)
                ).all()
                count_by_type = {str(alert_type): int(count) for alert_type, count in count_rows}

                latest_rows = session.execute(
                    select(AlertModel, DomainModel)
                    .join(DomainModel, DomainModel.id == AlertModel.domain_id)
                    .where(AlertModel.alert_type.in_(alert_types))
                    .where(AlertModel.telegram_chat_id.in_(sorted(destinations)))
                    .order_by(desc(AlertModel.created_at))
                ).all()
                for alert, domain in latest_rows:
                    alert_type = str(alert.alert_type)
                    if alert_type in latest_by_type:
                        continue
                    latest_by_type[alert_type] = {
                        "domain": domain.fqdn,
                        "created_at": alert.created_at.isoformat(),
                    }

            return [
                {
                    "id": str(r.id),
                    "query": r.watch_query,
                    "status": r.status,
                    "tlds": (r.tlds or {}).get("items", []),
                    "min_score": float(r.min_score) if r.min_score is not None else None,
                    "max_price_usd": float(r.max_price_usd) if r.max_price_usd is not None else None,
                    "max_length": int(r.max_length) if r.max_length is not None else None,
                    "daily_alert_limit": int(r.daily_alert_limit or 3),
                    "alerts_24h_sent": count_by_type.get(rule_alert_types[str(r.id)], 0),
                    "last_alert_domain": latest_by_type.get(rule_alert_types[str(r.id)], {}).get("domain"),
                    "last_alert_at": latest_by_type.get(rule_alert_types[str(r.id)], {}).get("created_at"),
                }
                for r in rows
            ]

    def list_active_watch_targets(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(UserWatchRuleModel, TelegramUserModel, UserSubscriptionModel)
                .join(TelegramUserModel, TelegramUserModel.id == UserWatchRuleModel.user_id)
                .join(UserSubscriptionModel, UserSubscriptionModel.user_id == TelegramUserModel.id)
                .where(UserWatchRuleModel.status == "active")
                .where(TelegramUserModel.is_active.is_(True))
                .where(TelegramUserModel.disclaimer_accepted_at.is_not(None))
                .where(UserSubscriptionModel.status == "active")
                .where(UserSubscriptionModel.channel_type.in_(["telegram", "max"]))
                .order_by(desc(UserWatchRuleModel.created_at))
            ).all()

            result: list[dict] = []
            for rule, user, sub in rows:
                result.append(
                    {
                        "rule_id": str(rule.id),
                        "telegram_user_id": user.telegram_user_id,
                        "query": rule.watch_query,
                        "tlds": (rule.tlds or {}).get("items", []),
                        "min_score": float(rule.min_score) if rule.min_score is not None else None,
                        "max_price_usd": float(rule.max_price_usd) if rule.max_price_usd is not None else None,
                        "max_length": int(rule.max_length) if rule.max_length is not None else None,
                        "daily_alert_limit": int(rule.daily_alert_limit or 3),
                        "channel_type": sub.channel_type,
                        "channel_target": sub.channel_target,
                    }
                )
            return result

    def list_telegram_chats_by_user_ids(self, telegram_user_ids: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in telegram_user_ids if str(item).strip()]
        if not normalized:
            return []

        with self._session() as session:
            rows = session.execute(
                select(TelegramUserModel.telegram_chat_id)
                .where(TelegramUserModel.telegram_user_id.in_(normalized))
                .where(TelegramUserModel.telegram_chat_id.is_not(None))
                .where(TelegramUserModel.is_active.is_(True))
                .where(TelegramUserModel.disclaimer_accepted_at.is_not(None))
            ).all()
            # Keep deterministic ordering and uniqueness.
            seen: set[str] = set()
            result: list[str] = []
            for row in rows:
                chat_id = str(row[0]).strip()
                if not chat_id or chat_id in seen:
                    continue
                seen.add(chat_id)
                result.append(chat_id)
            return result

    def update_watch_rule(
        self,
        telegram_user_id: str,
        rule_id: str,
        query: str | None = None,
        tlds: list[str] | None = None,
        min_score: float | None = None,
        max_price_usd: float | None = None,
        max_length: int | None = None,
        daily_alert_limit: int | None = None,
        min_score_set: bool = False,
        max_price_usd_set: bool = False,
        max_length_set: bool = False,
        daily_alert_limit_set: bool = False,
    ) -> bool:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            try:
                rule_uuid = uuid.UUID(rule_id)
            except ValueError:
                return False

            rule = session.execute(
                select(UserWatchRuleModel)
                .where(UserWatchRuleModel.id == rule_uuid)
                .where(UserWatchRuleModel.user_id == user.id)
                .limit(1)
            ).scalar_one_or_none()
            if not rule:
                return False

            if query is not None:
                query_clean = query.strip()
                if len(query_clean) < 2:
                    return False
                rule.watch_query = query_clean
            if tlds is not None:
                rule.tlds = {"items": _normalize_watch_rule_tlds(tlds)}
            if min_score_set:
                rule.min_score = min_score
            if max_price_usd_set:
                rule.max_price_usd = max_price_usd
            if max_length_set:
                rule.max_length = max_length
            if daily_alert_limit_set and daily_alert_limit is not None:
                rule.daily_alert_limit = daily_alert_limit

            rule.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def set_watch_rule_status(self, telegram_user_id: str, rule_id: str, status: str) -> bool:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            try:
                rule_uuid = uuid.UUID(rule_id)
            except ValueError:
                return False

            rule = session.execute(
                select(UserWatchRuleModel)
                .where(UserWatchRuleModel.id == rule_uuid)
                .where(UserWatchRuleModel.user_id == user.id)
                .limit(1)
            ).scalar_one_or_none()
            if not rule:
                return False

            rule.status = status
            rule.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def set_telegram_alerts_enabled(
        self,
        telegram_user_id: str,
        telegram_chat_id: str | None,
        enabled: bool,
    ) -> bool:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            subscriptions = session.execute(
                select(UserSubscriptionModel)
                .where(UserSubscriptionModel.user_id == user.id)
                .where(UserSubscriptionModel.channel_type == "telegram")
            ).scalars()
            subscriptions_list = list(subscriptions)

            status = "active" if enabled else "paused"
            if subscriptions_list:
                for sub in subscriptions_list:
                    sub.status = status
                    sub.updated_at = datetime.now(timezone.utc)
            elif telegram_chat_id:
                session.add(
                    UserSubscriptionModel(
                        user_id=user.id,
                        channel_type="telegram",
                        channel_target=str(telegram_chat_id),
                        alert_types={"default": True},
                        status=status,
                    )
                )

            session.commit()
            return True

    def get_telegram_alerts_enabled(self, telegram_user_id: str) -> bool:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            active = session.execute(
                select(UserSubscriptionModel.id)
                .where(UserSubscriptionModel.user_id == user.id)
                .where(UserSubscriptionModel.channel_type == "telegram")
                .where(UserSubscriptionModel.status == "active")
                .limit(1)
            ).scalar_one_or_none()
            return active is not None

    def set_channel_subscription_enabled(
        self,
        telegram_user_id: str,
        channel_type: str,
        channel_target: str | None,
        enabled: bool,
    ) -> bool:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            safe_channel_type = channel_type.strip().lower()
            if safe_channel_type not in {"telegram", "max"}:
                return False

            status = "active" if enabled else "paused"
            subs = session.execute(
                select(UserSubscriptionModel)
                .where(UserSubscriptionModel.user_id == user.id)
                .where(UserSubscriptionModel.channel_type == safe_channel_type)
            ).scalars()
            subs_list = list(subs)

            if subs_list:
                for sub in subs_list:
                    sub.status = status
                    if channel_target:
                        sub.channel_target = str(channel_target)
                    sub.updated_at = datetime.now(timezone.utc)
            elif channel_target:
                session.add(
                    UserSubscriptionModel(
                        user_id=user.id,
                        channel_type=safe_channel_type,
                        channel_target=str(channel_target),
                        alert_types={"default": True},
                        status=status,
                    )
                )
            else:
                return False

            session.commit()
            return True

    def get_channel_alerts_enabled(self, telegram_user_id: str, channel_type: str) -> bool:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return False

            active = session.execute(
                select(UserSubscriptionModel.id)
                .where(UserSubscriptionModel.user_id == user.id)
                .where(UserSubscriptionModel.channel_type == channel_type.strip().lower())
                .where(UserSubscriptionModel.status == "active")
                .limit(1)
            ).scalar_one_or_none()
            return active is not None

    def log_bot_event(
        self,
        event_type: str,
        telegram_user_id: str | None = None,
        telegram_chat_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        with self._session() as session:
            user_id = None
            if telegram_user_id:
                user = session.execute(
                    select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
                ).scalar_one_or_none()
                if user:
                    user_id = user.id

            event = BotEventModel(
                user_id=user_id,
                telegram_chat_id=telegram_chat_id,
                event_type=event_type,
                payload=payload or {},
            )
            session.add(event)
            session.commit()

    def list_telegram_subscriptions(self, telegram_user_id: str) -> list[dict]:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return []

            rows = session.execute(
                select(UserSubscriptionModel)
                .where(UserSubscriptionModel.user_id == user.id)
                .order_by(desc(UserSubscriptionModel.created_at))
            ).scalars()

            return [
                {
                    "id": str(row.id),
                    "channel_type": row.channel_type,
                    "channel_target": row.channel_target,
                    "status": row.status,
                    "alert_types": row.alert_types or {},
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in rows
            ]

    def list_bot_events(self, telegram_user_id: str, limit: int = 50) -> list[dict]:
        with self._session() as session:
            user = session.execute(
                select(TelegramUserModel).where(TelegramUserModel.telegram_user_id == str(telegram_user_id)).limit(1)
            ).scalar_one_or_none()
            if not user:
                return []

            rows = session.execute(
                select(BotEventModel)
                .where(BotEventModel.user_id == user.id)
                .order_by(desc(BotEventModel.created_at))
                .limit(max(1, min(limit, 200)))
            ).scalars()

            return [
                {
                    "id": str(row.id),
                    "event_type": row.event_type,
                    "telegram_chat_id": row.telegram_chat_id,
                    "payload": row.payload or {},
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    def list_bot_events_filtered(
        self,
        telegram_user_id: str,
        limit: int = 50,
        event_type: str | None = None,
        query_text: str | None = None,
    ) -> list[dict]:
        items = self.list_bot_events(telegram_user_id=telegram_user_id, limit=max(1, min(limit, 200)))
        filtered = items

        if event_type:
            target = event_type.strip().lower()
            filtered = [item for item in filtered if str(item.get("event_type", "")).lower() == target]

        if query_text:
            q = query_text.strip().lower()
            filtered = [
                item
                for item in filtered
                if q in str(item.get("event_type", "")).lower() or q in str(item.get("payload", "")).lower()
            ]

        return filtered[: max(1, min(limit, 200))]

    def list_bot_events_page(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
        telegram_user_id: str | None = None,
        telegram_chat_id: str | None = None,
        query_text: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> dict:
        safe_limit = max(1, min(int(limit), 300))
        safe_offset = max(0, int(offset))
        target_event_type = (event_type or "").strip().lower()
        target_uid = (telegram_user_id or "").strip()
        target_chat = (telegram_chat_id or "").strip()
        q = (query_text or "").strip().lower()

        with self._session() as session:
            user = aliased(TelegramUserModel)
            filters = []

            if target_event_type:
                filters.append(func.lower(BotEventModel.event_type) == target_event_type)
            if target_uid:
                filters.append(user.telegram_user_id == target_uid)
            if target_chat:
                filters.append(BotEventModel.telegram_chat_id == target_chat)
            if created_from:
                filters.append(BotEventModel.created_at >= created_from)
            if created_to:
                filters.append(BotEventModel.created_at <= created_to)
            if q:
                filters.append(
                    or_(
                        func.lower(BotEventModel.event_type).contains(q),
                        func.lower(func.cast(BotEventModel.payload, Text)).contains(q),
                        func.lower(func.coalesce(user.telegram_user_id, "")).contains(q),
                        func.lower(func.coalesce(user.username, "")).contains(q),
                        func.lower(func.coalesce(BotEventModel.telegram_chat_id, "")).contains(q),
                    )
                )

            base_query = (
                select(BotEventModel, user.telegram_user_id, user.username)
                .outerjoin(user, user.id == BotEventModel.user_id)
            )
            if filters:
                base_query = base_query.where(and_(*filters))

            total_query = (
                select(func.count())
                .select_from(BotEventModel)
                .outerjoin(user, user.id == BotEventModel.user_id)
            )
            if filters:
                total_query = total_query.where(and_(*filters))

            sort_field = str(sort_by or "created_at").strip().lower()
            sort_direction = "asc" if str(sort_dir or "desc").strip().lower() == "asc" else "desc"
            sort_map = {
                "created_at": BotEventModel.created_at,
                "event_type": func.lower(BotEventModel.event_type),
                "telegram_user_id": func.lower(func.coalesce(user.telegram_user_id, "")),
                "username": func.lower(func.coalesce(user.username, "")),
                "telegram_chat_id": func.lower(func.coalesce(BotEventModel.telegram_chat_id, "")),
            }
            sort_expr = sort_map.get(sort_field, BotEventModel.created_at)
            order_expr = asc(sort_expr) if sort_direction == "asc" else desc(sort_expr)

            total = int(session.execute(total_query).scalar() or 0)
            rows = session.execute(
                base_query.order_by(order_expr, desc(BotEventModel.created_at)).offset(safe_offset).limit(safe_limit)
            ).all()

            items: list[dict] = []
            for event, uid_row, username_row in rows:
                items.append(
                    {
                        "id": str(event.id),
                        "event_type": event.event_type,
                        "telegram_user_id": uid_row,
                        "username": username_row,
                        "telegram_chat_id": event.telegram_chat_id,
                        "payload": event.payload or {},
                        "created_at": event.created_at.isoformat(),
                    }
                )

            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def list_users_activity_page(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        permission_contains: str | None = None,
        registered_only: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sort_by: str = "updated_at",
        sort_dir: str = "desc",
    ) -> dict:
        safe_limit = max(1, min(int(limit), 300))
        safe_offset = max(0, int(offset))
        q = (search or "").strip().lower()
        perm_sub = (permission_contains or "").strip().lower()
        login_event_types = {"auth_telegram_login", "max_oauth_login"}

        with self._session() as session:
            filters = []
            if q:
                filters.append(
                    or_(
                        func.lower(TelegramUserModel.telegram_user_id).contains(q),
                        func.lower(func.coalesce(TelegramUserModel.username, "")).contains(q),
                        func.lower(func.coalesce(TelegramUserModel.first_name, "")).contains(q),
                        func.lower(func.coalesce(TelegramUserModel.telegram_chat_id, "")).contains(q),
                    )
                )
            if created_from:
                filters.append(TelegramUserModel.created_at >= created_from)
            if created_to:
                filters.append(TelegramUserModel.created_at <= created_to)
            if registered_only:
                filters.append(
                    or_(
                        TelegramUserModel.disclaimer_accepted_at.is_not(None),
                        exists(
                            select(BotEventModel.id)
                            .where(BotEventModel.user_id == TelegramUserModel.id)
                            .where(func.lower(BotEventModel.event_type).in_(login_event_types))
                        ),
                    )
                )

            base_query = select(TelegramUserModel)
            if filters:
                base_query = base_query.where(and_(*filters))

            total_query = select(func.count()).select_from(TelegramUserModel)
            if filters:
                total_query = total_query.where(and_(*filters))

            sort_field = str(sort_by or "updated_at").strip().lower()
            sort_direction = "asc" if str(sort_dir or "desc").strip().lower() == "asc" else "desc"
            sort_map = {
                "telegram_user_id": TelegramUserModel.telegram_user_id,
                "username": func.lower(func.coalesce(TelegramUserModel.username, "")),
                "created_at": TelegramUserModel.created_at,
                "updated_at": TelegramUserModel.updated_at,
            }
            sort_expr = sort_map.get(sort_field, TelegramUserModel.updated_at)
            order_expr = asc(sort_expr) if sort_direction == "asc" else desc(sort_expr)

            total = int(session.execute(total_query).scalar() or 0)
            users = session.execute(
                base_query.order_by(order_expr, desc(TelegramUserModel.updated_at)).offset(safe_offset).limit(safe_limit * 2)
            ).scalars().all()

            if not users:
                return {
                    "items": [],
                    "total": total,
                    "limit": safe_limit,
                    "offset": safe_offset,
                    "next_offset": None,
                    "prev_offset": None,
                }

            user_ids = [u.id for u in users]
            role_rows = session.execute(
                select(UserRoleModel.user_id, RoleModel.code)
                .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
                .where(UserRoleModel.user_id.in_(user_ids))
            ).all()
            role_map: dict[uuid.UUID, list[str]] = {}
            for user_id, code in role_rows:
                role_map.setdefault(user_id, []).append(str(code))

            event_rows = session.execute(
                select(
                    BotEventModel.user_id,
                    func.count(BotEventModel.id),
                    func.max(BotEventModel.created_at),
                    func.max(
                        case(
                            (func.lower(BotEventModel.event_type).in_(login_event_types), 1),
                            else_=0,
                        )
                    ),
                )
                .where(BotEventModel.user_id.in_(user_ids))
                .group_by(BotEventModel.user_id)
            ).all()
            event_map: dict[uuid.UUID, tuple[int, datetime | None, bool]] = {}
            for uid, count_total, last_at, has_login in event_rows:
                event_map[uid] = (int(count_total or 0), last_at, bool(has_login))

            items: list[dict] = []
            for user in users:
                roles = sorted({item for item in role_map.get(user.id, [])})
                permissions = _permissions_from_roles(roles)
                capabilities = _capabilities_from_permissions(permissions)
                if perm_sub and not any(perm_sub in p.lower() for p in permissions):
                    continue
                events_total, last_event_at, has_login_event = event_map.get(user.id, (0, None, False))
                is_registered = bool(user.disclaimer_accepted_at) or has_login_event
                items.append(
                    {
                        "telegram_user_id": user.telegram_user_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "chat_id": user.telegram_chat_id,
                        "is_active": bool(user.is_active),
                        "roles": roles,
                        "permissions": permissions,
                        "capabilities": capabilities,
                        "is_registered": is_registered,
                        "events_total": events_total,
                        "disclaimer_accepted_at": user.disclaimer_accepted_at.isoformat() if user.disclaimer_accepted_at else None,
                        "created_at": user.created_at.isoformat(),
                        "updated_at": user.updated_at.isoformat(),
                        "last_event_at": last_event_at.isoformat() if last_event_at else None,
                    }
                )
                if len(items) >= safe_limit:
                    break

            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def log_access_event(
        self,
        action: str,
        actor_telegram_user_id: str | None = None,
        target_telegram_user_id: str | None = None,
        role_code: str | None = None,
        payload: dict | None = None,
    ) -> None:
        safe_action = str(action).strip()
        if not safe_action:
            return

        with self._session() as session:
            actor_user_id = None
            target_user_id = None

            if actor_telegram_user_id:
                actor_user = session.execute(
                    select(TelegramUserModel)
                    .where(TelegramUserModel.telegram_user_id == str(actor_telegram_user_id).strip())
                    .limit(1)
                ).scalar_one_or_none()
                if actor_user:
                    actor_user_id = actor_user.id

            if target_telegram_user_id:
                target_user = session.execute(
                    select(TelegramUserModel)
                    .where(TelegramUserModel.telegram_user_id == str(target_telegram_user_id).strip())
                    .limit(1)
                ).scalar_one_or_none()
                if target_user:
                    target_user_id = target_user.id

            session.add(
                AccessEventModel(
                    actor_user_id=actor_user_id,
                    target_user_id=target_user_id,
                    action=safe_action,
                    role_code=str(role_code).strip().lower() if role_code else None,
                    payload=payload or {},
                )
            )
            session.commit()

    def list_access_events(
        self,
        limit: int = 100,
        action: str | None = None,
        actor_telegram_user_id: str | None = None,
        target_telegram_user_id: str | None = None,
        offset: int = 0,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[dict]:
        page = self.list_access_events_page(
            limit=limit,
            offset=offset,
            action=action,
            actor_telegram_user_id=actor_telegram_user_id,
            target_telegram_user_id=target_telegram_user_id,
            created_from=created_from,
            created_to=created_to,
        )
        return page["items"]

    def list_access_events_page(
        self,
        limit: int = 100,
        offset: int = 0,
        action: str | None = None,
        actor_telegram_user_id: str | None = None,
        target_telegram_user_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> dict:
        safe_limit = max(1, min(int(limit), 300))
        safe_offset = max(0, int(offset))
        target_action = (action or "").strip().lower()
        actor_uid = (actor_telegram_user_id or "").strip()
        target_uid = (target_telegram_user_id or "").strip()
        with self._session() as session:
            actor_user = aliased(TelegramUserModel)
            target_user = aliased(TelegramUserModel)

            filters = []
            if target_action:
                filters.append(func.lower(AccessEventModel.action) == target_action)
            if actor_uid:
                filters.append(actor_user.telegram_user_id == actor_uid)
            if target_uid:
                filters.append(target_user.telegram_user_id == target_uid)
            if created_from:
                filters.append(AccessEventModel.created_at >= created_from)
            if created_to:
                filters.append(AccessEventModel.created_at <= created_to)

            base_query = (
                select(AccessEventModel, actor_user.telegram_user_id, target_user.telegram_user_id)
                .outerjoin(actor_user, actor_user.id == AccessEventModel.actor_user_id)
                .outerjoin(target_user, target_user.id == AccessEventModel.target_user_id)
            )
            if filters:
                base_query = base_query.where(and_(*filters))

            total_query = (
                select(func.count())
                .select_from(AccessEventModel)
                .outerjoin(actor_user, actor_user.id == AccessEventModel.actor_user_id)
                .outerjoin(target_user, target_user.id == AccessEventModel.target_user_id)
            )
            if filters:
                total_query = total_query.where(and_(*filters))

            total = int(session.execute(total_query).scalar() or 0)
            rows = session.execute(
                base_query.order_by(desc(AccessEventModel.created_at)).offset(safe_offset).limit(safe_limit)
            ).all()

            items: list[dict] = []
            for event, actor_uid_row, target_uid_row in rows:
                item = {
                    "id": str(event.id),
                    "action": event.action,
                    "role_code": event.role_code,
                    "actor_telegram_user_id": actor_uid_row,
                    "target_telegram_user_id": target_uid_row,
                    "payload": event.payload or {},
                    "created_at": event.created_at.isoformat(),
                }
                items.append(item)
            next_offset = safe_offset + safe_limit if (safe_offset + safe_limit) < total else None
            prev_offset = max(0, safe_offset - safe_limit) if safe_offset > 0 else None
            return {
                "items": items,
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
            }

    def get_admin_dashboard_stats(self) -> dict:
        login_event_types = {"auth_telegram_login", "max_oauth_login"}
        with self._session() as session:
            users_total = int(session.execute(select(func.count()).select_from(TelegramUserModel)).scalar() or 0)
            users_active = int(
                session.execute(
                    select(func.count()).select_from(TelegramUserModel).where(TelegramUserModel.is_active.is_(True))
                ).scalar()
                or 0
            )
            users_registered = int(
                session.execute(
                    select(func.count())
                    .select_from(TelegramUserModel)
                    .where(
                        or_(
                            TelegramUserModel.disclaimer_accepted_at.is_not(None),
                            exists(
                                select(BotEventModel.id)
                                .where(BotEventModel.user_id == TelegramUserModel.id)
                                .where(func.lower(BotEventModel.event_type).in_(login_event_types))
                            ),
                        )
                    )
                ).scalar()
                or 0
            )
            users_with_watch_rules = int(
                session.execute(
                    select(func.count(func.distinct(UserWatchRuleModel.user_id))).select_from(UserWatchRuleModel)
                ).scalar()
                or 0
            )
            watch_rules_total = int(session.execute(select(func.count()).select_from(UserWatchRuleModel)).scalar() or 0)
            watch_rules_active = int(
                session.execute(
                    select(func.count()).select_from(UserWatchRuleModel).where(UserWatchRuleModel.status == "active")
                ).scalar()
                or 0
            )
            domains_total = int(session.execute(select(func.count()).select_from(DomainModel)).scalar() or 0)
            alerts_total = int(session.execute(select(func.count()).select_from(AlertModel)).scalar() or 0)
            registration_orders_total = int(session.execute(select(func.count()).select_from(RegistrationOrderModel)).scalar() or 0)
            bot_events_total = int(session.execute(select(func.count()).select_from(BotEventModel)).scalar() or 0)
            access_events_total = int(session.execute(select(func.count()).select_from(AccessEventModel)).scalar() or 0)
            copilot_events_total = int(session.execute(select(func.count()).select_from(CopilotEventModel)).scalar() or 0)
            conversations_total = int(session.execute(select(func.count()).select_from(ConversationModel)).scalar() or 0)

            registration_status_rows = session.execute(
                select(RegistrationOrderModel.status, func.count())
                .group_by(RegistrationOrderModel.status)
            ).all()
            registration_by_status = {str(status.value if hasattr(status, "value") else status): int(count) for status, count in registration_status_rows}

            # NOTE: shops/products are not part of this service schema yet.
            return {
                "users_total": users_total,
                "users_registered": users_registered,
                "users_active": users_active,
                "users_with_watch_rules": users_with_watch_rules,
                "watch_rules_total": watch_rules_total,
                "watch_rules_active": watch_rules_active,
                "domains_total": domains_total,
                "alerts_total": alerts_total,
                "registration_orders_total": registration_orders_total,
                "registration_orders_by_status": registration_by_status,
                "bot_events_total": bot_events_total,
                "access_events_total": access_events_total,
                "copilot_events_total": copilot_events_total,
                "conversations_total": conversations_total,
                "stores_total": None,
                "products_total": None,
                "ecommerce_orders_total": None,
                "notes": {
                    "stores_total": "not_available_in_this_service",
                    "products_total": "not_available_in_this_service",
                    "ecommerce_orders_total": "not_available_in_this_service",
                },
            }

    def get_alert_quality_metrics(self, days: int = 7) -> dict:
        safe_days = max(1, min(int(days), 90))
        since = datetime.now(timezone.utc) - timedelta(days=safe_days)
        with self._session() as session:
            alerts_total = int(
                session.execute(
                    select(func.count()).select_from(AlertModel).where(AlertModel.created_at >= since)
                ).scalar()
                or 0
            )
            feedback_total = int(
                session.execute(
                    select(func.count()).select_from(AlertFeedbackModel).where(AlertFeedbackModel.created_at >= since)
                ).scalar()
                or 0
            )
            suppressed_total = int(
                session.execute(
                    select(func.count()).select_from(AlertSuppressionModel).where(AlertSuppressionModel.created_at >= since)
                ).scalar()
                or 0
            )
            monitor_rows = session.execute(
                select(BotEventModel.event_type, BotEventModel.payload, BotEventModel.telegram_chat_id, BotEventModel.created_at)
                .where(BotEventModel.created_at >= since)
                .where(
                    or_(
                        func.lower(BotEventModel.event_type).like("monitor_%"),
                        and_(
                            func.lower(BotEventModel.event_type).contains("telegram"),
                            func.lower(BotEventModel.event_type).contains("error"),
                        ),
                    )
                )
            ).all()
            monitor_metrics = summarize_monitor_quality_events(
                [
                    {
                        "event_type": row[0],
                        "payload": row[1] or {},
                        "telegram_chat_id": row[2],
                        "created_at": row[3],
                    }
                    for row in monitor_rows
                ]
            )
            return {
                "days": safe_days,
                "alerts_total": alerts_total,
                "feedback_total": feedback_total,
                "suppressed_total": suppressed_total,
                **monitor_metrics,
            }

    def create_conversation(self, telegram_user_id: str, channel: str = "web") -> str:
        safe_uid = str(telegram_user_id).strip()
        if not safe_uid:
            return ""
        with self._session() as session:
            row = ConversationModel(
                telegram_user_id=safe_uid,
                channel=str(channel).strip() or "web",
                status="active",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return str(row.id)

    def get_conversation(self, conversation_id: str, telegram_user_id: str | None = None) -> dict | None:
        try:
            cid = uuid.UUID(str(conversation_id).strip())
        except ValueError:
            return None
        with self._session() as session:
            row = session.execute(select(ConversationModel).where(ConversationModel.id == cid).limit(1)).scalar_one_or_none()
            if not row:
                return None
            if telegram_user_id and str(row.telegram_user_id).strip() != str(telegram_user_id).strip():
                return None
            return {
                "id": str(row.id),
                "telegram_user_id": row.telegram_user_id,
                "channel": row.channel,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }

    def log_conversation_message(
        self,
        conversation_id: str,
        telegram_user_id: str,
        direction: str,
        message_text: str,
        intent: str | None = None,
        confidence: float | None = None,
        raw_payload: dict | None = None,
    ) -> str:
        safe_uid = str(telegram_user_id).strip()
        safe_text = str(message_text).strip()
        if not safe_uid:
            return ""
        try:
            cid = uuid.UUID(str(conversation_id).strip())
        except ValueError:
            return ""
        with self._session() as session:
            conversation = session.execute(
                select(ConversationModel).where(ConversationModel.id == cid).limit(1)
            ).scalar_one_or_none()
            if not conversation:
                return ""

            item = ConversationMessageModel(
                conversation_id=cid,
                telegram_user_id=safe_uid,
                direction=str(direction).strip().lower() or "assistant",
                message_text=safe_text,
                intent=(str(intent).strip().lower() if intent else None),
                confidence=confidence,
                raw_payload=raw_payload or {},
            )
            session.add(item)
            conversation.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(item)
            return str(item.id)

    def list_conversation_messages(
        self,
        conversation_id: str,
        telegram_user_id: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        try:
            cid = uuid.UUID(str(conversation_id).strip())
        except ValueError:
            return []
        safe_limit = max(1, min(50, int(limit)))
        with self._session() as session:
            conversation = session.execute(
                select(ConversationModel).where(ConversationModel.id == cid).limit(1)
            ).scalar_one_or_none()
            if not conversation:
                return []
            if telegram_user_id and str(conversation.telegram_user_id).strip() != str(telegram_user_id).strip():
                return []

            rows = session.execute(
                select(ConversationMessageModel)
                .where(ConversationMessageModel.conversation_id == cid)
                .order_by(desc(ConversationMessageModel.created_at))
                .limit(safe_limit)
            ).scalars().all()
            items = list(reversed(rows))
            return [
                {
                    "id": str(item.id),
                    "direction": item.direction,
                    "message_text": item.message_text,
                    "intent": item.intent,
                    "confidence": float(item.confidence) if item.confidence is not None else None,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]

    def create_copilot_confirmation(
        self,
        telegram_user_id: str,
        conversation_id: str,
        action_type: str,
        action_payload: dict,
        ttl_minutes: int = 5,
    ) -> dict | None:
        safe_uid = str(telegram_user_id).strip()
        safe_action = str(action_type).strip().lower()
        if not safe_uid or not safe_action:
            return None
        try:
            cid = uuid.UUID(str(conversation_id).strip())
        except ValueError:
            return None

        token = f"cp_{secrets.token_hex(16)}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, ttl_minutes))
        with self._session() as session:
            row = CopilotActionConfirmationModel(
                conversation_id=cid,
                telegram_user_id=safe_uid,
                action_type=safe_action,
                action_payload=action_payload or {},
                status="pending",
                confirmation_token=token,
                expires_at=expires_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": str(row.id),
                "conversation_id": str(row.conversation_id),
                "telegram_user_id": row.telegram_user_id,
                "action_type": row.action_type,
                "action_payload": row.action_payload or {},
                "status": row.status,
                "confirmation_token": row.confirmation_token,
                "expires_at": row.expires_at.isoformat(),
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }

    def get_copilot_confirmation(self, confirmation_token: str, telegram_user_id: str | None = None) -> dict | None:
        token = str(confirmation_token).strip()
        if not token:
            return None
        with self._session() as session:
            row = session.execute(
                select(CopilotActionConfirmationModel)
                .where(CopilotActionConfirmationModel.confirmation_token == token)
                .limit(1)
            ).scalar_one_or_none()
            if not row:
                return None
            if telegram_user_id and str(row.telegram_user_id).strip() != str(telegram_user_id).strip():
                return None
            return {
                "id": str(row.id),
                "conversation_id": str(row.conversation_id),
                "telegram_user_id": row.telegram_user_id,
                "action_type": row.action_type,
                "action_payload": row.action_payload or {},
                "status": row.status,
                "confirmation_token": row.confirmation_token,
                "expires_at": row.expires_at.isoformat(),
                "result_payload": row.result_payload or {},
                "error_message": row.error_message,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }

    def update_copilot_confirmation_status(
        self,
        confirmation_token: str,
        status: str,
        result_payload: dict | None = None,
        error_message: str | None = None,
    ) -> bool:
        token = str(confirmation_token).strip()
        safe_status = str(status).strip().lower()
        if not token or not safe_status:
            return False
        with self._session() as session:
            row = session.execute(
                select(CopilotActionConfirmationModel)
                .where(CopilotActionConfirmationModel.confirmation_token == token)
                .limit(1)
            ).scalar_one_or_none()
            if not row:
                return False
            row.status = safe_status
            row.result_payload = result_payload if result_payload is not None else row.result_payload
            row.error_message = str(error_message).strip() if error_message else None
            row.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def log_copilot_event(
        self,
        event_type: str,
        telegram_user_id: str,
        conversation_id: str | None = None,
        confirmation_token: str | None = None,
        payload: dict | None = None,
    ) -> str:
        safe_event = str(event_type).strip().lower()
        safe_uid = str(telegram_user_id).strip()
        if not safe_event or not safe_uid:
            return ""

        conversation_uuid = None
        confirmation_uuid = None
        with self._session() as session:
            if conversation_id:
                try:
                    conversation_uuid = uuid.UUID(str(conversation_id).strip())
                except ValueError:
                    conversation_uuid = None

            if confirmation_token:
                row = session.execute(
                    select(CopilotActionConfirmationModel.id)
                    .where(CopilotActionConfirmationModel.confirmation_token == str(confirmation_token).strip())
                    .limit(1)
                ).scalar_one_or_none()
                if row:
                    confirmation_uuid = row

            item = CopilotEventModel(
                telegram_user_id=safe_uid,
                conversation_id=conversation_uuid,
                confirmation_id=confirmation_uuid,
                event_type=safe_event,
                payload=payload or {},
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return str(item.id)
