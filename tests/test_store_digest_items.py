import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.store import _build_cabinet_digest_item


def test_build_cabinet_digest_item_extracts_delivery_details() -> None:
    event = SimpleNamespace(
        id="event-1",
        telegram_chat_id="13903713",
        created_at=datetime(2026, 6, 16, 6, 13, tzinfo=timezone.utc),
        payload={
            "domains": ["assistlab.io", "catchhub.ru"],
            "destination": "13903713",
            "items_count": 2,
            "delivery": {
                "mode": "telegram",
                "chat_id": "13903713",
                "message_id": "614",
                "items_count": 2,
            },
        },
    )

    item = _build_cabinet_digest_item(event, channel="telegram")

    assert item == {
        "id": "event-1",
        "channel": "telegram",
        "channel_target": "13903713",
        "created_at": "2026-06-16T06:13:00+00:00",
        "domains": ["assistlab.io", "catchhub.ru"],
        "items_count": 2,
        "message_id": "614",
        "delivery": {
            "mode": "telegram",
            "chat_id": "13903713",
            "message_id": "614",
            "items_count": 2,
        },
    }


def test_build_cabinet_digest_item_falls_back_to_delivery_items_count() -> None:
    event = SimpleNamespace(
        id="event-2",
        telegram_chat_id="7951273850",
        created_at=datetime(2026, 6, 16, 6, 6, tzinfo=timezone.utc),
        payload={"domains": ["assistlab.io"], "delivery": {"items_count": 1}},
    )

    item = _build_cabinet_digest_item(event, channel=None)

    assert item["channel"] == "telegram"
    assert item["channel_target"] == "7951273850"
    assert item["items_count"] == 1
    assert item["message_id"] is None
