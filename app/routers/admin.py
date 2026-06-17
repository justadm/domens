from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.auth import AuthUserResponse, _get_current_user as get_real_session_user
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


class FeedbackRatiosResponse(BaseModel):
    more: int = 0
    less: int = 0
    never: int = 0
    why: int = 0
    positive_rate: float = 0.0
    negative_rate: float = 0.0
    total: int = 0


class AdminQualityResponse(BaseModel):
    days: int
    alerts_total: int
    feedback_total: int
    suppressed_total: int
    feedback_ratios: FeedbackRatiosResponse = Field(default_factory=FeedbackRatiosResponse)
    monitor_runs_total: int = 0
    monitor_alerts_sent: int = 0
    monitor_digests_sent: int = 0
    monitor_checked_total: int = 0
    monitor_skip_reasons: dict[str, int] = Field(default_factory=dict)
    monitor_duplicate_alert_groups: list[dict] = Field(default_factory=list)
    monitor_duplicate_alert_groups_total: int = 0
    telegram_errors_total: int = 0
    registration_enabled: bool = False
    monitor_enabled: bool = False
    monitor_watchlist_only: bool = True
    monitor_admin_fanout_enabled: bool = False
    monitor_alert_target_cooldown_minutes: int = 0


def _build_admin_quality_metrics(days: int) -> dict:
    metrics = store.get_alert_quality_metrics(days=days)
    metrics.update(
        {
            "registration_enabled": bool(settings.registration_enabled),
            "monitor_enabled": bool(settings.monitor_enabled),
            "monitor_watchlist_only": bool(settings.monitor_watchlist_only),
            "monitor_admin_fanout_enabled": bool(settings.monitor_admin_fanout_enabled),
            "monitor_alert_target_cooldown_minutes": int(settings.monitor_alert_target_cooldown_minutes),
        }
    )
    return metrics


def _format_report_rate(value: float | int | None) -> str:
    return f"{float(value or 0) * 100:.1f}%"


def _markdown_cell(value) -> str:
    return str(value if value is not None else "-").replace("|", "\\|").replace("\n", " ")


def _format_admin_quality_report(metrics: dict, generated_at: datetime) -> str:
    feedback = metrics.get("feedback_ratios") or {}
    duplicate_groups = metrics.get("monitor_duplicate_alert_groups") or []
    skip_reasons = metrics.get("monitor_skip_reasons") or {}

    lines = [
        "# Domens Admin Quality Report",
        "",
        f"Window days: {int(metrics.get('days') or 0)}",
        f"generated_at: {generated_at.isoformat()}",
        "",
        "## Safety flags",
        f"- registration_enabled: {bool(metrics.get('registration_enabled'))}",
        f"- monitor_enabled: {bool(metrics.get('monitor_enabled'))}",
        f"- monitor_watchlist_only: {bool(metrics.get('monitor_watchlist_only'))}",
        f"- monitor_admin_fanout_enabled: {bool(metrics.get('monitor_admin_fanout_enabled'))}",
        f"- monitor_digest_enabled: {bool(settings.monitor_digest_enabled)}",
        f"- monitor_alert_target_cooldown_minutes: {int(metrics.get('monitor_alert_target_cooldown_minutes') or 0)}",
        "",
        "## Totals",
        f"- alerts_total: {int(metrics.get('alerts_total') or 0)}",
        f"- feedback_total: {int(metrics.get('feedback_total') or 0)}",
        f"- suppressed_total: {int(metrics.get('suppressed_total') or 0)}",
        f"- monitor_runs_total: {int(metrics.get('monitor_runs_total') or 0)}",
        f"- monitor_checked_total: {int(metrics.get('monitor_checked_total') or 0)}",
        f"- monitor_alerts_sent: {int(metrics.get('monitor_alerts_sent') or 0)}",
        f"- monitor_digests_sent: {int(metrics.get('monitor_digests_sent') or 0)}",
        "",
        "## Feedback distribution",
        "feedback_ratios:",
        f"- more: {int(feedback.get('more') or 0)}",
        f"- less: {int(feedback.get('less') or 0)}",
        f"- never: {int(feedback.get('never') or 0)}",
        f"- why: {int(feedback.get('why') or 0)}",
        f"- positive_rate: {_format_report_rate(feedback.get('positive_rate'))}",
        f"- negative_rate: {_format_report_rate(feedback.get('negative_rate'))}",
        f"- total: {int(feedback.get('total') or 0)}",
        "",
        "## Duplicate groups",
        "| destination | fqdn | count | first_sent_at | last_sent_at |",
        "| --- | --- | ---: | --- | --- |",
    ]
    if duplicate_groups:
        for item in duplicate_groups:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(item.get("destination")),
                        _markdown_cell(item.get("fqdn")),
                        _markdown_cell(item.get("count")),
                        _markdown_cell(item.get("first_sent_at")),
                        _markdown_cell(item.get("last_sent_at")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | 0 | - | - |")

    lines.extend(
        [
            "",
            "## Skip reasons",
        ]
    )
    if skip_reasons:
        for reason, count in sorted(skip_reasons.items()):
            lines.append(f"- {_markdown_cell(reason)}: {int(count or 0)}")
    else:
        lines.append("- none: 0")

    lines.extend(
        [
            "",
            "## Telegram errors",
            f"- telegram_errors_total: {int(metrics.get('telegram_errors_total') or 0)}",
            "",
            "## Go/no-go notes",
            "- reviewer:",
            "- go_no_go_decision:",
            "- evidence_link:",
            "- follow_up:",
            "",
        ]
    )
    return "\n".join(lines)


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
    user = get_real_session_user(request)
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


@router.get("/quality", response_model=AdminQualityResponse)
async def admin_quality(request: Request, days: int = 7) -> AdminQualityResponse:
    _require_admin(request)
    metrics = _build_admin_quality_metrics(days=days)
    return AdminQualityResponse(**metrics)


@router.get("/quality-report.md")
async def admin_quality_report(request: Request, days: int = 7) -> Response:
    _require_admin(request)
    generated_at = datetime.now(timezone.utc)
    metrics = _build_admin_quality_metrics(days=days)
    content = _format_admin_quality_report(metrics, generated_at=generated_at)
    filename = f"domens-quality-report-{generated_at.date().isoformat()}.md"
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
