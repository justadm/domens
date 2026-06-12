import uuid
import os
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import registrations


def test_execute_registration_blocked_when_disabled(monkeypatch) -> None:
    order_id = str(uuid.uuid4())
    fake_order = SimpleNamespace(order_id=order_id, domain='example.com', status='queued')

    monkeypatch.setattr(registrations.settings, 'registration_enabled', False)
    monkeypatch.setattr(
        registrations,
        'store',
        SimpleNamespace(get_order=lambda oid: fake_order if oid == order_id else None),
    )

    client = TestClient(app)
    response = client.post(f'/v1/registrations/{order_id}/execute')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'blocked'
    assert body['registrar_response']['result'] == 'blocked_by_config'


def test_execute_registration_fails_on_unavailable_precheck(monkeypatch) -> None:
    order_id = str(uuid.uuid4())
    fake_order = SimpleNamespace(order_id=order_id, domain='example.com', status='queued')
    state = {'status': None}

    monkeypatch.setattr(registrations.settings, 'registration_enabled', True)
    monkeypatch.setattr(registrations.settings, 'registration_require_available_check', True)
    monkeypatch.setattr(
        registrations,
        'store',
        SimpleNamespace(
            get_order=lambda oid: fake_order if oid == order_id else None,
            set_order_status=lambda oid, status, **kwargs: state.update({"status": status, "payload": kwargs}),
        ),
    )
    async def fake_check_availability(domain: str) -> dict:
        return {'available': False, 'status': 'registered'}

    async def fake_register_domain(domain: str) -> dict:
        return {'result': 'registered', 'provider': 'timeweb'}

    monkeypatch.setattr(
        registrations,
        'registrar_client',
        SimpleNamespace(
            check_availability=fake_check_availability,
            register_domain=fake_register_domain,
        ),
    )

    client = TestClient(app)
    response = client.post(f'/v1/registrations/{order_id}/execute')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert body['registrar_response']['result'] == 'precheck_unavailable'
    assert state['status'] == 'failed'
    assert state['payload']['response_payload']['availability_check']['available'] is False


def test_execute_registration_blocks_unknown_availability(monkeypatch) -> None:
    order_id = str(uuid.uuid4())
    fake_order = SimpleNamespace(order_id=order_id, domain='example.com', status='queued')
    state = {'status': None, 'payload': None}

    monkeypatch.setattr(registrations.settings, 'registration_enabled', True)
    monkeypatch.setattr(registrations.settings, 'registration_require_available_check', True)
    monkeypatch.setattr(
        registrations,
        'store',
        SimpleNamespace(
            get_order=lambda oid: fake_order if oid == order_id else None,
            set_order_status=lambda oid, status, **kwargs: state.update({"status": status, "payload": kwargs}),
        ),
    )

    async def fake_check_availability(domain: str) -> dict:
        return {'provider': 'timeweb', 'available': None, 'status': 'unknown'}

    monkeypatch.setattr(
        registrations,
        'registrar_client',
        SimpleNamespace(check_availability=fake_check_availability),
    )

    client = TestClient(app)
    response = client.post(f'/v1/registrations/{order_id}/execute')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert body['registrar_response']['result'] == 'precheck_unavailable'
    assert body['registrar_response']['availability_check']['available'] is None
    assert state['status'] == 'failed'
    assert state['payload']['error_message'] == 'fresh availability check failed'
