from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.routers.auth import AuthUserResponse, get_authenticated_user
from app.state import store

router = APIRouter(prefix="/v1/cabinet", tags=["cabinet"])


class TelegramSubscriptionToggleRequest(BaseModel):
    enabled: bool
    chat_id: str | None = None


class WatchRuleCreateRequest(BaseModel):
    query: str = Field(min_length=2, max_length=256)
    tlds: list[str] = Field(default_factory=list)
    min_score: float | None = None
    max_price_usd: float | None = None


class WatchRuleStatusRequest(BaseModel):
    status: str


class CabinetProfileResponse(BaseModel):
    telegram_user_id: str
    username: str | None = None
    first_name: str | None = None
    locale: str | None = None
    chat_id: str | None = None
    disclaimer_accepted_at: str | None = None
    disclaimer_version: str | None = None
    alerts_enabled: bool
    watch_rules_active: int


class CabinetSubscriptionsResponse(BaseModel):
    items: list[dict]


class CabinetWatchRulesResponse(BaseModel):
    items: list[dict]


class CabinetHistoryResponse(BaseModel):
    items: list[dict]


def _require_user(request: Request) -> AuthUserResponse:
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


@router.get("/profile", response_model=CabinetProfileResponse)
async def cabinet_profile(request: Request) -> CabinetProfileResponse:
    auth_user = _require_user(request)
    user = store.get_telegram_user(auth_user.telegram_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="profile not found")

    return CabinetProfileResponse(
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=user.first_name,
        locale=user.locale,
        chat_id=user.telegram_chat_id,
        disclaimer_accepted_at=user.disclaimer_accepted_at.isoformat() if user.disclaimer_accepted_at else None,
        disclaimer_version=user.disclaimer_version,
        alerts_enabled=store.get_telegram_alerts_enabled(user.telegram_user_id),
        watch_rules_active=store.get_watch_rules_count(user.telegram_user_id),
    )


@router.get("/subscriptions", response_model=CabinetSubscriptionsResponse)
async def cabinet_subscriptions(request: Request) -> CabinetSubscriptionsResponse:
    auth_user = _require_user(request)
    return CabinetSubscriptionsResponse(items=store.list_telegram_subscriptions(auth_user.telegram_user_id))


@router.post("/subscriptions/telegram", response_model=CabinetSubscriptionsResponse)
async def cabinet_subscriptions_telegram_toggle(
    payload: TelegramSubscriptionToggleRequest,
    request: Request,
) -> CabinetSubscriptionsResponse:
    auth_user = _require_user(request)
    user = store.get_telegram_user(auth_user.telegram_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="profile not found")

    chat_id = payload.chat_id or user.telegram_chat_id
    ok = store.set_telegram_alerts_enabled(
        telegram_user_id=auth_user.telegram_user_id,
        telegram_chat_id=chat_id,
        enabled=payload.enabled,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="failed to update subscriptions")

    store.log_bot_event(
        "cabinet_alerts_toggle",
        telegram_user_id=auth_user.telegram_user_id,
        telegram_chat_id=chat_id,
        payload={"enabled": payload.enabled},
    )

    return CabinetSubscriptionsResponse(items=store.list_telegram_subscriptions(auth_user.telegram_user_id))


@router.get("/watch-rules", response_model=CabinetWatchRulesResponse)
async def cabinet_watch_rules(request: Request) -> CabinetWatchRulesResponse:
    auth_user = _require_user(request)
    return CabinetWatchRulesResponse(items=store.list_watch_rules(auth_user.telegram_user_id))


@router.post("/watch-rules", response_model=CabinetWatchRulesResponse)
async def cabinet_watch_rule_create(payload: WatchRuleCreateRequest, request: Request) -> CabinetWatchRulesResponse:
    auth_user = _require_user(request)
    rule_id = store.add_watch_rule(
        telegram_user_id=auth_user.telegram_user_id,
        watch_query=payload.query.strip(),
        tlds=payload.tlds,
        min_score=payload.min_score,
        max_price_usd=payload.max_price_usd,
    )
    if not rule_id:
        raise HTTPException(status_code=400, detail="failed to create watch rule")

    store.log_bot_event(
        "cabinet_watch_add",
        telegram_user_id=auth_user.telegram_user_id,
        payload={"rule_id": rule_id, "query": payload.query.strip()},
    )

    return CabinetWatchRulesResponse(items=store.list_watch_rules(auth_user.telegram_user_id))


@router.post("/watch-rules/{rule_id}/status", response_model=CabinetWatchRulesResponse)
async def cabinet_watch_rule_status(
    rule_id: str,
    payload: WatchRuleStatusRequest,
    request: Request,
) -> CabinetWatchRulesResponse:
    auth_user = _require_user(request)
    status = payload.status.strip().lower()
    if status not in {"active", "paused", "deleted"}:
        raise HTTPException(status_code=400, detail="invalid status")

    ok = store.set_watch_rule_status(auth_user.telegram_user_id, rule_id, status)
    if not ok:
        raise HTTPException(status_code=404, detail="watch rule not found")

    store.log_bot_event(
        "cabinet_watch_status",
        telegram_user_id=auth_user.telegram_user_id,
        payload={"rule_id": rule_id, "status": status},
    )

    return CabinetWatchRulesResponse(items=store.list_watch_rules(auth_user.telegram_user_id))


@router.get("/history", response_model=CabinetHistoryResponse)
async def cabinet_history(request: Request, limit: int = 40) -> CabinetHistoryResponse:
    auth_user = _require_user(request)
    return CabinetHistoryResponse(items=store.list_bot_events(auth_user.telegram_user_id, limit=limit))
