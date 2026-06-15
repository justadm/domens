import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app


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
