import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import auth as auth_router


def test_auth_me_guest_mode_disabled(monkeypatch) -> None:
    monkeypatch.setattr(auth_router.settings, "web_guest_auth_enabled", False)
    monkeypatch.setattr(auth_router, "_get_current_user", lambda _request: None)
    client = TestClient(app)
    response = client.get("/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False


def test_auth_me_guest_mode_enabled(monkeypatch) -> None:
    monkeypatch.setattr(auth_router.settings, "web_guest_auth_enabled", True)
    monkeypatch.setattr(auth_router.settings, "web_guest_user_id", "13903713")
    monkeypatch.setattr(auth_router.settings, "web_guest_is_admin", True)
    monkeypatch.setattr(auth_router, "_get_current_user", lambda _request: None)
    monkeypatch.setattr(
        auth_router.store,
        "upsert_telegram_user",
        lambda **_kwargs: type("GuestUser", (), {"telegram_user_id": "13903713", "username": None, "first_name": "LK Guest", "locale": "ru"})(),
    )
    monkeypatch.setattr(auth_router.store, "list_user_role_codes", lambda _uid: ["admin"])
    monkeypatch.setattr(auth_router.store, "grant_role", lambda *_args, **_kwargs: True)

    client = TestClient(app)
    response = client.get("/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["telegram_user_id"] == "13903713"
    assert data["user"]["is_admin"] is True
