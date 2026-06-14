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
    assert "Быстрые действия" in sent[0][1]
    assert "/commands" in sent[0][1]
    assert "/watch add" not in sent[0][1]
    assert sent[0][2] is not None
    buttons = [button["text"] for row in sent[0][2]["keyboard"] for button in row]
    assert "👤 Профиль" in buttons
    assert "🎯 Радар" in buttons
    assert "command_help" in events


def test_telegram_commands_replies_with_full_reference(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: False)

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/commands")))

    assert result["action"] == "commands_sent"
    assert sent
    assert "Все команды:" in sent[0][1]
    assert "/watch add <query>" in sent[0][1]
    assert "/admin roles" not in sent[0][1]
    assert sent[0][2] is not None
    assert "command_commands" in events


def test_telegram_start_existing_user_points_to_menu(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(
        tg.store,
        "upsert_telegram_user",
        lambda *args, **kwargs: SimpleNamespace(disclaimer_accepted_at="2026-06-12T10:00:00+00:00"),
    )
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/start")))

    assert result["action"] == "start_existing_user"
    assert sent
    assert "Главное меню" in sent[0][1]
    assert "/commands" in sent[0][1]
    assert "списка команд" not in sent[0][1]
    buttons = [button["text"] for row in sent[0][2]["keyboard"] for button in row]
    assert "👤 Профиль" in buttons
    assert "🎯 Радар" in buttons
    assert "command_start" in events


def test_disclaimer_acceptance_points_to_menu(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []
    answered: list[tuple[str, str | None]] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    async def _fake_answer(callback_query_id: str, text: str | None = None) -> dict:
        answered.append((callback_query_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(tg, "answer_telegram_callback", _fake_answer)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "mark_disclaimer_accepted", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))

    result = asyncio.run(
        tg.process_telegram_update(
            {
                "callback_query": {
                    "id": "cb1",
                    "data": "accept_disclaimer",
                    "from": {"id": 13903713},
                    "message": {"chat": {"id": 13903713}},
                }
            }
        )
    )

    assert result["action"] == "disclaimer_accepted"
    assert answered == [("cb1", None)]
    assert sent
    assert "Главное меню" in sent[0][1]
    assert "/commands" in sent[0][1]
    assert "/profile, /watch" not in sent[0][1]
    assert "disclaimer_accepted" in events


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
    assert "Профиль" in sent[0][1]
    assert "Роль: user" in sent[0][1]
    assert "Username: @just" in sent[0][1]
    assert "Алерты: включены" in sent[0][1]
    assert "Активных правил: 2" in sent[0][1]
    assert "За 24ч: отправлено 1, осталось 24" in sent[0][1]
    assert "user_id:" not in sent[0][1]
    assert "chat_id:" not in sent[0][1]
    assert "disclaimer:" not in sent[0][1]
    assert "command_profile" in events


def test_telegram_profile_does_not_show_remaining_when_alerts_disabled(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda *args, **kwargs: None)
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
    monkeypatch.setattr(tg.store, "get_watch_rules_count", lambda _uid: 10)
    monkeypatch.setattr(tg.store, "get_telegram_alerts_enabled", lambda _uid: False)
    monkeypatch.setattr(
        tg.store,
        "get_user_alert_usage_24h",
        lambda *_args, **_kwargs: {"daily_sent": 0, "daily_remaining_total": 0},
    )
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: True)

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/profile")))

    assert result["action"] == "profile_sent"
    assert sent
    assert "Алерты: выключены" in sent[0][1]
    assert "За 24ч: отправлено 0" in sent[0][1]
    assert "осталось" not in sent[0][1]


def test_telegram_menu_replies_with_icon_grid(monkeypatch) -> None:
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
    assert [[button["text"] for button in row] for row in keyboard["keyboard"]] == [
        ["👤 Профиль", "📊 Лимиты", "🎯 Радар"],
        ["🔔 Алерты", "🔎 Найти", "❓ Помощь"],
    ]
    buttons = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert "👤 Профиль" in buttons
    assert "📊 Лимиты" in buttons
    assert "🎯 Радар" in buttons
    assert "🔔 Алерты" in buttons
    assert "🔎 Найти" in buttons
    assert "❓ Помощь" in buttons
    assert "/profile" not in buttons
    assert "/watch seed" not in buttons
    assert "command_menu" in events


def test_telegram_watch_menu_button_opens_submenu(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))

    result = asyncio.run(tg.process_telegram_update(_telegram_message("🎯 Радар")))

    assert result["action"] == "watch_menu_sent"
    assert sent
    assert sent[0][1] == "Радар доменов:"
    keyboard = sent[0][2]
    assert keyboard is not None
    assert [[button["text"] for button in row] for row in keyboard["keyboard"]] == [
        ["📋 Правила", "➕ Добавить", "🌱 Старт"],
        ["🎚 Core", "🌐 Wide", "⬅️ Назад"],
    ]
    assert "command_watch_menu" in events


