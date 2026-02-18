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
