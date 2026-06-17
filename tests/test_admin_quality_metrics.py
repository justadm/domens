import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import admin as admin_router
from app.routers.auth import AuthUserResponse
from app.services.store import build_alert_feedback_ratios, summarize_monitor_quality_events


def test_admin_quality_endpoint_returns_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router,
        "get_real_session_user",
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
            "feedback_ratios": {
                "more": 1,
                "less": 0,
                "never": 0,
                "why": 0,
                "positive_rate": 1.0,
                "negative_rate": 0.0,
                "total": 1,
            },
            "monitor_runs_total": 4,
            "monitor_alerts_sent": 1,
            "monitor_digests_sent": 1,
            "monitor_checked_total": 88,
            "monitor_skip_reasons": {"target_cooldown": 2, "status_not_interesting": 86},
            "monitor_duplicate_alert_groups": [],
            "monitor_duplicate_alert_groups_total": 0,
            "telegram_errors_total": 0,
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
        "feedback_ratios": {
            "more": 1,
            "less": 0,
            "never": 0,
            "why": 0,
            "positive_rate": 1.0,
            "negative_rate": 0.0,
            "total": 1,
        },
        "monitor_runs_total": 4,
        "monitor_alerts_sent": 1,
        "monitor_digests_sent": 1,
        "monitor_checked_total": 88,
        "monitor_skip_reasons": {"target_cooldown": 2, "status_not_interesting": 86},
        "monitor_duplicate_alert_groups": [],
        "monitor_duplicate_alert_groups_total": 0,
        "telegram_errors_total": 0,
        "registration_enabled": False,
        "monitor_enabled": False,
        "monitor_watchlist_only": True,
        "monitor_admin_fanout_enabled": False,
        "monitor_alert_target_cooldown_minutes": 360,
    }


def test_summarize_monitor_quality_events_counts_canary_signals() -> None:
    events = [
        {
            "event_type": "monitor_run_finished",
            "payload": {
                "checked": 10,
                "alerts_sent": 1,
                "skip_reasons": {"target_cooldown": 2, "status_not_interesting": 7},
            },
        },
        {
            "event_type": "monitor_run_finished",
            "payload": {
                "checked": 5,
                "alerts_sent": 0,
                "skip_reasons": {"watch_daily_limit": 5},
            },
        },
        {"event_type": "monitor_alert_sent", "payload": {}},
        {
            "event_type": "monitor_alert_sent",
            "telegram_chat_id": "13903713",
            "created_at": "2026-06-17T10:00:00+00:00",
            "payload": {"fqdn": "assistlab.io", "destination": "13903713"},
        },
        {
            "event_type": "monitor_alert_sent",
            "telegram_chat_id": "13903713",
            "created_at": "2026-06-17T12:00:00+00:00",
            "payload": {"fqdn": "assistlab.io", "destination": "13903713"},
        },
        {
            "event_type": "monitor_alert_sent",
            "telegram_chat_id": "13903713",
            "created_at": "2026-06-17T13:00:00+00:00",
            "payload": {"fqdn": "catchhub.ru", "destination": "13903713"},
        },
        {"event_type": "monitor_digest_sent", "payload": {"items_count": 3}},
        {"event_type": "monitor_digest_sent", "payload": {"delivery": {"mode": "telegram_error"}}},
        {"event_type": "monitor_candidate_error", "payload": {"error": "provider timeout"}},
        {"event_type": "telegram_delivery_error", "payload": {"error": "blocked"}},
    ]

    assert summarize_monitor_quality_events(events) == {
        "monitor_runs_total": 2,
        "monitor_alerts_sent": 4,
        "monitor_digests_sent": 2,
        "monitor_checked_total": 15,
        "monitor_skip_reasons": {
            "status_not_interesting": 7,
            "target_cooldown": 2,
            "watch_daily_limit": 5,
        },
        "monitor_duplicate_alert_groups": [
            {
                "destination": "13903713",
                "fqdn": "assistlab.io",
                "count": 2,
                "first_sent_at": "2026-06-17T10:00:00+00:00",
                "last_sent_at": "2026-06-17T12:00:00+00:00",
            }
        ],
        "monitor_duplicate_alert_groups_total": 1,
        "telegram_errors_total": 2,
    }


def test_summarize_monitor_quality_events_orders_duplicate_timestamps_by_instant() -> None:
    events = [
        {
            "event_type": "monitor_alert_sent",
            "telegram_chat_id": "13903713",
            "created_at": "2026-06-17T09:00:00+03:00",
            "payload": {"fqdn": "assistlab.io"},
        },
        {
            "event_type": "monitor_alert_sent",
            "telegram_chat_id": "13903713",
            "created_at": "2026-06-17T07:00:00+00:00",
            "payload": {"fqdn": "assistlab.io"},
        },
    ]

    metrics = summarize_monitor_quality_events(events)

    assert metrics["monitor_duplicate_alert_groups"] == [
        {
            "destination": "13903713",
            "fqdn": "assistlab.io",
            "count": 2,
            "first_sent_at": "2026-06-17T09:00:00+03:00",
            "last_sent_at": "2026-06-17T07:00:00+00:00",
        }
    ]


def test_build_alert_feedback_ratios_handles_zero_total() -> None:
    assert build_alert_feedback_ratios({}) == {
        "more": 0,
        "less": 0,
        "never": 0,
        "why": 0,
        "positive_rate": 0.0,
        "negative_rate": 0.0,
        "total": 0,
    }


def test_build_alert_feedback_ratios_groups_quality_signals() -> None:
    assert build_alert_feedback_ratios({"more": 3, "less": 2, "never": 1, "why": 4}) == {
        "more": 3,
        "less": 2,
        "never": 1,
        "why": 4,
        "positive_rate": 0.3,
        "negative_rate": 0.3,
        "total": 10,
    }
