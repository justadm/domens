import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import llm_nlu
from app.services.llm_nlu import LlmNluResult, LlmReplyResult


def test_detect_intent_uses_intent_model(monkeypatch) -> None:
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_nlu_enabled", True)
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_provider", "ollama")
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_intent_model", "qwen2.5:0.5b")
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_intent_timeout_seconds", 12)

    captured: dict = {}

    async def _fake_call_ollama(message: str, mode: str, lang: str, model: str, timeout: int):
        captured.update({"model": model, "timeout": timeout, "mode": mode})
        return LlmNluResult(intent="help", confidence=0.9, entities={}, provider="ollama", model=model)

    monkeypatch.setattr(llm_nlu, "_call_ollama", _fake_call_ollama)

    result = asyncio.run(llm_nlu.detect_intent_with_llm(message="что умеешь", mode="assistant", lang="ru"))
    assert result is not None
    assert captured["model"] == "qwen2.5:0.5b"
    assert captured["timeout"] == 12


def test_generate_reply_uses_reply_model(monkeypatch) -> None:
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_nlu_enabled", True)
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_provider", "ollama")
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_reply_model", "qwen2.5:7b-instruct")
    monkeypatch.setattr(llm_nlu.settings, "copilot_llm_reply_timeout_seconds", 35)

    captured: dict = {}

    async def _fake_generate_reply_ollama(
        message: str,
        intent: str,
        lang: str,
        history: list[dict],
        model: str,
        timeout: int,
    ):
        captured.update({"model": model, "timeout": timeout, "intent": intent})
        return LlmReplyResult(reply="ok", provider="ollama", model=model)

    monkeypatch.setattr(llm_nlu, "_generate_reply_ollama", _fake_generate_reply_ollama)

    result = asyncio.run(
        llm_nlu.generate_chat_reply_with_llm(
            message="привет",
            intent="chat",
            lang="ru",
            history=[],
        )
    )
    assert result is not None
    assert captured["model"] == "qwen2.5:7b-instruct"
    assert captured["timeout"] == 35
