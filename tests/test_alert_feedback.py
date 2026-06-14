import asyncio

from app.routers import telegram as tg


def test_feedback_callback_is_recorded(monkeypatch) -> None:
    recorded: dict[str, str] = {}
    answered: list[tuple[str, str | None]] = []
    events: list[str] = []

    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))
    monkeypatch.setattr(
        tg.store,
        "record_alert_feedback",
        lambda token, telegram_user_id, feedback_type, payload=None: recorded.update(
            {"token": token, "user": telegram_user_id, "type": feedback_type}
        )
        or True,
    )

    async def fake_answer(callback_query_id: str, text: str | None = None) -> dict:
        answered.append((callback_query_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "answer_telegram_callback", fake_answer)

    result = asyncio.run(
        tg.process_telegram_update(
            {
                "callback_query": {
                    "id": "cb1",
                    "data": "feedback:less:cfm_123",
                    "from": {"id": 13903713},
                    "message": {"chat": {"id": 13903713}},
                }
            }
        )
    )

    assert result["action"] == "feedback"
    assert recorded == {"token": "cfm_123", "user": "13903713", "type": "less"}
    assert answered == [("cb1", "Принято")]
    assert "alert_feedback" in events


def test_feedback_never_adds_long_suppression(monkeypatch) -> None:
    suppressions: list[tuple[str, str, str, int]] = []

    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "record_alert_feedback", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        tg.store,
        "get_alert_by_token",
        lambda _token: type("Alert", (), {"domain": "stackai.ru", "telegram_chat_id": "13903713"})(),
    )
    monkeypatch.setattr(
        tg.store,
        "suppress_alert",
        lambda fqdn, destination, reason, days=30: suppressions.append((fqdn, destination, reason, days)),
    )

    async def fake_answer(_callback_query_id: str, _text: str | None = None) -> dict:
        return {"ok": True}

    monkeypatch.setattr(tg, "answer_telegram_callback", fake_answer)

    result = asyncio.run(
        tg.process_telegram_update(
            {
                "callback_query": {
                    "id": "cb1",
                    "data": "feedback:never:cfm_123",
                    "from": {"id": 13903713},
                    "message": {"chat": {"id": 13903713}},
                }
            }
        )
    )

    assert result["action"] == "feedback"
    assert suppressions == [("stackai.ru", "13903713", "user_never", 365)]


def test_feedback_why_sends_saved_alert_explanation(monkeypatch) -> None:
    recorded: dict[str, str] = {}
    texts: list[tuple[str, str]] = []
    answered: list[tuple[str, str | None]] = []
    events: list[str] = []

    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))
    monkeypatch.setattr(
        tg.store,
        "record_alert_feedback",
        lambda token, telegram_user_id, feedback_type, payload=None: recorded.update(
            {"token": token, "user": telegram_user_id, "type": feedback_type}
        )
        or True,
    )
    monkeypatch.setattr(
        tg.store,
        "get_alert_by_token",
        lambda _token: type(
            "Alert",
            (),
            {
                "domain": "stackai.ru",
                "telegram_chat_id": "13903713",
                "explanation": {
                    "score": 87.35,
                    "status": "available",
                    "tld": "ru",
                    "matched_query": "ai tools",
                    "risk": "provider_checked",
                },
            },
        )(),
    )

    async def fake_answer(callback_query_id: str, text: str | None = None) -> dict:
        answered.append((callback_query_id, text))
        return {"ok": True}

    async def fake_send_text(chat_id: str, text: str) -> dict:
        texts.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "answer_telegram_callback", fake_answer)
    monkeypatch.setattr(tg, "send_telegram_text", fake_send_text)

    result = asyncio.run(
        tg.process_telegram_update(
            {
                "callback_query": {
                    "id": "cb1",
                    "data": "feedback:why:cfm_123",
                    "from": {"id": 13903713},
                    "message": {"chat": {"id": 13903713}},
                }
            }
        )
    )

    assert result["action"] == "feedback"
    assert result["feedback_type"] == "why"
    assert recorded == {"token": "cfm_123", "user": "13903713", "type": "why"}
    assert answered == [("cb1", "Показываю почему")]
    assert texts
    assert "Почему прислал stackai.ru:" in texts[0][1]
    assert "score: 87.35" in texts[0][1]
    assert "статус: available" in texts[0][1]
    assert "TLD: .ru" in texts[0][1]
    assert "watch: ai tools" in texts[0][1]
    assert "риск: provider_checked" in texts[0][1]
    assert "alert_feedback" in events
