from datetime import datetime
from pydantic import BaseModel, Field


class DomainCheckRequest(BaseModel):
    domains: list[str] = Field(default_factory=list)
    source: str = "manual"


class DomainCheckResult(BaseModel):
    domain: str
    status: str
    score: float
    drop_time_estimated_at: datetime | None = None


class DomainCheckResponse(BaseModel):
    results: list[DomainCheckResult]


class CandidateIngestRequest(BaseModel):
    candidates: list[str] = Field(default_factory=list)
    watchlist_id: str | None = None


class CandidateIngestResponse(BaseModel):
    accepted: int


class TriggerAlertRequest(BaseModel):
    domain: str
    telegram_chat_id: str
    watchlist_id: str | None = None


class TriggerAlertResponse(BaseModel):
    alert_id: str
    confirmation_token: str
    status: str


class ConfirmRegistrationRequest(BaseModel):
    confirmation_token: str
    confirmed_by: str


class ConfirmRegistrationResponse(BaseModel):
    order_id: str
    domain: str
    status: str


class ExecuteRegistrationResponse(BaseModel):
    order_id: str
    status: str
    registrar_response: dict


class TelegramWebhookRequest(BaseModel):
    callback_data: str | None = None
    from_user: str | None = None
    callback_query: dict | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str
    database: bool
    telegram_configured: bool
    monitoring_enabled: bool
    registration_enabled: bool