def test_telegram_alerts_menu_button_opens_submenu(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))

    result = asyncio.run(tg.process_telegram_update(_telegram_message("🔔 Алерты")))

    assert result["action"] == "alerts_menu_sent"
    assert sent
    assert sent[0][1] == "Управление алертами:"
    keyboard = sent[0][2]
    assert keyboard is not None
    assert [[button["text"] for button in row] for row in keyboard["keyboard"]] == [
        ["✅ Включить", "⏸ Выключить", "📊 Лимиты"],
        ["📜 История"],
        ["⬅️ Назад"],
    ]
    assert "command_alerts_menu" in events


def test_watch_rules_text_includes_limits_usage_and_last_alert() -> None:
    text = tg._watch_rules_text(
        [
            {
                "id": "ce1425e4-2d00-4586-9e58-3a8204c83248",
                "status": "active",
                "query": "domain catcher",
                "daily_alert_limit": 1,
                "alerts_24h_sent": 1,
                "last_alert_domain": "catcherlab.ru",
                "last_alert_at": "2026-06-13T17:47:10+00:00",
            },
            {
                "id": "704cdd88-5a9e-4fb7-b54a-ac93610cb78f",
                "status": "paused",
                "query": "domain radar",
                "daily_alert_limit": 1,
                "alerts_24h_sent": 0,
                "last_alert_domain": None,
                "last_alert_at": None,
            },
        ]
    )

    assert "Ваши watch-правила" in text
    assert "1. active domain catcher" in text
    assert "id: ce1425e4" in text
    assert "лимит: 1/день" in text
    assert "за 24ч: 1" in text
    assert "последний: catcherlab.ru" in text
    assert "2. paused domain radar" in text
    assert "последний: пока нет" in text


def test_watch_rules_text_and_keyboard_hide_deleted_rules() -> None:
    rules = [
        {
            "id": "17313857-8a89-473c-9cc9-ad00de7c13b7",
            "status": "deleted",
            "query": "cloud ops",
            "daily_alert_limit": 3,
            "alerts_24h_sent": 0,
            "last_alert_domain": None,
        },
        {
            "id": "ce1425e4-2d00-4586-9e58-3a8204c83248",
            "status": "active",
            "query": "domain catcher",
            "daily_alert_limit": 1,
            "alerts_24h_sent": 1,
            "last_alert_domain": "catcherlab.ru",
        },
    ]

    text = tg._watch_rules_text(rules)
    keyboard = tg._watch_rules_keyboard(rules)

    assert "cloud ops" not in text
    assert "domain catcher" in text
    assert keyboard is not None
    assert "17313857" not in str(keyboard)
    assert "ce1425e4" in str(keyboard)


def test_watch_rules_text_explains_when_only_deleted_rules_exist() -> None:
    text = tg._watch_rules_text(
        [
            {
                "id": "17313857-8a89-473c-9cc9-ad00de7c13b7",
                "status": "deleted",
                "query": "cloud ops",
            }
        ]
    )

    assert "Активных watch-правил нет" in text
    assert "cloud ops" not in text


def test_telegram_limits_explains_when_alerts_disabled(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    events: list[str] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda event, **_kwargs: events.append(event))
    monkeypatch.setattr(tg.store, "get_telegram_alerts_enabled", lambda _uid: False)
    monkeypatch.setattr(
        tg.store,
        "get_user_alert_usage_24h",
        lambda *_args, **_kwargs: {"daily_sent": 0, "daily_remaining_total": 0},
    )

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/limits")))

    assert result["action"] == "limits_sent"
    assert sent
    assert "Алерты выключены" in sent[0][1]
    assert "🔔 Алерты -> ✅ Включить" in sent[0][1]
    assert "осталось: 0" not in sent[0][1]
    assert "command_limits" in events


def test_telegram_human_profile_button_dispatches_profile(monkeypatch) -> None:
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

    result = asyncio.run(tg.process_telegram_update(_telegram_message("👤 Профиль")))

    assert result["action"] == "profile_sent"
    assert sent
    assert "Роль: user" in sent[0][1]
    assert "user_id:" not in sent[0][1]
    assert "command_profile" in events


def test_telegram_watch_add_button_accepts_next_plain_text(monkeypatch) -> None:
    messages: list[tuple[str, str, dict | None]] = []
    texts: list[tuple[str, str]] = []
    events: list[str] = []
    added: list[tuple[str, str]] = []

    if hasattr(tg, "_pending_watch_add"):
        tg._pending_watch_add.clear()

    async def _fake_send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        messages.append((chat_id, text, reply_markup))
        return {"ok": True}

    async def _fake_send_text(chat_id: str, text: str) -> dict:
        texts.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send_message)
    monkeypatch.setattr(tg, "send_telegram_text", _fake_send_text)
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

    def _add_rule(user_id: str, watch_query: str, **_kwargs) -> str:
        added.append((user_id, watch_query))
        return "rule-1"

    monkeypatch.setattr(tg.store, "add_watch_rule", _add_rule)

    prompt_result = asyncio.run(tg.process_telegram_update(_telegram_message("➕ Добавить")))
    add_result = asyncio.run(tg.process_telegram_update(_telegram_message("ai crm")))

    assert prompt_result["action"] == "watch_add_prompt_sent"
    assert messages
    assert "Напишите тему" in messages[0][1]
    assert "/watch add" not in messages[0][1]
    assert add_result["action"] == "watch_added_from_prompt"
    assert added == [("13903713", "ai crm")]
    assert texts
    assert "Правило добавлено" in texts[-1][1]
    assert "command_watch_add_prompt" in events
    assert "watch_add_from_prompt" in events


