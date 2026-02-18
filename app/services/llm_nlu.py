from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

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
WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-Я0-9_]{3,}")
_KB_PARAGRAPHS: list[tuple[str, str]] | None = None


@dataclass
class LlmNluResult:
    intent: str
    confidence: float
    entities: dict
    provider: str
    model: str


@dataclass
class LlmReplyResult:
    reply: str
    provider: str
    model: str
    trim_reason: str | None = None


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
    knowledge_block = _select_knowledge_context(message, settings.copilot_llm_knowledge_max_chars)
    if knowledge_block:
        knowledge_block = f"Knowledge snippets:\n{knowledge_block}\n"
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
        "- use knowledge snippets as source of truth for domain-specific commands/flows.\n"
        f"- user language: {lang}.\n"
        f"- ui mode hint: {mode}.\n"
        f"{knowledge_block}"
        f"User message: {message}\n"
    )


def _clean_reply_text(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json|text)?", "", value).strip()
        value = re.sub(r"```$", "", value).strip()
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def _trim_reply_text(text: str, max_chars: int) -> tuple[str, str | None]:
    safe_limit = max(120, int(max_chars))
    value = _clean_reply_text(text)
    if len(value) <= safe_limit:
        return value, None
    trimmed = value[: safe_limit - 1].rstrip()
    return trimmed + "…", "max_chars"


def _build_chat_prompt(message: str, intent: str, lang: str, history: list[dict]) -> str:
    max_chars = max(120, int(settings.copilot_llm_reply_max_chars))
    knowledge_block = _select_knowledge_context(message, settings.copilot_llm_knowledge_max_chars)
    lines = []
    for item in history[-8:]:
        direction = "user" if str(item.get("direction")) == "user" else "assistant"
        text = _clip(item.get("message_text") or "", 240)
        if text:
            lines.append(f"{direction}: {text}")
    history_block = "\n".join(lines) if lines else "(empty)"
    if knowledge_block:
        knowledge_block = f"Knowledge snippets:\n{knowledge_block}\n"

    return (
        "You are an assistant for domain monitoring and registration service.\n"
        "Answer naturally and briefly in user's language.\n"
        "Do not invent executed actions. For mutating actions mention confirmation is required.\n"
        "If request is unclear, ask one short clarifying question.\n"
        f"Intent hint: {intent}\n"
        f"User language: {lang}\n"
        f"Max answer length: {max_chars} chars\n"
        f"{knowledge_block}"
        "Recent context:\n"
        f"{history_block}\n"
        "User message:\n"
        f"{message}\n"
        "Return plain text only."
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_kb_paragraphs() -> list[tuple[str, str]]:
    global _KB_PARAGRAPHS
    if _KB_PARAGRAPHS is not None:
        return _KB_PARAGRAPHS

    if not settings.copilot_llm_knowledge_enabled:
        _KB_PARAGRAPHS = []
        return _KB_PARAGRAPHS

    root = _project_root()
    files = [item.strip() for item in str(settings.copilot_llm_knowledge_files or "").split(",") if item.strip()]
    paragraphs: list[tuple[str, str]] = []
    for rel in files:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunks = [re.sub(r"\s+", " ", block).strip() for block in text.split("\n\n")]
        for chunk in chunks:
            if len(chunk) < 30:
                continue
            paragraphs.append((rel, chunk[:1000]))

    _KB_PARAGRAPHS = paragraphs[:2000]
    return _KB_PARAGRAPHS


def _query_terms(text: str) -> set[str]:
    return {m.group(0).lower() for m in WORD_PATTERN.finditer(str(text or ""))}


def _score_paragraph(query_terms: set[str], paragraph: str) -> int:
    if not query_terms:
        return 0
    words = {m.group(0).lower() for m in WORD_PATTERN.finditer(paragraph)}
    return len(query_terms & words)


def _select_knowledge_context(message: str, max_chars: int) -> str:
    if not settings.copilot_llm_knowledge_enabled:
        return ""
    limit = max(400, int(max_chars or 2400))
    terms = _query_terms(message)
    rows = _load_kb_paragraphs()
    if not rows:
        return ""

    scored: list[tuple[int, str, str]] = []
    for source, paragraph in rows:
        score = _score_paragraph(terms, paragraph)
        if score > 0:
            scored.append((score, source, paragraph))
    if not scored:
        # fallback: first few headings/paragraphs if no overlap
        scored = [(1, source, paragraph) for source, paragraph in rows[:6]]

    scored.sort(key=lambda item: item[0], reverse=True)
    picked: list[str] = []
    used = 0
    for _score, source, paragraph in scored:
        line = f"[{source}] {paragraph}"
        if used + len(line) + 1 > limit:
            continue
        picked.append(line)
        used += len(line) + 1
        if len(picked) >= 6:
            break
    return "\n".join(picked)


def _intent_model() -> str:
    return str(settings.copilot_llm_intent_model or settings.copilot_llm_ollama_model).strip() or "qwen2.5:0.5b"


def _reply_model() -> str:
    return str(settings.copilot_llm_reply_model or settings.copilot_llm_ollama_model).strip() or "qwen2.5:7b-instruct"


def _intent_timeout() -> int:
    return max(3, int(settings.copilot_llm_intent_timeout_seconds or settings.copilot_llm_timeout_seconds))


def _reply_timeout() -> int:
    return max(3, int(settings.copilot_llm_reply_timeout_seconds or settings.copilot_llm_timeout_seconds))


async def _call_ollama(message: str, mode: str, lang: str, model: str, timeout: int) -> LlmNluResult | None:
    url = settings.copilot_llm_ollama_base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": _build_prompt(message, mode, lang),
        "stream": False,
        "format": "json",
    }
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
        model=model,
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


