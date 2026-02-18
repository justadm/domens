import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import cabinet as cabinet_router
from app.routers.auth import AuthUserResponse


def test_cabinet_profile_includes_permissions_and_capabilities(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "get_telegram_user",
        lambda _uid: type(
            "U",
            (),
            {
                "telegram_user_id": "13903713",
                "username": "just",
                "first_name": "Just",
                "locale": "ru",
                "telegram_chat_id": "13903713",
                "disclaimer_accepted_at": None,
                "disclaimer_version": "v1",
            },
        )(),
    )
    monkeypatch.setattr(cabinet_router.store, "list_user_role_codes", lambda _uid: ["operator"])
    monkeypatch.setattr(cabinet_router.store, "list_user_permissions", lambda _uid: ["copilot.register_domain", "watch.manage"])
    monkeypatch.setattr(
        cabinet_router.store,
        "list_user_capabilities",
        lambda _uid: {"copilot_register_domain": True, "watch_manage": True, "admin_panel_read": False},
    )
    monkeypatch.setattr(cabinet_router.store, "get_user_alert_usage_24h", lambda *_args, **_kwargs: {"daily_sent": 0, "daily_remaining_total": 10, "channels": []})
    monkeypatch.setattr(cabinet_router.store, "get_telegram_alerts_enabled", lambda _uid: True)
    monkeypatch.setattr(cabinet_router.store, "get_channel_alerts_enabled", lambda _uid, _channel: False)
    monkeypatch.setattr(cabinet_router.store, "get_watch_rules_count", lambda _uid: 3)

    response = client.get("/v1/cabinet/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["roles"] == ["operator"]
    assert "copilot.register_domain" in data["permissions"]
    assert data["capabilities"]["copilot_register_domain"] is True
    assert data["is_admin"] is False