def test_telegram_find_button_accepts_next_plain_text(monkeypatch) -> None:
    messages: list[tuple[str, str, dict | None]] = []
    texts: list[tuple[str, str]] = []
    events: list[tuple[str, dict | None]] = []

    if hasattr(tg, "_pending_domain_search"):
        tg._pending_domain_search.clear()

    async def _fake_send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        messages.append((chat_id, text, reply_markup))
        return {"ok": True}

    async def _fake_send_text(chat_id: str, text: str) -> dict:
        texts.append((chat_id, text))
        return {"ok": True}

    async def _fake_status(domain: str, **_kwargs):
        return ("available" if domain.endswith(".ru") else "registered", None)

    monkeypatch.setattr(tg, "send_telegram_message", _fake_send_message)
    monkeypatch.setattr(tg, "send_telegram_text", _fake_send_text)
    monkeypatch.setattr(tg, "infer_status", _fake_status)
    monkeypatch.setattr(tg, "score_domain", lambda _domain: 70)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tg.store,
        "log_bot_event",
        lambda event, **kwargs: events.append((event, kwargs.get("payload"))),
    )
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
    monkeypatch.setattr(tg.settings, "monitor_tlds", ".ru,.io", raising=False)

    prompt_result = asyncio.run(tg.process_telegram_update(_telegram_message("🔎 Найти")))
    search_result = asyncio.run(tg.process_telegram_update(_telegram_message("ai tools")))

    assert prompt_result["action"] == "domains_prompt_sent"
    assert messages
    assert "Напишите тему" in messages[0][1]
    assert "/domains now" not in messages[0][1]
    assert search_result["action"] == "domains_now_from_prompt_done"
    assert texts
    assert "Подбор по запросу:" in texts[-1][1]
    assert "aitools.ru" in texts[-1][1]
    assert ("command_domains_prompt", None) in events
    assert any(event == "domains_now_from_prompt" for event, _payload in events)


def test_telegram_alert_history_button_shows_recent_alerts(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    events: list[str] = []
    captured: dict[str, object] = {}

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    def _fake_history(**kwargs):
        captured.update(kwargs)
        return {
            "items": [
                {
                    "domain": "stackai.ru",
                    "alert_type": "watch_rule_match:r1",
                    "created_at": "2026-06-14T10:00:00+00:00",
                    "explanation": {
                        "score": 88.4,
                        "status": "available",
                        "tld": "ru",
                        "matched_query": "stack ai",
                        "risk": "provider_checked",
                    },
                    "latest_feedback": {"type": "more"},
                    "feedback_counts": {"more": 1, "why": 1},
                }
            ],
            "total": 1,
            "limit": 5,
            "offset": 0,
            "next_offset": None,
            "prev_offset": None,
        }

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
    monkeypatch.setattr(tg.store, "list_user_alerts_page", _fake_history)

    result = asyncio.run(tg.process_telegram_update(_telegram_message("📜 История")))

    assert result["action"] == "alerts_history_sent"
    assert captured == {"telegram_user_id": "13903713", "limit": 5, "offset": 0}
    assert sent
    assert "История алертов" in sent[0][1]
    assert "1. stackai.ru" in sent[0][1]
    assert "score: 88.4" in sent[0][1]
    assert "статус: available" in sent[0][1]
    assert "TLD: .ru" in sent[0][1]
    assert "watch: stack ai" in sent[0][1]
    assert "feedback: more" in sent[0][1]
    assert "counts: more=1, why=1" in sent[0][1]
    assert "command_alerts_history" in events


def test_telegram_alert_history_explains_empty_state(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg.store, "upsert_telegram_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda *args, **kwargs: None)
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
    monkeypatch.setattr(
        tg.store,
        "list_user_alerts_page",
        lambda **_kwargs: {"items": [], "total": 0, "limit": 5, "offset": 0, "next_offset": None},
    )

    result = asyncio.run(tg.process_telegram_update(_telegram_message("/alerts history")))

    assert result["action"] == "alerts_history_empty"
    assert sent
    assert "История алертов пока пустая" in sent[0][1]


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


def test_admin_help_returns_admin_command_summary(monkeypatch) -> None:
    sent: list[str] = []

    async def _fake_send(chat_id: str, text: str) -> dict:
        sent.append(f"{chat_id}:{text}")
        return {"ok": True}

    monkeypatch.setattr(tg, "send_telegram_text", _fake_send)
    monkeypatch.setattr(tg, "_is_admin_user", lambda _uid: True)
    monkeypatch.setattr(tg.store, "log_bot_event", lambda *args, **kwargs: None)

    result = asyncio.run(tg._handle_admin("chat1", "u1", "/admin help"))

    assert result["action"] == "admin_help"
    assert sent
    assert "Админ-команды:" in sent[0]
    assert "/admin roles" in sent[0]


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
