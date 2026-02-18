import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import copilot as copilot_router
from app.routers.auth import AuthUserResponse


def _mock_auth(monkeypatch) -> None:
    monkeypatch.setattr(
        copilot_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=True),
    )


def test_copilot_message_requires_auth(monkeypatch) -> None:
    monkeypatch.setattr(copilot_router, "get_authenticated_user", lambda _request: None)
    client = TestClient(app)
    response = client.post("/v1/copilot/message", json={"message": "hello", "mode": "chat"})
    assert response.status_code == 401


def test_copilot_message_returns_confirmation(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")
    monkeypatch.setattr(
        copilot_router.store,
        "create_copilot_confirmation",
        lambda **_kwargs: {
            "confirmation_token": "cp_test_1",
            "action_type": "create_watch",
            "action_payload": {"query": "ai security", "tlds": [".ai"]},
        },
    )

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/message",
        json={"message": "добавь watch для ai security", "mode": "assistant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["requires_confirmation"] is True
    assert data["confirmation_token"] == "cp_test_1"
    assert data["intent"] == "create_watch"


def test_copilot_confirm_cancel(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(
        copilot_router.store,
        "get_copilot_confirmation",
        lambda *_args, **_kwargs: {
            "status": "pending",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "conversation_id": "conv-1",
            "action_type": "create_watch",
            "action_payload": {"query": "ai"},
        },
    )
    monkeypatch.setattr(copilot_router.store, "update_copilot_confirmation_status", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/confirm",
        json={"confirmation_token": "cp_test_2", "decision": "cancel"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


def test_copilot_confirm_executes_watch(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(
        copilot_router.store,
        "get_copilot_confirmation",
        lambda *_args, **_kwargs: {
            "status": "pending",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "conversation_id": "conv-1",
            "action_type": "create_watch",
            "action_payload": {"query": "ai security", "tlds": [".ai", ".io"]},
        },
    )
    monkeypatch.setattr(copilot_router.store, "add_watch_rule", lambda **_kwargs: "rule-1")
    monkeypatch.setattr(copilot_router.store, "update_copilot_confirmation_status", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/confirm",
        json={"confirmation_token": "cp_test_3", "decision": "confirm"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "executed"
    assert data["execution_result"]["rule_id"] == "rule-1"