async def _generate_reply_ollama(
    message: str,
    intent: str,
    lang: str,
    history: list[dict],
    model: str,
    timeout: int,
) -> LlmReplyResult | None:
    url = settings.copilot_llm_ollama_base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": _build_chat_prompt(message=message, intent=intent, lang=lang, history=history),
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        body = response.json()
    reply = str(body.get("response") or "").strip()
    if not reply:
        return None
    text, trim_reason = _trim_reply_text(reply, settings.copilot_llm_reply_max_chars)
    return LlmReplyResult(
        reply=text,
        provider="ollama",
        model=model,
        trim_reason=trim_reason,
    )


async def _generate_reply_openrouter(message: str, intent: str, lang: str, history: list[dict]) -> LlmReplyResult | None:
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
            {"role": "system", "content": "You are concise assistant. Return plain text only."},
            {"role": "user", "content": _build_chat_prompt(message=message, intent=intent, lang=lang, history=history)},
        ],
        "temperature": 0.25,
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
    if not content.strip():
        return None
    text, trim_reason = _trim_reply_text(content, settings.copilot_llm_reply_max_chars)
    return LlmReplyResult(
        reply=text,
        provider="openrouter",
        model=settings.copilot_llm_fallback_model,
        trim_reason=trim_reason,
    )


async def detect_intent_with_llm(message: str, mode: str, lang: str) -> LlmNluResult | None:
    if not settings.copilot_llm_nlu_enabled:
        return None

    provider = str(settings.copilot_llm_provider or "ollama").strip().lower()
    if provider == "ollama":
        result = await _call_ollama(
            message=message,
            mode=mode,
            lang=lang,
            model=_intent_model(),
            timeout=_intent_timeout(),
        )
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


async def generate_chat_reply_with_llm(
    message: str,
    intent: str,
    lang: str,
    history: list[dict] | None = None,
) -> LlmReplyResult | None:
    if not settings.copilot_llm_nlu_enabled:
        return None

    context = history or []
    provider = str(settings.copilot_llm_provider or "ollama").strip().lower()
    if provider == "ollama":
        result = await _generate_reply_ollama(
            message=message,
            intent=intent,
            lang=lang,
            history=context,
            model=_reply_model(),
            timeout=_reply_timeout(),
        )
        if result:
            return result
        if settings.copilot_llm_fallback_enabled:
            return await _generate_reply_openrouter(message=message, intent=intent, lang=lang, history=context)
        return None

    if provider == "openrouter":
        result = await _generate_reply_openrouter(message=message, intent=intent, lang=lang, history=context)
        if result:
            return result
        if settings.copilot_llm_fallback_enabled:
            return await _generate_reply_ollama(message=message, intent=intent, lang=lang, history=context)
        return None

    return None
