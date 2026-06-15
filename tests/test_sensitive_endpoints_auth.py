import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import alerts as alerts_router
from app.routers import auth as auth_router


def test_operational_endpoints_require_auth() -> None:
    client = TestClient(app)

    cases = [
        ("post", "/v1/alerts/trigger", {"domain": "example.com", "telegram_chat_id": "13903713"}),
        ("post", "/v1/domains/check", {"domains": ["example.com"]}),
        ("post", "/v1/domains/candidates", {"candidates": ["example.com"]}),
        ("post", "/v1/monitoring/run-once", None),
    ]

    for method, path, json_body in cases:
        response = getattr(client, method)(path, json=json_body)
        assert response.status_code == 401, path


def test_operational_endpoints_do_not_accept_guest_admin(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(auth_router.settings, "web_guest_auth_enabled", True)
    monkeypatch.setattr(auth_router.settings, "web_guest_user_id", "guest")
    monkeypatch.setattr(auth_router.settings, "web_guest_is_admin", True)
    monkeypatch.setattr(alerts_router, "send_telegram_alert", lambda *_args, **_kwargs: None)

    response = client.post(
        "/v1/alerts/trigger",
        json={"domain": "example.com", "telegram_chat_id": "13903713"},
    )

    assert response.status_code == 401
