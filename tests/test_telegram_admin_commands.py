import asyncio

from app.routers import telegram as tg


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
