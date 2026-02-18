from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.config import settings

ALLOWED_INTENTS = {
    "create_watch",
    "toggle_alerts",
    "register_domain",
    "domain_check",
    "domain_suggest",
    "help",
    "qa",
    "chat",
}

INTENT_ALIASES = {
    "watch_create": "create_watch",
    "watch": "create_watch",
    "alerts_toggle": "toggle_alerts",
    "alert_toggle": "toggle_alerts",
    "check_domain": "domain_check",
    "suggest_domains": "domain_suggest",
    "domains_suggest": "domain_suggest",
    "question": "qa",
}

DOMAIN_PATTERN = re.compile(r"\b[a-z0-9][a-z0-9-]{0,61}\.[a-z0-9.-]{2,24}\b", re.IGNORECASE)


@dataclass
class LlmNluResult:
    intent: str
    confidence: float
    entities: dict
    provider: str
    model: str


def _clip(value: str, size: int) -> str:
    return str(value or "").strip()[:size]


def _extract_first_domain(text: str) -> str | None:
    match = DOMAIN_PATTERN.search(str(text or ""))
    if not match:
        return None
    return match.group(0).lower()


def _parse_json_maybe(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _normalize_intent(raw: str) -> str:
    intent = _clip(raw, 64).lower().replace("-", "_")
    intent = INTENT_ALIASES.get(intent, intent)
    if intent not in ALLOWED_INTENTS:
        return "chat"
    return intent


def _normalize_confidence(raw: object) -> float:
    try:
        value = float(raw)
    except Exception:
        return 0.0
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def _normalize_entities(intent: str, entities: dict, message_text: str) -> dict:
    src = entities if isinstance(entities, dict) else {}
    out: dict = {}

    if intent in {"domain_check", "register_domain"}:
        domain = _clip(src.get("domain") or "", 120).lower() or (_extract_first_domain(message_text) or "")
        if domain:
            out["domain"] = domain
        return out

    if intent == "create_watch":
        query = _clip(src.get("query") or message_text, 120)
        if query:
            out["query"] = query
        tlds = src.get("tlds")
        if isinstance(tlds, list):
            out["tlds"] = [f".{str(item).lower().strip().lstrip('.')}" for item in tlds if str(item).strip()][:10]
        return out

    if intent == "toggle_alerts":
        enabled_raw = src.get("enabled")
        if isinstance(enabled_raw, bool):
            out["enabled"] = enabled_raw
        else:
            lowered = str(enabled_raw or "").lower().strip()
            out["enabled"] = lowered in {"1", "true", "yes", "on", "вкл", "включить", "enabled"}
        return out

    if intent == "domain_suggest":
        query = _clip(src.get("query") or message_text, 120)
        if query:
            out["query"] = query
        tlds = src.get("tlds")
        if isinstance(tlds, list):
            out["tlds"] = [f".{str(item).lower().strip().lstrip('.')}" for item in tlds if str(item).strip()][:8]
        mode_raw = str(src.get("suggest_mode") or "prioritized").strip().lower()
        out["suggest_mode"] = "available_only" if mode_raw in {"available_only", "only_available", "free_only"} else "prioritized"
        return out

    return out


def _build_prompt(message: str, mode: str, lang: str) -> str:
    return (
        "You are NLU parser for a domain automation system.\n"
        "Return ONLY one JSON object. No markdown.\n"
        "Schema:\n"
        "{"
        '"intent":"create_watch|toggle_alerts|register_domain|domain_check|domain_suggest|help|qa|chat",'
        '"confidence":0.0,'
        '"entities":{"domain":"","query":"","enabled":true,"tlds":[".com"],"suggest_mode":"prioritized|available_only"}'
        "}\n"
        "Rules:\n"
        "- classify user request into one allowed intent.\n"
        "- for state-changing actions keep intent explicit.\n"
        "- if uncertain choose chat.\n"
        "- confidence in range 0..1.\n"
        f"- user language: {lang}.\n"
        f"- ui mode hint: {mode}.\n"
        f"User message: {message}\n"
    )


async def _call_ollama(message: str, mode: str, lang: str) -> LlmNluResult | None:
    url = settings.copilot_llm_ollama_base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": settings.copilot_llm_ollama_model,
        "prompt": _build_prompt(message, mode, lang),
        "stream": False,
        "format": "json",
    }
    timeout = max(3, int(settings.copilot_llm_timeout_seconds))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        body = response.json()
    data = _parse_json_maybe(body.get("response") or "")
    if not data:
        return None
    intent = _normalize_intent(str(data.get("intent") or "chat"))
    confidence = _normalize_confidence(data.get("confidence"))
    entities = _normalize_entities(intent, data.get("entities") or {}, message)
    return LlmNluResult(
        intent=intent,
        confidence=confidence,
        entities=entities,
        provider="ollama",
        model=settings.copilot_llm_ollama_model,
    )


async def _call_openrouter(message: str, mode: str, lang: str) -> LlmNluResult | None:
    if not settings.copilot_llm_fallback_api_key:
        return None
    url = settings.copilot_llm_fallback_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.copilot_llm_fallback_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.copilot_llm_fallback_model,
        "messages": [
            {"role": "system", "content": "You are strict NLU JSON parser. Return only JSON object."},
            {"role": "user", "content": _build_prompt(message, mode, lang)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    timeout = max(3, int(settings.copilot_llm_timeout_seconds))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
    choices = body.get("choices") if isinstance(body, dict) else None
    content = ""
    if isinstance(choices, list) and choices:
        content = str(((choices[0] or {}).get("message") or {}).get("content") or "")
    data = _parse_json_maybe(content)
    if not data:
        return None
    intent = _normalize_intent(str(data.get("intent") or "chat"))
    confidence = _normalize_confidence(data.get("confidence"))
    entities = _normalize_entities(intent, data.get("entities") or {}, message)
    return LlmNluResult(
        intent=intent,
        confidence=confidence,
        entities=entities,
        provider="openrouter",
        model=settings.copilot_llm_fallback_model,
    )


async def detect_intent_with_llm(message: str, mode: str, lang: str) -> LlmNluResult | None:
    if not settings.copilot_llm_nlu_enabled:
        return None

    provider = str(settings.copilot_llm_provider or "ollama").strip().lower()
    if provider == "ollama":
        result = await _call_ollama(message=message, mode=mode, lang=lang)
        if result:
            return result
        if settings.copilot_llm_fallback_enabled:
            return await _call_openrouter(message=message, mode=mode, lang=lang)
        return None

    if provider == "openrouter":
        result = await _call_openrouter(message=message, mode=mode, lang=lang)
        if result:
            return result
        if settings.copilot_llm_fallback_enabled:
            return await _call_ollama(message=message, mode=mode, lang=lang)
        return None

    return None
