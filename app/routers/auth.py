from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.state import store

router = APIRouter(prefix="/v1/auth", tags=["auth"])

COOKIE_NAME = "domens_session"
TELEGRAM_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60
_max_oauth_states: dict[str, int] = {}


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
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    is_admin: bool = False


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: AuthUserResponse | None = None


class TelegramWidgetConfigResponse(BaseModel):
    enabled: bool
    bot_username: str | None = None


class MaxOauthConfigResponse(BaseModel):
    enabled: bool
    label: str = "MAX"


class MaxOauthLoginUrlResponse(BaseModel):
    enabled: bool
    url: str | None = None


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

    roles = store.list_user_role_codes(user.telegram_user_id)
    permissions = store.list_user_permissions(user.telegram_user_id)
    capabilities = store.list_user_capabilities(user.telegram_user_id)
    env_admins = {item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()}
    is_admin = bool(capabilities.get("admin_panel_read")) or user.telegram_user_id in env_admins
    return AuthUserResponse(
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=user.first_name,
        locale=user.locale,
        roles=roles,
        permissions=permissions,
        capabilities=capabilities,
        is_admin=is_admin,
    )


def _get_guest_user() -> AuthUserResponse | None:
    if not settings.web_guest_auth_enabled:
        return None
    guest_uid = str(settings.web_guest_user_id or "").strip()
    if not guest_uid:
        return None

    user = store.upsert_telegram_user(
        telegram_user_id=guest_uid,
        telegram_chat_id=None,
        username=None,
        first_name="LK Guest",
        locale="ru",
    )
    roles = store.list_user_role_codes(user.telegram_user_id)
    if settings.web_guest_is_admin:
        if "admin" not in roles and "superadmin" not in roles:
            store.grant_role(user.telegram_user_id, "admin", granted_by="web_guest_auth")
            roles = store.list_user_role_codes(user.telegram_user_id)

    permissions = store.list_user_permissions(user.telegram_user_id)
    capabilities = store.list_user_capabilities(user.telegram_user_id)
    env_admins = {item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()}
    is_admin = settings.web_guest_is_admin or bool(capabilities.get("admin_panel_read")) or user.telegram_user_id in env_admins
    return AuthUserResponse(
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=user.first_name,
        locale=user.locale,
        roles=roles,
        permissions=permissions,
        capabilities=capabilities,
        is_admin=is_admin,
    )


def _is_max_oauth_configured() -> bool:
    return bool(
        settings.max_oauth_enabled
        and settings.max_oauth_authorize_url
        and settings.max_oauth_token_url
        and settings.max_oauth_userinfo_url
        and settings.max_oauth_client_id
        and settings.max_oauth_client_secret
        and settings.max_oauth_redirect_uri
    )


def _cleanup_max_states(now_ts: int) -> None:
    expired = [key for key, exp in _max_oauth_states.items() if exp <= now_ts]
    for key in expired:
        _max_oauth_states.pop(key, None)


def get_authenticated_user(request: Request) -> AuthUserResponse | None:
    user = _get_current_user(request)
    if user:
        return user
    return _get_guest_user()


@router.get("/telegram/widget-config", response_model=TelegramWidgetConfigResponse)
async def telegram_widget_config() -> TelegramWidgetConfigResponse:
    enabled = bool(settings.telegram_bot_username and settings.telegram_bot_token)
    return TelegramWidgetConfigResponse(
        enabled=enabled,
        bot_username=settings.telegram_bot_username if enabled else None,
    )


@router.get("/max/config", response_model=MaxOauthConfigResponse)
async def max_oauth_config() -> MaxOauthConfigResponse:
    return MaxOauthConfigResponse(enabled=_is_max_oauth_configured())


