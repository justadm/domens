import asyncio
from types import SimpleNamespace

from app.routers import telegram as tg


def _telegram_message(text: str) -> dict:
    return {
        "message": {
            "text": text,
            "chat": {"id": 13903713},
            "from": {
                "id": 13903713,
                "username": "just",
                "first_name": "Just",
                "language_code": "ru",
            },
        }
    }


def test_telegram_help_replies_with_menu(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: False)

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/help")))

    assert result["action"] == "help_sent"
    assert sent
    assert sent[0][0] == "13903713"
    assert "/watch" in sent[0][1]
    assert sent[0][2] is not None
    assert "command_help" in events


def test_telegram_profile_replies(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))
    monkeypatch.setattr(
        tg.store,
        "get_telegram_user",
        lambda _uid: SimpleNamespace(
            telegram_user_id="13903713",
            telegram_chat_id="13903713",
            username="just",
            disclaimer_accepted_at="2026-06-12T10:00:00+00:00",
        ),
    )
    monkeypatch.setattr(tg.store, "get_watch_rules_count", lambda _uid: 2)
    monkeypatch.setattr(tg.store, "get_telegram_alerts_enabled", lambda _uid: True)
    monkeypatch.setattr(
        tg.store,
        "get_user_alert_usage_24h",
        lambda *_args, **_kwargs: {"daily_sent": 1, "daily_remaining_total": 24},
    )
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: False)

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/profile")))

    assert result["action"] == "profile_sent"
    assert sent
    assert sent[0][0] == "13903713"
    assert "user_id: 13903713" in sent[0][1]
    assert "active watch rules: 2" in sent[0][1]
    assert "command_profile" in events


def test_telegram_menu_replies_with_main_actions(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/menu")))

    assert result["action"] == "menu_sent"
    assert sent
    assert sent[0][0] == "13903713"
    assert sent[0][1] == "Главное меню:"
    keyboard = sent[0][2]
    assert keyboard is not None
    buttons = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert "/profile" in buttons
    assert "/watch list" in buttons
    assert "/alerts on" in buttons
    assert "/help" in buttons
    assert "/watch seed" not in buttons
    assert "command_menu" in events


def test_admin_command_forbidden_for_regular_user(monkeypatch) -> None:
    sent: list[str] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append(f"{chat_id}:{text}")
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: False)

    result = asyncio.run(tg._handle_admin("chat1", "u1", "/admin roles"))
    assert result["action"] == "admin_forbidden"
    assert sent
    assert "Недостаточно прав" in sent[0]


def test_admin_roles_returns_roles_list(monkeypatch) -> None:
    sent: list[str] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: True)
    monkeypatch.setattr(
        tg.store,
        "list_roles",
        lambda: [
            {"code": "admin", "title": "Admin"},
            {"code": "viewer", "title": "Viewer"},
        ],
    )
    monkeypatch.setattr(tg.store, "log_bot_event", lambda *args, **kwargs: None)

    result = asyncio.run(tg._handle_admin("chat1", "u1", "/admin roles"))
    assert result["action"] == "admin_roles"
    assert result["count"] == 2
    assert sent
    assert "Роли:" in sent[0]
    assert "admin (Admin)" in sent[0]


def test_admin_access_events_returns_rows(monkeypatch) -> None:
    sent: list[str] = []

    async def _fake_send(_chat_id: str, text: str) -> dict:
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: True)
    monkeypatch.setattr(
        tg.store,
        "list_access_events",
        lambda **_kwargs: [
            {
                "created_at": "2026-02-18T17:30:00+00:00",
                "action": "grant_role",
                "actor_telegram_user_id": "13903713",
                "target_telegram_user_id": "42",
                "role_code": "operator",
            }
        ],
    )
    monkeypatch.setattr(tg.store, "log_bot_event", lambda *args, **kwargs: None)

    result = asyncio.run(tg._handle_admin("chat1", "u1", "/admin access-events grant_role 5"))
    assert result["action"] == "admin_access_events"
    assert result["count"] == 1
    assert sent
    assert "Аудит доступа" in sent[0]
    assert "grant_role" in sent[0]


def test_admin_access_events_bad_limit(monkeypatch) -> None:
    sent: list[str] = []

    async def _fake_send(_chat_id: str, text: str) -> dict:
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: True)

    result = asyncio.run(tg._handle_admin("chat1", "u1", "/admin access-events grant_role abc"))
    assert result["action"] == "admin_access_events_bad_limit"
    assert sent
    assert "Лимит должен быть числом" in sent[0]


def test_admin_grant_superadmin_forbidden_for_non_superadmin(monkeypatch) -> None:
    sent: list[str] = []

    async def _fake_send(_chat_id: str, text: str) -> dict:
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: True)
    monkeypatch.setattr(tg, "_can_manage_role", lambda _uid, _role: False)

    result = asyncio.run(tg._handle_admin("chat1", "u1", "/admin grant 42 superadmin"))
    assert result["action"] == "admin_grant_forbidden_role_manage"
    assert sent
    assert "Только superadmin" in sent[0]
