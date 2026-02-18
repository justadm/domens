from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.routers.auth import AuthUserResponse, get_authenticated_user
from app.routers.copilot import get_copilot_runtime_status
from app.state import store

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class RoleAssignRequest(BaseModel):
    telegram_user_id: str
    role: str


class AdminUsersResponse(BaseModel):
    items: list[dict]


class AdminRolesResponse(BaseModel):
    items: list[dict]


class AdminAccessEventsResponse(BaseModel):
    items: list[dict]


class RoleAssignResponse(BaseModel):
    ok: bool
    telegram_user_id: str
    role: str


class CopilotRuntimeResponse(BaseModel):
    status: dict


def _env_admin_ids() -> set[str]:
    return {item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()}


def _is_admin_uid(telegram_user_id: str) -> bool:
    uid = str(telegram_user_id).strip()
    if not uid:
        return False
    if uid in _env_admin_ids():
        return True
    return store.has_any_role(uid, ["admin", "superadmin"])


def _require_admin(request: Request) -> AuthUserResponse:
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    if not _is_admin_uid(user.telegram_user_id):
        raise HTTPException(status_code=403, detail="admin access required")
    return user


@router.get("/roles", response_model=AdminRolesResponse)
async def list_roles(request: Request) -> AdminRolesResponse:
    _require_admin(request)
    return AdminRolesResponse(items=store.list_roles())


@router.get("/users", response_model=AdminUsersResponse)
async def list_users(request: Request, search: str | None = None, limit: int = 100) -> AdminUsersResponse:
    _require_admin(request)
    return AdminUsersResponse(items=store.list_users_with_roles(search=search, limit=limit))


@router.post("/grant", response_model=RoleAssignResponse)
async def grant_role(payload: RoleAssignRequest, request: Request) -> RoleAssignResponse:
    admin = _require_admin(request)
    uid = payload.telegram_user_id.strip()
    role = payload.role.strip().lower()
    if role not in {"viewer", "operator", "admin", "superadmin"}:
        raise HTTPException(status_code=400, detail="invalid role")
    ok = store.grant_role(uid, role, granted_by=f"admin:{admin.telegram_user_id}")
    if not ok:
        raise HTTPException(status_code=400, detail="failed to grant role")
    store.log_bot_event(
        "admin_grant_role",
        telegram_user_id=admin.telegram_user_id,
        payload={"target": uid, "role": role},
    )
    store.log_access_event(
        action="grant_role",
        actor_telegram_user_id=admin.telegram_user_id,
        target_telegram_user_id=uid,
        role_code=role,
        payload={"source": "api"},
    )
    return RoleAssignResponse(ok=True, telegram_user_id=uid, role=role)


@router.post("/revoke", response_model=RoleAssignResponse)
async def revoke_role(payload: RoleAssignRequest, request: Request) -> RoleAssignResponse:
    admin = _require_admin(request)
    uid = payload.telegram_user_id.strip()
    role = payload.role.strip().lower()
    if role not in {"viewer", "operator", "admin", "superadmin"}:
        raise HTTPException(status_code=400, detail="invalid role")
    ok = store.revoke_role(uid, role)
    if not ok:
        raise HTTPException(status_code=404, detail="role assignment not found")
    store.log_bot_event(
        "admin_revoke_role",
        telegram_user_id=admin.telegram_user_id,
        payload={"target": uid, "role": role},
    )
    store.log_access_event(
        action="revoke_role",
        actor_telegram_user_id=admin.telegram_user_id,
        target_telegram_user_id=uid,
        role_code=role,
        payload={"source": "api"},
    )
    return RoleAssignResponse(ok=True, telegram_user_id=uid, role=role)


@router.get("/access-events", response_model=AdminAccessEventsResponse)
async def list_access_events(
    request: Request,
    limit: int = 100,
    action: str | None = None,
    actor_telegram_user_id: str | None = None,
    target_telegram_user_id: str | None = None,
) -> AdminAccessEventsResponse:
    _require_admin(request)
    return AdminAccessEventsResponse(
        items=store.list_access_events(
            limit=limit,
            action=action,
            actor_telegram_user_id=actor_telegram_user_id,
            target_telegram_user_id=target_telegram_user_id,
        )
    )


@router.get("/copilot-runtime", response_model=CopilotRuntimeResponse)
async def copilot_runtime(request: Request) -> CopilotRuntimeResponse:
    _require_admin(request)
    return CopilotRuntimeResponse(status=get_copilot_runtime_status())
