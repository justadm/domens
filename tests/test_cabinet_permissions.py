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


def test_cabinet_domains_page(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "list_user_domains_page",
        lambda **_kwargs: {
            "total": 1,
            "limit": 50,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [{"id": "d1", "fqdn": "example.ru", "current_status": "available"}],
        },
    )

    response = client.get("/v1/cabinet/domains?limit=50&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["fqdn"] == "example.ru"


def test_cabinet_orders_page(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "list_user_registration_orders_page",
        lambda **_kwargs: {
            "total": 1,
            "limit": 50,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [{"id": "o1", "domain": "example.ru", "status": "queued"}],
        },
    )

    response = client.get("/v1/cabinet/orders?limit=50&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "example.ru"


def test_cabinet_alerts_page_includes_explanation_and_feedback(monkeypatch) -> None:
    client = TestClient(app)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )

    def _fake_list_user_alerts_page(**kwargs):
        captured.update(kwargs)
        return {
            "total": 1,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [
                {
                    "id": "a1",
                    "domain_id": "d1",
                    "domain": "stackai.ru",
                    "alert_type": "watch_rule_match:r1",
                    "channel": "telegram",
                    "channel_target": "13903713",
                    "acknowledged": False,
                    "created_at": "2026-06-13T09:00:00+00:00",
                    "acknowledged_at": None,
                    "explanation": {
                        "score": 88.4,
                        "status": "available",
                        "provider": "timeweb",
                        "matched_query": "stack ai",
                        "tld": "ru",
                        "length": 7,
                        "risk": "provider_checked",
                    },
                    "latest_feedback": {
                        "type": "more",
                        "created_at": "2026-06-13T09:05:00+00:00",
                    },
                    "feedback_counts": {"more": 1},
                    "suppression_state": None,
                }
            ],
        }

    monkeypatch.setattr(cabinet_router.store, "list_user_alerts_page", _fake_list_user_alerts_page)

    response = client.get("/v1/cabinet/alerts?limit=20&offset=0&search=stack&feedback=more")
    assert response.status_code == 200
    data = response.json()
    assert captured == {
        "telegram_user_id": "13903713",
        "limit": 20,
        "offset": 0,
        "search": "stack",
        "feedback": "more",
        "domains": [],
    }
    assert data["items"][0]["domain"] == "stackai.ru"
    assert data["items"][0]["explanation"]["score"] == 88.4
    assert data["items"][0]["latest_feedback"]["type"] == "more"
    assert "suppression_state" in data["items"][0]
    assert "confirmation_token" not in data["items"][0]


def test_cabinet_alerts_page_filters_by_digest_domains(monkeypatch) -> None:
    client = TestClient(app)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )

    def _fake_list_user_alerts_page(**kwargs):
        captured.update(kwargs)
        return {
            "total": 2,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [],
        }

    monkeypatch.setattr(cabinet_router.store, "list_user_alerts_page", _fake_list_user_alerts_page)

    response = client.get(
        "/v1/cabinet/alerts?limit=20&offset=0&domains=assistlab.io,catchhub.ru,stackai.ru"
    )

    assert response.status_code == 200
    assert captured["domains"] == ["assistlab.io", "catchhub.ru", "stackai.ru"]


def test_cabinet_alerts_rejects_guest_fallback(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="guest", is_admin=False),
    )
    monkeypatch.setattr(cabinet_router, "get_real_session_user", lambda _request: None)
    monkeypatch.setattr(
        cabinet_router.store,
        "list_user_alerts_page",
        lambda **_kwargs: {
            "total": 0,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [],
        },
    )

    response = client.get("/v1/cabinet/alerts?limit=20")

    assert response.status_code == 401


def test_cabinet_digests_page_includes_delivery_payload(monkeypatch) -> None:
    client = TestClient(app)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )

    def _fake_list_user_digests_page(**kwargs):
        captured.update(kwargs)
        return {
            "total": 1,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [
                {
                    "id": "e1",
                    "channel": "telegram",
                    "channel_target": "13903713",
                    "created_at": "2026-06-16T06:13:00+00:00",
                    "domains": ["assistlab.io"],
                    "items_count": 1,
                    "message_id": "614",
                    "delivery": {"mode": "telegram", "message_id": "614", "items_count": 1},
                }
            ],
        }

    monkeypatch.setattr(cabinet_router.store, "list_user_digests_page", _fake_list_user_digests_page)

    response = client.get("/v1/cabinet/digests?limit=20&offset=0&search=assist")

    assert response.status_code == 200
    data = response.json()
    assert captured == {
        "telegram_user_id": "13903713",
        "limit": 20,
        "offset": 0,
        "search": "assist",
    }
    assert data["items"][0]["domains"] == ["assistlab.io"]
    assert data["items"][0]["message_id"] == "614"


