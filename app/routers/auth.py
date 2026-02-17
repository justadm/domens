from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import settings
from app.state import store

router = APIRouter(prefix="/v1/auth", tags=["auth"])

COOKIE_NAME = "domens_session"
TELEGRAM_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60


class TelegramLoginRequest(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class AuthUserResponse(BaseModel):
    telegram_user_id: str
    username: str | None = None
    first_name: str | None = None
    locale: str | None = None


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: AuthUserResponse | None = None


class TelegramWidgetConfigResponse(BaseModel):
    enabled: bool
    bot_username: str | None = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(raw: str) -> str:
    digest = hmac.new(settings.auth_jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()
    return _b64url_encode(digest)


def _build_session_token(telegram_user_id: str) -> str:
    now = int(time.time())
    exp = now + max(60, settings.auth_jwt_ttl_seconds)
    payload = {
        "uid": str(telegram_user_id),
        "iat": now,
        "exp": exp,
    }
    payload_raw = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_raw)
    return f"{payload_raw}.{signature}"


def _verify_session_token(token: str) -> dict[str, Any] | None:
    try:
        payload_raw, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = _sign(payload_raw)
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_raw).decode())
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        return None

    uid = payload.get("uid")
    if not uid:
        return None

    return payload


def _telegram_data_check_string(data: dict[str, Any]) -> str:
    items: list[str] = []
    for key in sorted(data.keys()):
        if key == "hash":
            continue
        value = data.get(key)
        if value is None:
            continue
        items.append(f"{key}={value}")
    return "\n".join(items)


def _verify_telegram_login(payload: TelegramLoginRequest) -> bool:
    if not settings.telegram_bot_token:
        return False

    data = payload.model_dump()
    data_check_string = _telegram_data_check_string(data)
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, payload.hash):
        return False

    now = int(time.time())
    if now - int(payload.auth_date) > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        return False

    return True


def _cookie_secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "")
    if proto.lower() == "https":
        return True
    return request.url.scheme == "https"


def _get_current_user(request: Request) -> AuthUserResponse | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    payload = _verify_session_token(token)
    if not payload:
        return None

    user = store.get_telegram_user(str(payload["uid"]))
    if not user:
        return None

    return AuthUserResponse(
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=user.first_name,
        locale=user.locale,
    )


@router.get("/telegram/widget-config", response_model=TelegramWidgetConfigResponse)
async def telegram_widget_config() -> TelegramWidgetConfigResponse:
    enabled = bool(settings.telegram_bot_username and settings.telegram_bot_token)
    return TelegramWidgetConfigResponse(
        enabled=enabled,
        bot_username=settings.telegram_bot_username if enabled else None,
    )


@router.post("/telegram/login", response_model=AuthSessionResponse)
async def telegram_login(payload: TelegramLoginRequest, request: Request, response: Response) -> AuthSessionResponse:
    if not _verify_telegram_login(payload):
        raise HTTPException(status_code=401, detail="invalid telegram auth payload")

    user = store.upsert_telegram_user(
        telegram_user_id=str(payload.id),
        telegram_chat_id=None,
        username=payload.username,
        first_name=payload.first_name,
        locale=None,
    )

    token = _build_session_token(user.telegram_user_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max(60, settings.auth_jwt_ttl_seconds),
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        path="/",
    )

    return AuthSessionResponse(
        authenticated=True,
        user=AuthUserResponse(
            telegram_user_id=user.telegram_user_id,
            username=user.username,
            first_name=user.first_name,
            locale=user.locale,
        ),
    )


@router.get("/me", response_model=AuthSessionResponse)
async def auth_me(request: Request) -> AuthSessionResponse:
    user = _get_current_user(request)
    if not user:
        return AuthSessionResponse(authenticated=False)
    return AuthSessionResponse(authenticated=True, user=user)


@router.post("/logout", response_model=AuthSessionResponse)
async def auth_logout(response: Response) -> AuthSessionResponse:
    response.delete_cookie(COOKIE_NAME, path="/")
    return AuthSessionResponse(authenticated=False)
