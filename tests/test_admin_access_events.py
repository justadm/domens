import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import admin as admin_router
from app.routers.auth import AuthUserResponse


def test_admin_access_events_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/v1/admin/access-events")
    assert response.status_code == 401


def test_admin_access_events_returns_items(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)

    monkeypatch.setattr(
        admin_router.store,
        "list_access_events",
        lambda **kwargs: [
            {
                "id": "evt-1",
                "action": "grant_role",
                "role_code": "operator",
                "actor_telegram_user_id": "13903713",
                "target_telegram_user_id": "111",
                "payload": {"source": "api"},
                "created_at": "2026-02-18T00:00:00+00:00",
            }
        ],
    )

    response = client.get("/v1/admin/access-events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("items"), list)
    assert data["items"][0]["action"] == "grant_role"
