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
        "list_access_events_page",
        lambda **kwargs: {
            "total": 1,
            "limit": int(kwargs.get("limit", 10)),
            "offset": int(kwargs.get("offset", 0)),
            "next_offset": None,
            "prev_offset": None,
            "items": [
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
        },
    )

    response = client.get("/v1/admin/access-events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["offset"] == 0
    assert isinstance(data.get("items"), list)
    assert data["items"][0]["action"] == "grant_role"


def test_admin_access_events_forwards_filters(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)

    captured: dict = {}

    def _fake_page(**kwargs):
        captured.update(kwargs)
        return {"total": 0, "limit": 5, "offset": 10, "next_offset": None, "prev_offset": 5, "items": []}

    monkeypatch.setattr(admin_router.store, "list_access_events_page", _fake_page)

    response = client.get(
        "/v1/admin/access-events"
        "?limit=5&offset=10&action=grant_role"
        "&actor_telegram_user_id=13903713&target_telegram_user_id=42"
        "&created_from=2026-02-18T00:00:00Z&created_to=2026-02-18T23:59:59Z"
    )
    assert response.status_code == 200
    assert captured["limit"] == 5
    assert captured["offset"] == 10
    assert captured["action"] == "grant_role"
    assert captured["actor_telegram_user_id"] == "13903713"
    assert captured["target_telegram_user_id"] == "42"
    assert captured["created_from"] is not None
    assert captured["created_to"] is not None


def test_admin_users_activity_returns_items(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(
        admin_router.store,
        "list_users_activity_page",
        lambda **kwargs: {
            "total": 1,
            "limit": int(kwargs.get("limit", 10)),
            "offset": int(kwargs.get("offset", 0)),
            "next_offset": None,
            "prev_offset": None,
            "items": [
                {
                    "telegram_user_id": "42",
                    "is_registered": True,
                    "events_total": 12,
                    "roles": ["operator"],
                    "permissions": ["watch.manage"],
                    "capabilities": {"watch_manage": True},
                    "created_at": "2026-02-18T00:00:00+00:00",
                    "updated_at": "2026-02-18T01:00:00+00:00",
                    "last_event_at": "2026-02-18T01:00:00+00:00",
                }
            ],
        },
    )
    response = client.get("/v1/admin/users-activity?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["telegram_user_id"] == "42"
    assert data["items"][0]["is_registered"] is True


def test_admin_bot_events_forwards_filters(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    captured: dict = {}

    def _fake_page(**kwargs):
        captured.update(kwargs)
        return {"total": 0, "limit": 10, "offset": 5, "next_offset": None, "prev_offset": 0, "items": []}

    monkeypatch.setattr(admin_router.store, "list_bot_events_page", _fake_page)
    response = client.get(
        "/v1/admin/bot-events"
        "?limit=10&offset=5&event_type=incoming_message"
        "&telegram_user_id=13903713&telegram_chat_id=-1001"
        "&search=watch_add"
        "&created_from=2026-02-18T00:00:00Z&created_to=2026-02-18T23:59:59Z"
    )
    assert response.status_code == 200
    assert captured["limit"] == 10
    assert captured["offset"] == 5
    assert captured["event_type"] == "incoming_message"
    assert captured["telegram_user_id"] == "13903713"
    assert captured["telegram_chat_id"] == "-1001"
    assert captured["query_text"] == "watch_add"
    assert captured["created_from"] is not None
    assert captured["created_to"] is not None
