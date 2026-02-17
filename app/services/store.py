from __future__ import annotations

import uuid
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
    create_engine,
    desc,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, relationship, sessionmaker


Base = declarative_base()


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
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    domain: Mapped[DomainModel] = relationship(back_populates="alerts")


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

    def create_alert(self, domain: str, telegram_chat_id: str, token: str, alert_type: str = "manual_trigger") -> Alert:
        with self._session() as session:
            domain_model = self._get_or_create_domain(session, domain)
            alert = AlertModel(
                domain_id=domain_model.id,
                telegram_chat_id=telegram_chat_id,
                alert_type=alert_type,
                confirmation_token=token,
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

    def create_order(self, domain: str) -> RegistrationOrder:
        with self._session() as session:
            domain_model = self._get_or_create_domain(session, domain)
            order = RegistrationOrderModel(
                domain_id=domain_model.id,
                status=RegistrationStatus.QUEUED,
                request_payload={},
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

    def set_order_status(self, order_id: str, status: str) -> None:
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
                tlds={"items": tlds or []},
                min_score=min_score,
                max_price_usd=max_price_usd,
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

            rows = session.execute(
                select(UserWatchRuleModel)
                .where(UserWatchRuleModel.user_id == user.id)
                .order_by(desc(UserWatchRuleModel.created_at))
            ).scalars()
            return [
                {
                    "id": str(r.id),
                    "query": r.watch_query,
                    "status": r.status,
                    "tlds": (r.tlds or {}).get("items", []),
                    "min_score": float(r.min_score) if r.min_score is not None else None,
                    "max_price_usd": float(r.max_price_usd) if r.max_price_usd is not None else None,
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
                        "channel_type": sub.channel_type,
                        "channel_target": sub.channel_target,
                    }
                )
            return result

    def update_watch_rule(
        self,
        telegram_user_id: str,
        rule_id: str,
        query: str | None = None,
        tlds: list[str] | None = None,
        min_score: float | None = None,
        max_price_usd: float | None = None,
        min_score_set: bool = False,
        max_price_usd_set: bool = False,
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
                rule.tlds = {"items": tlds}
            if min_score_set:
                rule.min_score = min_score
            if max_price_usd_set:
                rule.max_price_usd = max_price_usd

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
