import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import admin as admin_router
from app.routers.auth import AuthUserResponse


def test_admin_endpoint_requires_auth() -> None:
    client = TestClient(app)
    response = client.get('/v1/admin/roles')
    assert response.status_code == 401


def test_admin_endpoint_allows_admin_session(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(
        admin_router.store,
        "list_roles",
        lambda: [
            {"id": "1", "code": "admin", "title": "Admin", "created_at": "2026-02-18T00:00:00+00:00"},
            {"id": "2", "code": "viewer", "title": "Viewer", "created_at": "2026-02-18T00:00:00+00:00"},
        ],
    )
    response = client.get('/v1/admin/roles')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get('items'), list)
    codes = {item.get('code') for item in data['items'] if isinstance(item, dict)}
    assert 'admin' in codes


def test_admin_copilot_runtime(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(
        admin_router,
        "get_copilot_runtime_status",
        lambda: {"llm_enabled": True, "provider": "ollama", "model": "qwen2.5:0.5b"},
    )
    response = client.get('/v1/admin/copilot-runtime')
    assert response.status_code == 200
    data = response.json()
    assert data["status"]["provider"] == "ollama"


def test_admin_cannot_grant_superadmin(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(admin_router.store, "has_permission", lambda _uid, _perm: False)
    monkeypatch.setattr(admin_router.store, "grant_role", lambda *_args, **_kwargs: True)

    response = client.post(
        "/v1/admin/grant",
        json={"telegram_user_id": "42", "role": "superadmin"},
    )
    assert response.status_code == 403


def test_superadmin_can_grant_admin(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["superadmin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(admin_router.store, "has_permission", lambda _uid, _perm: True)
    monkeypatch.setattr(admin_router.store, "grant_role", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(admin_router.store, "log_bot_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin_router.store, "log_access_event", lambda *args, **kwargs: None)

    response = client.post(
        "/v1/admin/grant",
        json={"telegram_user_id": "42", "role": "admin"},
    )
    assert response.status_code == 200


def test_manager_admin_role_is_valid_for_grant(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["superadmin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(admin_router.store, "has_permission", lambda _uid, _perm: True)
    monkeypatch.setattr(admin_router.store, "grant_role", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(admin_router.store, "log_bot_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin_router.store, "log_access_event", lambda *args, **kwargs: None)

    response = client.post(
        "/v1/admin/grant",
        json={"telegram_user_id": "42", "role": "manager_admin"},
    )
    assert response.status_code == 200


def test_role_manage_requires_basic_permission_for_non_elevated(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)

    def _fake_has_permission(_uid: str, perm: str) -> bool:
        return perm == "admin.panel.read"

    monkeypatch.setattr(admin_router.store, "has_permission", _fake_has_permission)
    monkeypatch.setattr(admin_router.store, "grant_role", lambda *_args, **_kwargs: True)

    response = client.post(
        "/v1/admin/grant",
        json={"telegram_user_id": "42", "role": "operator"},
    )
    assert response.status_code == 403
