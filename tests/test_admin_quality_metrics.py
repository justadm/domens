from fastapi.testclient import TestClient

from app.main import app
from app.routers import admin as admin_router
from app.routers.auth import AuthUserResponse


def test_admin_quality_endpoint_returns_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", roles=["admin"], is_admin=True),
    )
    monkeypatch.setattr(admin_router, "_is_admin_uid", lambda _uid: True)
    monkeypatch.setattr(
        admin_router.store,
        "get_alert_quality_metrics",
        lambda days=7: {
            "days": days,
            "alerts_total": 2,
            "feedback_total": 1,
            "suppressed_total": 3,
        },
    )

    client = TestClient(app)
    response = client.get("/v1/admin/quality?days=7")

    assert response.status_code == 200
    assert response.json() == {
        "days": 7,
        "alerts_total": 2,
        "feedback_total": 1,
        "suppressed_total": 3,
    }
