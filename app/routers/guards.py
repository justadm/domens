from fastapi import HTTPException, Request

from app.config import settings
from app.routers.auth import AuthUserResponse, get_authenticated_user
from app.state import store


def _env_admin_ids() -> set[str]:
    return {item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()}


def require_admin_user(request: Request) -> AuthUserResponse:
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    uid = str(user.telegram_user_id).strip()
    if uid in _env_admin_ids() or store.has_permission(uid, "admin.panel.read"):
        return user

    raise HTTPException(status_code=403, detail="admin access required")
