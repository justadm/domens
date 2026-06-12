from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ready_returns_runtime_flags(monkeypatch) -> None:
    monkeypatch.setattr("app.main.store.ping", lambda: True)

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] is True
    assert "telegram_configured" in data
    assert "monitoring_enabled" in data
    assert "registration_enabled" in data


def test_ready_degrades_when_database_ping_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.main.store.ping", lambda: False)

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] is False
