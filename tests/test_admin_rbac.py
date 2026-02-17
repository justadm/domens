import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers.auth import COOKIE_NAME, _build_session_token


def test_admin_endpoint_requires_auth() -> None:
    client = TestClient(app)
    response = client.get('/v1/admin/roles')
    assert response.status_code == 401


def test_admin_endpoint_allows_admin_session() -> None:
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, _build_session_token('13903713'))
    response = client.get('/v1/admin/roles')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get('items'), list)
    codes = {item.get('code') for item in data['items'] if isinstance(item, dict)}
    assert 'admin' in codes
