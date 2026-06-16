from datetime import datetime, timedelta, timezone

from app.services.store import _build_alert_suppression_state


def test_active_alert_suppression_state_prefers_never_over_less() -> None:
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)

    state = _build_alert_suppression_state(
        [
            {
                "reason": "user_less",
                "created_at": now - timedelta(minutes=10),
                "expires_at": now + timedelta(days=1),
            },
            {
                "reason": "user_never",
                "created_at": now - timedelta(minutes=20),
                "expires_at": now + timedelta(days=10),
            },
        ],
        now=now,
    )

    assert state["reason"] == "user_never"
    assert state["active"] is True


def test_active_alert_suppression_state_ignores_expired_rows() -> None:
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)

    state = _build_alert_suppression_state(
        [
            {
                "reason": "user_never",
                "created_at": now - timedelta(days=2),
                "expires_at": now - timedelta(seconds=1),
            }
        ],
        now=now,
    )

    assert state is None
