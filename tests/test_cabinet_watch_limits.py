from fastapi.testclient import TestClient

from app.main import app
from app.routers import cabinet as cabinet_router
from app.routers.auth import AuthUserResponse


def test_watch_rule_limits_are_clamped(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        cabinet_router,
        "_require_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["operator"], is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "add_watch_rule",
        lambda **kwargs: captured.update(kwargs) or "rule-1",
    )
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(cabinet_router.store, "list_watch_rules", lambda _uid: [])

    client = TestClient(app)
    response = client.post(
        "/v1/cabinet/watch-rules",
        json={"query": "ai tools", "daily_alert_limit": 99, "max_length": 100},
    )

    assert response.status_code == 200
    assert captured["daily_alert_limit"] == 10
    assert captured["max_length"] == 30


def test_watch_rule_update_allows_clearing_max_length(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        cabinet_router,
        "_require_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["operator"], is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "update_watch_rule",
        lambda **kwargs: captured.update(kwargs) or True,
    )
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(cabinet_router.store, "list_watch_rules", lambda _uid: [])

    client = TestClient(app)
    response = client.patch(
        "/v1/cabinet/watch-rules/00000000-0000-0000-0000-000000000001",
        json={"daily_alert_limit": 0, "max_length": None},
    )

    assert response.status_code == 200
    assert captured["daily_alert_limit"] == 1
    assert captured["max_length"] is None
    assert captured["max_length_set"] is True