def test_cabinet_digests_rejects_guest_fallback(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="guest", is_admin=False),
    )
    monkeypatch.setattr(cabinet_router, "get_real_session_user", lambda _request: None)
    monkeypatch.setattr(
        cabinet_router.store,
        "list_user_digests_page",
        lambda **_kwargs: {
            "total": 0,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
            "items": [],
        },
        raising=False,
    )

    response = client.get("/v1/cabinet/digests?limit=20")

    assert response.status_code == 401


def test_cabinet_alert_feedback_records_choice_and_never_suppresses(monkeypatch) -> None:
    client = TestClient(app)
    recorded: dict[str, object] = {}
    suppressions: list[tuple[str, str, str, int]] = []
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )

    monkeypatch.setattr(
        cabinet_router.store,
        "record_user_alert_feedback",
        lambda alert_id, telegram_user_id, feedback_type, payload=None: recorded.update(
            {
                "alert_id": alert_id,
                "telegram_user_id": telegram_user_id,
                "feedback_type": feedback_type,
                "payload": payload,
            }
        )
        or {
            "alert_id": alert_id,
            "domain": "stackai.ru",
            "channel_target": "13903713",
            "feedback": {"type": feedback_type, "created_at": "2026-06-13T09:05:00+00:00"},
        },
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "suppress_alert",
        lambda fqdn, destination, reason, days=30: suppressions.append((fqdn, destination, reason, days)),
    )
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *_args, **_kwargs: None)

    response = client.post("/v1/cabinet/alerts/a1/feedback", json={"feedback_type": "never"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["feedback"]["type"] == "never"
    assert recorded["alert_id"] == "a1"
    assert recorded["telegram_user_id"] == "13903713"
    assert recorded["feedback_type"] == "never"
    assert suppressions == [("stackai.ru", "13903713", "user_never", 365)]


def test_cabinet_alert_feedback_rejects_guest_fallback(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="guest", is_admin=False),
    )
    monkeypatch.setattr(cabinet_router, "get_real_session_user", lambda _request: None)
    monkeypatch.setattr(cabinet_router.store, "record_user_alert_feedback", lambda **_kwargs: None)

    response = client.post("/v1/cabinet/alerts/a1/feedback", json={"feedback_type": "less"})

    assert response.status_code == 401


def test_cabinet_alert_feedback_less_adds_medium_suppression(monkeypatch) -> None:
    client = TestClient(app)
    recorded: dict[str, object] = {}
    suppressions: list[tuple[str, str, str, int]] = []
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )

    monkeypatch.setattr(
        cabinet_router.store,
        "record_user_alert_feedback",
        lambda alert_id, telegram_user_id, feedback_type, payload=None: recorded.update(
            {
                "alert_id": alert_id,
                "telegram_user_id": telegram_user_id,
                "feedback_type": feedback_type,
                "payload": payload,
            }
        )
        or {
            "alert_id": alert_id,
            "domain": "stackai.ru",
            "channel_target": "13903713",
            "feedback": {"type": feedback_type, "created_at": "2026-06-13T09:05:00+00:00"},
        },
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "suppress_alert",
        lambda fqdn, destination, reason, days=30: suppressions.append((fqdn, destination, reason, days)),
    )
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *_args, **_kwargs: None)

    response = client.post("/v1/cabinet/alerts/a1/feedback", json={"feedback_type": "less"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert recorded["feedback_type"] == "less"
    assert suppressions == [("stackai.ru", "13903713", "user_less", 90)]


def test_cabinet_alert_feedback_more_adds_quiet_watch_rule(monkeypatch) -> None:
    client = TestClient(app)
    recorded: dict[str, object] = {}
    added: list[dict] = []
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )

    monkeypatch.setattr(
        cabinet_router.store,
        "record_user_alert_feedback",
        lambda alert_id, telegram_user_id, feedback_type, payload=None: recorded.update(
            {
                "alert_id": alert_id,
                "telegram_user_id": telegram_user_id,
                "feedback_type": feedback_type,
                "payload": payload,
            }
        )
        or {
            "alert_id": alert_id,
            "domain": "stackai.ru",
            "channel_target": "13903713",
            "explanation": {"matched_query": "ai tools", "tld": "ru"},
            "feedback": {"type": feedback_type, "created_at": "2026-06-13T09:05:00+00:00"},
        },
    )
    monkeypatch.setattr(cabinet_router.store, "list_watch_rules", lambda _user_id: [])
    monkeypatch.setattr(
        cabinet_router.store,
        "add_watch_rule",
        lambda telegram_user_id, watch_query, **kwargs: added.append(
            {"telegram_user_id": telegram_user_id, "watch_query": watch_query, **kwargs}
        )
        or "rule-1",
    )
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *_args, **_kwargs: None)

    response = client.post("/v1/cabinet/alerts/a1/feedback", json={"feedback_type": "more"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert recorded["feedback_type"] == "more"
    assert added == [
        {
            "telegram_user_id": "13903713",
            "watch_query": "ai tools",
            "tlds": [".ru"],
            "daily_alert_limit": 1,
        }
    ]


def test_cabinet_preferences_returns_watch_rules_and_suppressions(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "list_user_preferences",
        lambda _uid: {
            "watch_rules": [{"id": "r1", "query": "ai tools", "status": "active"}],
            "suppressions": [
                {
                    "id": "s1",
                    "fqdn": "stackai.ru",
                    "reason": "user_never",
                    "expires_at": "2027-06-13T09:05:00+00:00",
                }
            ],
        },
    )

    response = client.get("/v1/cabinet/preferences")

    assert response.status_code == 200
    data = response.json()
    assert data["watch_rules"][0]["query"] == "ai tools"
    assert data["suppressions"][0]["fqdn"] == "stackai.ru"


def test_cabinet_preferences_rejects_guest_fallback(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(cabinet_router.settings, "web_guest_auth_enabled", True)
    monkeypatch.setattr(cabinet_router.settings, "web_guest_user_id", "13903713")
    monkeypatch.setattr(cabinet_router.settings, "web_guest_is_admin", False)

    response = client.get("/v1/cabinet/preferences")

    assert response.status_code == 401


def test_cabinet_preferences_delete_suppression(monkeypatch) -> None:
    client = TestClient(app)
    deleted: list[tuple[str, str]] = []
    events: list[dict] = []
    monkeypatch.setattr(
        cabinet_router,
        "get_real_session_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "delete_alert_suppression",
        lambda telegram_user_id, suppression_id: deleted.append((telegram_user_id, suppression_id)) or True,
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "log_bot_event",
        lambda event, **kwargs: events.append({"event": event, **kwargs}),
    )

    response = client.delete("/v1/cabinet/preferences/suppressions/s1")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "suppression_id": "s1"}
    assert deleted == [("13903713", "s1")]
    assert events[0]["event"] == "cabinet_suppression_delete"


def test_cabinet_domain_details(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "get_user_domain_details",
        lambda _uid, _id: {"id": "d1", "fqdn": "example.ru"},
    )

    response = client.get("/v1/cabinet/domains/d1")
    assert response.status_code == 200
    assert response.json()["item"]["fqdn"] == "example.ru"


def test_cabinet_order_details(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "get_user_order_details",
        lambda _uid, _id: {"id": "o1", "status": "queued"},
    )

    response = client.get("/v1/cabinet/orders/o1")
    assert response.status_code == 200
    assert response.json()["item"]["id"] == "o1"


def test_cabinet_order_cancel(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "get_user_order_details",
        lambda _uid, _id: {"id": "o1", "status": "queued"},
    )
    monkeypatch.setattr(cabinet_router.store, "set_order_status", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *_args, **_kwargs: None)

    response = client.post("/v1/cabinet/orders/o1/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


def test_cabinet_domain_recheck(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "get_user_domain_details",
        lambda _uid, _id: {"id": "d1", "fqdn": "example.ru"},
    )
    async def _fake_infer_status(_domain, timeweb_client=None):
        return ("available", None)

    monkeypatch.setattr(cabinet_router, "infer_status", _fake_infer_status)
    monkeypatch.setattr(cabinet_router, "score_domain", lambda _domain: 77)
    monkeypatch.setattr(cabinet_router.store, "upsert_domain_snapshot", lambda **_kwargs: None)
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *_args, **_kwargs: None)

    response = client.post("/v1/cabinet/domains/d1/recheck")
    assert response.status_code == 200
    assert response.json()["status"] == "available"


def test_cabinet_order_execute(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        cabinet_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=False),
    )
    monkeypatch.setattr(
        cabinet_router.store,
        "get_user_order_details",
        lambda _uid, _id: {"id": "o1", "status": "queued"},
    )
    monkeypatch.setattr(cabinet_router.store, "log_bot_event", lambda *_args, **_kwargs: None)

    async def _fake_execute(_order_id: str):
        return type(
            "R",
            (),
            {"status": "registered", "order_id": "o1", "model_dump": lambda self: {"status": "registered"}},
        )()

    import app.routers.registrations as reg_router

    monkeypatch.setattr(reg_router, "execute_registration", _fake_execute)
    response = client.post("/v1/cabinet/orders/o1/execute")
    assert response.status_code == 200
    assert response.json()["status"] == "registered"
