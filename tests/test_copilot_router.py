import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.routers import copilot as copilot_router
from app.routers.auth import AuthUserResponse
from app.services.llm_nlu import LlmNluResult, LlmReplyResult


def _mock_auth(monkeypatch) -> None:
    monkeypatch.setattr(
        copilot_router,
        "get_authenticated_user",
        lambda _request: AuthUserResponse(telegram_user_id="13903713", username="just", is_admin=True),
    )
    monkeypatch.setattr(copilot_router, "_lang_for_user", lambda _uid: "ru")


def test_copilot_message_requires_auth(monkeypatch) -> None:
    monkeypatch.setattr(copilot_router, "get_authenticated_user", lambda _request: None)
    client = TestClient(app)
    response = client.post("/v1/copilot/message", json={"message": "hello", "mode": "chat"})
    assert response.status_code == 401


def test_copilot_message_returns_confirmation(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")
    monkeypatch.setattr(
        copilot_router.store,
        "create_copilot_confirmation",
        lambda **_kwargs: {
            "confirmation_token": "cp_test_1",
            "action_type": "create_watch",
            "action_payload": {"query": "ai security", "tlds": [".ai"]},
        },
    )

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/message",
        json={"message": "добавь watch для ai security", "mode": "assistant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["requires_confirmation"] is True
    assert data["confirmation_token"] == "cp_test_1"
    assert data["intent"] == "create_watch"


def test_copilot_confirm_cancel(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(
        copilot_router.store,
        "get_copilot_confirmation",
        lambda *_args, **_kwargs: {
            "status": "pending",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "conversation_id": "conv-1",
            "action_type": "create_watch",
            "action_payload": {"query": "ai"},
        },
    )
    monkeypatch.setattr(copilot_router.store, "update_copilot_confirmation_status", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/confirm",
        json={"confirmation_token": "cp_test_2", "decision": "cancel"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


def test_copilot_confirm_executes_watch(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(
        copilot_router.store,
        "get_copilot_confirmation",
        lambda *_args, **_kwargs: {
            "status": "pending",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "conversation_id": "conv-1",
            "action_type": "create_watch",
            "action_payload": {"query": "ai security", "tlds": [".ai", ".io"]},
        },
    )
    monkeypatch.setattr(copilot_router.store, "add_watch_rule", lambda **_kwargs: "rule-1")
    monkeypatch.setattr(copilot_router.store, "update_copilot_confirmation_status", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/confirm",
        json={"confirmation_token": "cp_test_3", "decision": "confirm"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "executed"
    assert data["execution_result"]["rule_id"] == "rule-1"


def test_copilot_domain_suggest(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    async def _fake_status(domain: str, **_kwargs):
        if domain.endswith(".ru"):
            return "available", None
        return "registered", None

    monkeypatch.setattr(copilot_router, "infer_status", _fake_status)
    monkeypatch.setattr(copilot_router, "score_domain", lambda _domain: 77)

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/message",
        json={"message": "подбери домен на ИИ-тематику в зоне .ru", "mode": "assistant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "domain_suggest"
    assert "candidate" in data["reply"].lower() or "подбор кандидатов" in data["reply"].lower()


def test_copilot_domain_suggest_prioritizes_actionable_status(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    async def _fake_status(domain: str, **_kwargs):
        if "fintechhub.ru" in domain:
            return "pending_delete", None
        return "registered", None

    monkeypatch.setattr(copilot_router, "infer_status", _fake_status)
    monkeypatch.setattr(copilot_router, "score_domain", lambda _domain: 70)

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/message",
        json={"message": "подбери домен для fintech в зоне .ru", "mode": "assistant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "domain_suggest"
    assert "pending_delete" in data["reply"]


def test_copilot_domain_suggest_available_only_mode(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")

    async def _fake_status(domain: str, **_kwargs):
        if domain.endswith(".ru"):
            return "available", None
        return "registered", None

    monkeypatch.setattr(copilot_router, "infer_status", _fake_status)
    monkeypatch.setattr(copilot_router, "score_domain", lambda _domain: 66)

    client = TestClient(app)
    response = client.post(
        "/v1/copilot/message",
        json={"message": "подбери домен для fintech в зоне .ru,.com только свободные", "mode": "assistant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "domain_suggest"
    assert "только свободные" in data["reply"].lower()
    assert "registered" not in data["reply"].lower()


def test_copilot_uses_llm_intent_when_confident(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")
    monkeypatch.setattr(copilot_router.settings, "copilot_llm_nlu_enabled", True)
    monkeypatch.setattr(copilot_router.settings, "copilot_llm_confidence_threshold", 0.65)
    async def _fake_llm(**_kwargs):
        return LlmNluResult(
            intent="help",
            confidence=0.92,
            entities={},
            provider="ollama",
            model="qwen2.5:7b-instruct",
        )

    monkeypatch.setattr(copilot_router, "detect_intent_with_llm", _fake_llm)

    client = TestClient(app)
    response = client.post("/v1/copilot/message", json={"message": "что ты умеешь?", "mode": "assistant"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "help"


def test_copilot_falls_back_when_llm_confidence_low(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")
    monkeypatch.setattr(
        copilot_router.store,
        "create_copilot_confirmation",
        lambda **_kwargs: {
            "confirmation_token": "cp_test_low_conf",
            "action_type": "create_watch",
            "action_payload": {"query": "ai tools", "tlds": [".ai"]},
        },
    )
    monkeypatch.setattr(copilot_router.settings, "copilot_llm_nlu_enabled", True)
    monkeypatch.setattr(copilot_router.settings, "copilot_llm_confidence_threshold", 0.95)
    async def _fake_llm(**_kwargs):
        return LlmNluResult(
            intent="help",
            confidence=0.4,
            entities={},
            provider="ollama",
            model="qwen2.5:7b-instruct",
        )

    monkeypatch.setattr(copilot_router, "detect_intent_with_llm", _fake_llm)

    client = TestClient(app)
    response = client.post("/v1/copilot/message", json={"message": "добавь watch для ai tools", "mode": "assistant"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "create_watch"
    assert data["requires_confirmation"] is True


def test_copilot_chat_uses_llm_reply(monkeypatch) -> None:
    _mock_auth(monkeypatch)
    monkeypatch.setattr(copilot_router.store, "get_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(copilot_router.store, "create_conversation", lambda *_args, **_kwargs: "conv-1")
    monkeypatch.setattr(copilot_router.store, "log_conversation_message", lambda **_kwargs: "msg-1")
    monkeypatch.setattr(copilot_router.store, "log_copilot_event", lambda **_kwargs: "evt-1")
    monkeypatch.setattr(copilot_router.store, "list_conversation_messages", lambda **_kwargs: [])
    monkeypatch.setattr(copilot_router.settings, "copilot_llm_nlu_enabled", True)

    async def _fake_detect(**_kwargs):
        return None

    async def _fake_reply(**_kwargs):
        return LlmReplyResult(reply="Привет! Могу помочь с подбором домена и проверкой статуса.", provider="ollama", model="qwen2.5:0.5b")

    monkeypatch.setattr(copilot_router, "detect_intent_with_llm", _fake_detect)
    monkeypatch.setattr(copilot_router, "generate_chat_reply_with_llm", _fake_reply)

    client = TestClient(app)
    response = client.post("/v1/copilot/message", json={"message": "привет", "mode": "chat"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "chat"
    assert "помочь" in data["reply"].lower()
