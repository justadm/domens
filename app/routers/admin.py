from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import settings
from app.routers.auth import AuthUserResponse, get_authenticated_user
from app.routers.copilot import get_copilot_runtime_status
from app.services.ecom_stats import fetch_external_ecom_stats
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
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
    prev_offset: int | None = None
    items: list[dict]


class AdminBotEventsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
    prev_offset: int | None = None
    items: list[dict]


class AdminUsersActivityResponse(BaseModel):
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
    prev_offset: int | None = None
    items: list[dict]


class AdminDashboardResponse(BaseModel):
    stats: dict


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
    return store.has_permission(uid, "admin.panel.read")


def _require_admin(request: Request) -> AuthUserResponse:
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    if not _is_admin_uid(user.telegram_user_id):
        raise HTTPException(status_code=403, detail="admin access required")
    return user


def _require_role_manage_permission(actor_telegram_user_id: str, role: str) -> None:
    safe_role = str(role).strip().lower()
    if safe_role in {"admin", "superadmin"}:
        if store.has_permission(actor_telegram_user_id, "admin.roles.manage.elevated"):
            return
        raise HTTPException(status_code=403, detail="only superadmin can manage admin/superadmin roles")
    if store.has_permission(actor_telegram_user_id, "admin.roles.manage.basic"):
        return
    raise HTTPException(status_code=403, detail="admin role manage permission required")


@router.get("/roles", response_model=AdminRolesResponse)
async def list_roles(request: Request) -> AdminRolesResponse:
    _require_admin(request)
    return AdminRolesResponse(items=store.list_roles())


@router.get("/users", response_model=AdminUsersResponse)
async def list_users(request: Request, search: str | None = None, limit: int = 100) -> AdminUsersResponse:
    _require_admin(request)
    return AdminUsersResponse(items=store.list_users_with_roles(search=search, limit=limit))


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def dashboard(request: Request) -> AdminDashboardResponse:
    _require_admin(request)
    stats = store.get_admin_dashboard_stats()
    external = await fetch_external_ecom_stats()
    if external:
        for key in ("stores_total", "products_total", "ecommerce_orders_total"):
            if key in external and external.get(key) is not None:
                stats[key] = external.get(key)
        stats["ecom_source"] = str(settings.ecom_stats_base_url or "")
        if external.get("ecom_error"):
            stats["ecom_error"] = external.get("ecom_error")
        for extra_key, value in external.items():
            if extra_key in {"stores_total", "products_total", "ecommerce_orders_total", "ecom_error"}:
                continue
            stats[f"ecom_{extra_key}"] = value
    return AdminDashboardResponse(stats=stats)


@router.get("/users-activity", response_model=AdminUsersActivityResponse)
async def list_users_activity(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
    permission_contains: str | None = None,
    registered_only: bool = False,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
) -> AdminUsersActivityResponse:
    _require_admin(request)
    page = store.list_users_activity_page(
        limit=limit,
        offset=offset,
        search=search,
        permission_contains=permission_contains,
        registered_only=registered_only,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return AdminUsersActivityResponse(**page)


@router.post("/grant", response_model=RoleAssignResponse)
async def grant_role(payload: RoleAssignRequest, request: Request) -> RoleAssignResponse:
    admin = _require_admin(request)
    uid = payload.telegram_user_id.strip()
    role = payload.role.strip().lower()
    if role not in {"viewer", "viewer_admin", "operator", "manager_admin", "admin", "superadmin"}:
        raise HTTPException(status_code=400, detail="invalid role")
    _require_role_manage_permission(admin.telegram_user_id, role)
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
    if role not in {"viewer", "viewer_admin", "operator", "manager_admin", "admin", "superadmin"}:
        raise HTTPException(status_code=400, detail="invalid role")
    _require_role_manage_permission(admin.telegram_user_id, role)
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
    offset: int = 0,
    action: str | None = None,
    actor_telegram_user_id: str | None = None,
    target_telegram_user_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> AdminAccessEventsResponse:
    _require_admin(request)
    page = store.list_access_events_page(
        limit=limit,
        offset=offset,
        action=action,
        actor_telegram_user_id=actor_telegram_user_id,
        target_telegram_user_id=target_telegram_user_id,
        created_from=created_from,
        created_to=created_to,
    )
    return AdminAccessEventsResponse(**page)


@router.get("/bot-events", response_model=AdminBotEventsResponse)
async def list_bot_events(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    event_type: str | None = None,
    telegram_user_id: str | None = None,
    telegram_chat_id: str | None = None,
    search: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> AdminBotEventsResponse:
    _require_admin(request)
    page = store.list_bot_events_page(
        limit=limit,
        offset=offset,
        event_type=event_type,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        query_text=search,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return AdminBotEventsResponse(**page)


@router.get("/users-activity.csv")
async def export_users_activity_csv(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
    permission_contains: str | None = None,
    registered_only: bool = False,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
) -> Response:
    _require_admin(request)
    page = store.list_users_activity_page(
        limit=limit,
        offset=offset,
        search=search,
        permission_contains=permission_contains,
        registered_only=registered_only,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "telegram_user_id",
            "username",
            "first_name",
            "chat_id",
            "is_registered",
            "events_total",
            "roles",
            "permissions",
            "last_event_at",
            "created_at",
            "updated_at",
        ]
    )
    for item in page.get("items", []):
        writer.writerow(
            [
                item.get("telegram_user_id"),
                item.get("username"),
                item.get("first_name"),
                item.get("chat_id"),
                item.get("is_registered"),
                item.get("events_total"),
                ",".join(item.get("roles", [])),
                ",".join(item.get("permissions", [])),
                item.get("last_event_at"),
                item.get("created_at"),
                item.get("updated_at"),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users_activity.csv"},
    )


@router.get("/bot-events.csv")
async def export_bot_events_csv(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    event_type: str | None = None,
    telegram_user_id: str | None = None,
    telegram_chat_id: str | None = None,
    search: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> Response:
    _require_admin(request)
    page = store.list_bot_events_page(
        limit=limit,
        offset=offset,
        event_type=event_type,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        query_text=search,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "event_type",
            "telegram_user_id",
            "username",
            "telegram_chat_id",
            "payload_json",
        ]
    )
    for item in page.get("items", []):
        writer.writerow(
            [
                item.get("created_at"),
                item.get("event_type"),
                item.get("telegram_user_id"),
                item.get("username"),
                item.get("telegram_chat_id"),
                str(item.get("payload", {})),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=bot_events.csv"},
    )


@router.get("/copilot-runtime", response_model=CopilotRuntimeResponse)
async def copilot_runtime(request: Request) -> CopilotRuntimeResponse:
    _require_admin(request)
    return CopilotRuntimeResponse(status=get_copilot_runtime_status())