@router.get("/max/login-url", response_model=MaxOauthLoginUrlResponse)
async def max_oauth_login_url() -> MaxOauthLoginUrlResponse:
    if not _is_max_oauth_configured():
        return MaxOauthLoginUrlResponse(enabled=False, url=None)

    now_ts = int(time.time())
    _cleanup_max_states(now_ts)
    state = secrets.token_urlsafe(24)
    _max_oauth_states[state] = now_ts + max(60, settings.max_oauth_state_ttl_seconds)

    params = {
        "response_type": "code",
        "client_id": settings.max_oauth_client_id,
        "redirect_uri": settings.max_oauth_redirect_uri,
        "scope": settings.max_oauth_scope,
        "state": state,
    }
    url = f"{settings.max_oauth_authorize_url}?{urlencode(params)}"
    return MaxOauthLoginUrlResponse(enabled=True, url=url)


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
    store.log_bot_event("auth_telegram_login", telegram_user_id=user.telegram_user_id, payload={"provider": "telegram"})

    return AuthSessionResponse(
        authenticated=True,
        user=AuthUserResponse(
            telegram_user_id=user.telegram_user_id,
            username=user.username,
            first_name=user.first_name,
            locale=user.locale,
            roles=store.list_user_role_codes(user.telegram_user_id),
            permissions=store.list_user_permissions(user.telegram_user_id),
            capabilities=store.list_user_capabilities(user.telegram_user_id),
            is_admin=bool(store.has_permission(user.telegram_user_id, "admin.panel.read"))
            or bool(user.telegram_user_id in {item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()}),
        ),
    )


@router.get("/max/callback")
async def max_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"max oauth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code/state")
    if not _is_max_oauth_configured():
        raise HTTPException(status_code=400, detail="max oauth not configured")

    now_ts = int(time.time())
    _cleanup_max_states(now_ts)
    state_exp = _max_oauth_states.pop(state, None)
    if not state_exp or state_exp <= now_ts:
        raise HTTPException(status_code=400, detail="invalid oauth state")

    async with httpx.AsyncClient(timeout=12.0) as client:
        token_resp = await client.post(
            settings.max_oauth_token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.max_oauth_client_id,
                "client_secret": settings.max_oauth_client_secret,
                "redirect_uri": settings.max_oauth_redirect_uri,
            },
        )
        if token_resp.status_code >= 400:
            raise HTTPException(status_code=401, detail="max oauth token exchange failed")
        token_data = token_resp.json() if token_resp.content else {}
        access_token = str(token_data.get("access_token") or "")
        if not access_token:
            raise HTTPException(status_code=401, detail="max oauth access token missing")

        userinfo_resp = await client.get(
            settings.max_oauth_userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code >= 400:
            raise HTTPException(status_code=401, detail="max oauth userinfo failed")
        profile = userinfo_resp.json() if userinfo_resp.content else {}

    user_id = str(profile.get("id") or profile.get("user_id") or profile.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="max oauth user id missing")
    username = str(profile.get("username") or profile.get("login") or "").strip() or None
    first_name = str(profile.get("first_name") or profile.get("name") or "").strip() or None
    locale = str(profile.get("locale") or profile.get("language") or "").strip() or None

    user = store.upsert_telegram_user(
        telegram_user_id=f"max:{user_id}",
        telegram_chat_id=None,
        username=username,
        first_name=first_name,
        locale=locale,
    )
    store.log_bot_event("max_oauth_login", telegram_user_id=user.telegram_user_id, payload={"provider": "max"})

    token = _build_session_token(user.telegram_user_id)
    redirect = RedirectResponse(url="/?auth=max_ok", status_code=302)
    redirect.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max(60, settings.auth_jwt_ttl_seconds),
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        path="/",
    )
    return redirect


@router.get("/me", response_model=AuthSessionResponse)
async def auth_me(request: Request) -> AuthSessionResponse:
    user = get_authenticated_user(request)
    if not user:
        return AuthSessionResponse(authenticated=False)
    store.log_bot_event("auth_web_me", telegram_user_id=user.telegram_user_id, payload={"channel": "web"})
    return AuthSessionResponse(authenticated=True, user=user)


@router.post("/logout", response_model=AuthSessionResponse)
async def auth_logout(response: Response) -> AuthSessionResponse:
    response.delete_cookie(COOKIE_NAME, path="/")
    return AuthSessionResponse(authenticated=False)
