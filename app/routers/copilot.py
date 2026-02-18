from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.auth import AuthUserResponse, get_authenticated_user
from app.services.domain_checker import infer_status
from app.services.llm_nlu import detect_intent_with_llm, generate_chat_reply_with_llm
from app.services.domain_scoring import score_domain
from app.services.timeweb_api import TimewebApiClient
from app.state import store

router = APIRouter(prefix="/v1/copilot", tags=["copilot"])

timeweb_client = TimewebApiClient(
    base_url=settings.timeweb_api_base_url,
    api_token=settings.timeweb_api_token,
)

DOMAIN_PATTERN = re.compile(r"\b[a-z0-9][a-z0-9-]{0,61}\.[a-z0-9.-]{2,24}\b", re.IGNORECASE)
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_INFLIGHT_REQUESTS = 0
_INFLIGHT_LOCK = asyncio.Lock()
_LLM_SEMAPHORE = asyncio.Semaphore(max(1, int(settings.copilot_llm_max_parallel)))


async def _inc_inflight() -> int:
    global _INFLIGHT_REQUESTS
    async with _INFLIGHT_LOCK:
        _INFLIGHT_REQUESTS += 1
        return _INFLIGHT_REQUESTS


async def _dec_inflight() -> int:
    global _INFLIGHT_REQUESTS
    async with _INFLIGHT_LOCK:
        _INFLIGHT_REQUESTS = max(0, _INFLIGHT_REQUESTS - 1)
        return _INFLIGHT_REQUESTS


def _rate_limit_check(user_id: str) -> tuple[bool, int, int]:
    now = time.monotonic()
    safe_uid = str(user_id).strip() or "anon"
    window = max(5, int(settings.copilot_rate_limit_window_seconds))
    max_requests = max(1, int(settings.copilot_rate_limit_requests))
    dq = _RATE_BUCKETS[safe_uid]
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= max_requests:
        retry_after = max(1, int(window - (now - dq[0])))
        return False, 0, retry_after
    dq.append(now)
    remaining = max(0, max_requests - len(dq))
    return True, remaining, 0


def _llm_degrade_reason(inflight: int) -> str | None:
    threshold = max(1, int(settings.copilot_degrade_inflight_threshold))
    if inflight >= threshold:
        return "high_inflight"
    return None


def get_copilot_runtime_status() -> dict:
    intent_model = str(settings.copilot_llm_intent_model or settings.copilot_llm_ollama_model or "")
    reply_model = str(settings.copilot_llm_reply_model or settings.copilot_llm_ollama_model or "")
    return {
        "llm_enabled": bool(settings.copilot_llm_nlu_enabled),
        "provider": str(settings.copilot_llm_provider or "ollama"),
        "model": intent_model,
        "intent_model": intent_model,
        "reply_model": reply_model,
        "intent_timeout_seconds": int(settings.copilot_llm_intent_timeout_seconds or settings.copilot_llm_timeout_seconds),
        "reply_timeout_seconds": int(settings.copilot_llm_reply_timeout_seconds or settings.copilot_llm_timeout_seconds),
        "fallback_enabled": bool(settings.copilot_llm_fallback_enabled),
        "fallback_model": str(settings.copilot_llm_fallback_model or ""),
        "confidence_threshold": float(settings.copilot_llm_confidence_threshold),
        "llm_max_parallel": int(settings.copilot_llm_max_parallel),
        "rate_limit": {
            "window_seconds": int(settings.copilot_rate_limit_window_seconds),
            "requests": int(settings.copilot_rate_limit_requests),
            "tracked_users": len(_RATE_BUCKETS),
        },
        "degrade": {
            "inflight_threshold": int(settings.copilot_degrade_inflight_threshold),
            "current_inflight": _INFLIGHT_REQUESTS,
        },
    }


def _reset_runtime_state_for_tests() -> None:
    global _INFLIGHT_REQUESTS
    _RATE_BUCKETS.clear()
    _INFLIGHT_REQUESTS = 0


class CopilotMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="assistant")
    conversation_id: str | None = None
    channel: str = Field(default="web")


class CopilotMessageResponse(BaseModel):
    conversation_id: str
    reply: str
    intent: str
    confidence: float
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    action_preview: dict | None = None


class CopilotConfirmRequest(BaseModel):
    confirmation_token: str
    decision: str = Field(default="confirm")


class CopilotConfirmResponse(BaseModel):
    status: str
    message: str
    execution_result: dict | None = None


def _lang_for_user(user_id: str) -> str:
    user = store.get_telegram_user(user_id)
    locale = str(user.locale or "").strip().lower() if user else ""
    if locale.startswith("en"):
        return "en"
    return "ru"


def _t(lang: str, key: str) -> str:
    ru = {
        "help": (
            "Я могу: объяснить логику сервиса, проверить домен, предложить watch-правило, "
            "включить/выключить алерты и подготовить регистрацию домена с подтверждением."
        ),
        "qa": "Принято. Сформулируйте вопрос подробнее, и я отвечу по данным системы.",
        "chat": "Понял. Можем обсудить идею или задачу; для действий я сначала запрошу подтверждение.",
        "domain_check_start": "Сейчас проверю домен и верну статус.",
        "create_watch_confirm": "Понял как создание watch-правила: `{value}`. Подтвердите выполнение.",
        "toggle_alerts_confirm": "Понял запрос на переключение алертов. Подтвердите выполнение.",
        "register_domain_confirm": "Понял запрос на регистрацию: `{value}`. Подтвердите выполнение.",
        "register_domain_forbidden": "Недостаточно прав для регистрации домена. Нужна роль operator/admin/superadmin.",
        "request_received": "Запрос получен.",
        "domain_missing": "Не вижу домен в запросе. Пример: `проверь freebrand.com`.",
        "domain_suggest_missing": "Уточните тематику. Пример: `подбери домен для fintech в зоне .ai,.ru`.",
        "domain_suggest_header": "Подбор кандидатов:",
        "domain_suggest_mode_available_only": "Режим: только свободные/освобождающиеся.",
        "domain_suggest_mode_prioritized": "Режим: все с приоритетом по доступности.",
        "rate_limited": "Слишком много запросов. Повторите через {retry_after} сек.",
        "llm_degraded": "LLM-временнo отключен из-за нагрузки, использую быстрый режим.",
        "action_done": "Действие выполнено.",
        "action_canceled": "Действие отменено.",
        "token_expired": "Срок подтверждения истек.",
        "already_done": "Запрос уже обработан: {status}",
    }
    en = {
        "help": (
            "I can explain service logic, check a domain, suggest a watch rule, "
            "toggle alerts, and prepare domain registration with explicit confirmation."
        ),
        "qa": "Got it. Ask your question in more detail and I will answer using system data.",
        "chat": "Understood. We can discuss ideas; for actions I will ask for confirmation first.",
        "domain_check_start": "I will check the domain status now.",
        "create_watch_confirm": "I understood this as creating a watch rule: `{value}`. Please confirm.",
        "toggle_alerts_confirm": "I understood this as alert toggle request. Please confirm.",
        "register_domain_confirm": "I understood this as registration request: `{value}`. Please confirm.",
        "register_domain_forbidden": "Not enough permissions for domain registration. Required role: operator/admin/superadmin.",
        "request_received": "Request received.",
        "domain_missing": "No domain detected. Example: `check freebrand.com`.",
        "domain_suggest_missing": "Please specify the topic. Example: `suggest domains for fintech in .ai,.ru`.",
        "domain_suggest_header": "Candidate shortlist:",
        "domain_suggest_mode_available_only": "Mode: only free/releasing domains.",
        "domain_suggest_mode_prioritized": "Mode: all with availability priority.",
        "rate_limited": "Too many requests. Retry in {retry_after} sec.",
        "llm_degraded": "LLM temporarily disabled due to load; using fast mode.",
        "action_done": "Action executed.",
        "action_canceled": "Action canceled.",
        "token_expired": "Confirmation token has expired.",
        "already_done": "Request already processed: {status}",
    }
    bundle = en if lang == "en" else ru
    return bundle.get(key, key)


def _require_user(request: Request) -> AuthUserResponse:
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


def _env_admin_ids() -> set[str]:
    return {item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()}


def _can_register_domain(telegram_user_id: str) -> bool:
    uid = str(telegram_user_id).strip()
    if not uid:
        return False
    if uid in _env_admin_ids():
        return True
    return store.has_any_role(uid, ["operator", "admin", "superadmin"])


def _extract_first_domain(text: str) -> str | None:
    match = DOMAIN_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).lower()


def _extract_watch_query(text: str) -> str:
    quoted = re.findall(r'"([^"]{2,120})"', text)
    if quoted:
        return quoted[0].strip()

    lowered = text.lower()
    for marker in ["следи за", "watch", "добавь правило", "add rule", "monitor"]:
        idx = lowered.find(marker)
        if idx >= 0:
            tail = text[idx + len(marker) :].strip(" :,-")
            if len(tail) >= 2:
                return tail[:120]
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:120]


def _extract_requested_tlds(text: str) -> list[str]:
    found = [f".{match.group(1).lower()}" for match in re.finditer(r"(?:^|[\s,])\.([a-z]{2,10})\b", text.lower())]
    unique: list[str] = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return unique[:6]


def _parse_tlds_from_settings(raw: str) -> list[str]:
    return [item.strip().lower() for item in str(raw or "").split(",") if item.strip()]


def _normalize_suggest_query(raw: str) -> str:
    lowered = str(raw or "").lower()
    aliases = [
        ("искусствен", "ai"),
        ("ии", "ai"),
        ("ai", "ai"),
        ("финтех", "fintech"),
        ("fintech", "fintech"),
        ("безопас", "security"),
        ("security", "security"),
        ("агент", "agent"),
        ("agent", "agent"),
        ("облак", "cloud"),
        ("cloud", "cloud"),
        ("маркет", "market"),
        ("market", "market"),
        ("дев", "dev"),
        ("dev", "dev"),
        ("crypto", "crypto"),
        ("крипт", "crypto"),
    ]
    for marker, value in aliases:
        if marker in lowered:
            return value

    tokens = re.findall(r"[a-z0-9][a-z0-9-]{1,23}", lowered)
    stop = {
        "domain",
        "domains",
        "домен",
        "доменов",
        "подбери",
        "подобрать",
        "подбор",
        "зона",
        "zone",
        "тематикой",
        "тематика",
        "сфере",
        "ниша",
        "topic",
        "под",
        "на",
        "и",
        "в",
    }
    for token in tokens:
        if token not in stop:
            cleaned = re.sub(r"[^a-z0-9-]+", "", token)
            if len(cleaned) >= 2:
                return cleaned[:24]
    return ""


def _suggest_query_terms(raw: str, normalized: str) -> list[str]:
    terms = [item for item in re.findall(r"[a-z0-9]{2,24}", raw.lower()) if len(item) >= 2][:4]
    if normalized and normalized not in terms:
        terms.insert(0, normalized)
    return terms[:4]


def _domains_suggest_rank(item: dict, query_terms: list[str]) -> tuple:
    status_weight = {"available": 100, "pending_delete": 90, "redemption": 75, "client_hold": 70, "registered": 20}
    domain = str(item.get("domain") or "").lower()
    name = domain.split(".", 1)[0]
    base = float(item.get("score") or 0)
    status_bonus = status_weight.get(str(item.get("status") or "registered"), 10)
    term_bonus = 0
    if query_terms:
        hits = sum(1 for term in query_terms if term in name)
        term_bonus = hits * 8
        if name.startswith(query_terms[0]):
            term_bonus += 5
    length_penalty = max(0, len(name) - 11) * 1.5
    final_score = base + status_bonus + term_bonus - length_penalty
    return (-final_score, name)


def _is_noise_candidate(name: str, query: str) -> bool:
    raw = str(name or "").lower()
    if not raw or len(raw) < 3:
        return True
    if raw.startswith("-") or raw.endswith("-") or "--" in raw:
        return True
    if raw in {f"{query}ai", f"{query}{query}", f"go{query}{query}"}:
        return True
    if raw.count(query) > 1 and len(query) >= 3:
        return True
    unique_chars = len(set(raw))
    if len(raw) >= 5 and unique_chars <= 2:
        return True
    return False


def _build_suggest_seeds(normalized_query: str) -> list[str]:
    if not normalized_query:
        return []
    base = normalized_query
    seeds = [
        base,
        f"{base}hub",
        f"{base}lab",
        f"{base}base",
        f"{base}flow",
        f"{base}stack",
        f"{base}core",
        f"get{base}",
        f"try{base}",
        f"{base}now",
    ]
    unique: list[str] = []
    for item in seeds:
        if item not in unique and not _is_noise_candidate(item, base):
            unique.append(item[:24])
    return unique[:12]


def _extract_suggest_mode(raw: str) -> str:
    lowered = str(raw or "").lower()
    available_only_markers = [
        "только свобод",
        "only available",
        "only free",
        "free only",
        "only releasing",
        "только доступ",
    ]
    prioritized_markers = [
        "все с приоритетом",
        "all prioritized",
        "all with priority",
        "все варианты",
    ]
    if any(marker in lowered for marker in available_only_markers):
        return "available_only"
    if any(marker in lowered for marker in prioritized_markers):
        return "prioritized"
    return "prioritized"


def _extract_suggest_query(raw: str) -> str:
    compact = str(raw or "")
    for marker in [
        "подбери",
        "подберем",
        "подберём",
        "подобрать",
        "подбор",
        "предложи",
        "suggest",
        "find",
        "домен",
        "доменов",
        "домены",
        "зона",
        "zone",
        "в зоне",
        "for",
        "для",
    ]:
        compact = re.sub(rf"\b{re.escape(marker)}\b", " ", compact, flags=re.IGNORECASE)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact[:120]


def _detect_intent(text: str, mode: str) -> tuple[str, float, dict]:
    raw = str(text or "").strip()
    lowered = raw.lower()
    entities: dict = {}

    domain = _extract_first_domain(raw)
    if domain:
        entities["domain"] = domain

    if any(word in lowered for word in ["зарегистр", "купи домен", "register domain", "buy domain"]):
        return "register_domain", 0.92, entities

    if any(word in lowered for word in ["включи алерт", "alerts on", "включи уведом"]):
        entities["enabled"] = True
        return "toggle_alerts", 0.9, entities

    if any(word in lowered for word in ["выключи алерт", "alerts off", "выключи уведом"]):
        entities["enabled"] = False
        return "toggle_alerts", 0.9, entities

    if any(word in lowered for word in ["watch", "следи", "монитор", "подписк"]) and mode in {"assistant", "ask"}:
        entities["query"] = _extract_watch_query(raw)
        return "create_watch", 0.88, entities

    if any(
        word in lowered
        for word in [
            "подбери",
            "подберем",
            "подберём",
            "подобрать",
            "подбор",
            "предложи дом",
            "suggest domain",
            "find domain",
        ]
    ):
        entities["query"] = _extract_suggest_query(raw)
        entities["tlds"] = _extract_requested_tlds(raw)
        entities["suggest_mode"] = _extract_suggest_mode(raw)
        return "domain_suggest", 0.86, entities

    if domain and any(word in lowered for word in ["проверь", "status", "свобод", "занят"]):
        return "domain_check", 0.87, entities

    if any(word in lowered for word in ["что умеешь", "help", "команды", "как работает"]):
        return "help", 0.78, entities

    if mode == "ask":
        return "qa", 0.7, entities
    return "chat", 0.6, entities


def _format_preview(action_type: str, payload: dict) -> dict:
    if action_type == "create_watch":
        return {"action": "create_watch", "query": payload.get("query"), "tlds": payload.get("tlds") or []}
    if action_type == "toggle_alerts":
        return {"action": "toggle_alerts", "enabled": bool(payload.get("enabled"))}
    if action_type == "register_domain":
        return {"action": "register_domain", "domain": payload.get("domain")}
    return {"action": action_type, "payload": payload}


def _assistant_text_for_intent(intent: str, entities: dict) -> str:
    return _assistant_text_for_intent_lang(intent, entities, "ru")


def _assistant_text_for_intent_lang(intent: str, entities: dict, lang: str) -> str:
    if intent == "help":
        return _t(lang, "help")
    if intent == "qa":
        return _t(lang, "qa")
    if intent == "chat":
        return _t(lang, "chat")
    if intent == "domain_check":
        return _t(lang, "domain_check_start")
    if intent == "domain_suggest":
        return _t(lang, "domain_suggest_header")
    if intent == "create_watch":
        return _t(lang, "create_watch_confirm").format(value=entities.get("query"))
    if intent == "toggle_alerts":
        return _t(lang, "toggle_alerts_confirm")
    if intent == "register_domain":
        return _t(lang, "register_domain_confirm").format(value=entities.get("domain"))
    return _t(lang, "request_received")


def _action_from_intent(intent: str, entities: dict) -> tuple[str, dict] | None:
    if intent == "create_watch":
        query = str(entities.get("query") or "").strip()
        if not query:
            return None
        tlds = [item.strip() for item in str(settings.monitor_tlds or "").split(",") if item.strip()]
        return "create_watch", {"query": query, "tlds": tlds[:10]}
    if intent == "toggle_alerts":
        return "toggle_alerts", {"enabled": bool(entities.get("enabled"))}
    if intent == "register_domain":
        domain = str(entities.get("domain") or "").strip().lower()
        if not domain:
            return None
        return "register_domain", {"domain": domain}
    return None


@router.post("/message", response_model=CopilotMessageResponse)
async def copilot_message(payload: CopilotMessageRequest, request: Request) -> CopilotMessageResponse:
    user = _require_user(request)
    return await process_copilot_message(
        user_id=user.telegram_user_id,
        message=payload.message,
        mode=payload.mode,
        conversation_id=payload.conversation_id,
        channel=payload.channel,
    )


async def process_copilot_message(
    user_id: str,
    message: str,
    mode: str = "assistant",
    conversation_id: str | None = None,
    channel: str = "web",
) -> CopilotMessageResponse:
    lang = _lang_for_user(user_id)
    mode = str(mode or "assistant").strip().lower()
    if mode not in {"ask", "chat", "assistant"}:
        mode = "assistant"

    allowed, _remaining, retry_after = _rate_limit_check(user_id)
    if not allowed:
        store.log_copilot_event(
            event_type="rate_limited",
            telegram_user_id=user_id,
            conversation_id=None,
            payload={
                "retry_after": retry_after,
                "window_seconds": int(settings.copilot_rate_limit_window_seconds),
                "requests": int(settings.copilot_rate_limit_requests),
            },
        )
        raise HTTPException(status_code=429, detail=_t(lang, "rate_limited").format(retry_after=retry_after))

    inflight = await _inc_inflight()
    degrade_reason = _llm_degrade_reason(inflight)

    conversation_id = str(conversation_id or "").strip()
    if conversation_id:
        conversation = store.get_conversation(conversation_id, telegram_user_id=user_id)
        if not conversation:
            conversation_id = ""
    if not conversation_id:
        conversation_id = store.create_conversation(user_id, channel=channel)

    message_text = str(message or "").strip()
    intent, confidence, entities = _detect_intent(message_text, mode)
    intent_source = "rules"
    llm_meta: dict = {}
    llm_allowed = bool(settings.copilot_llm_nlu_enabled and not degrade_reason)
    if llm_allowed:
        try:
            async with _LLM_SEMAPHORE:
                llm_result = await detect_intent_with_llm(message=message_text, mode=mode, lang=lang)
            if llm_result:
                llm_meta = {
                    "provider": llm_result.provider,
                    "model": llm_result.model,
                    "intent": llm_result.intent,
                    "confidence": llm_result.confidence,
                }
                if llm_result.confidence >= float(settings.copilot_llm_confidence_threshold):
                    intent = llm_result.intent
                    confidence = llm_result.confidence
                    entities = llm_result.entities or {}
                    intent_source = "llm"
                else:
                    intent_source = "rules_llm_low_confidence"
            else:
                intent_source = "rules_llm_empty"
        except Exception as exc:
            intent_source = "rules_llm_failed"
            llm_meta = {"error": str(exc)}
    elif settings.copilot_llm_nlu_enabled and degrade_reason:
        intent_source = "rules_degraded"
        llm_meta = {"degrade_reason": degrade_reason}
        store.log_copilot_event(
            event_type="degraded_mode",
            telegram_user_id=user_id,
            conversation_id=conversation_id,
            payload={"reason": degrade_reason, "inflight": inflight},
        )

    store.log_conversation_message(
        conversation_id=conversation_id,
        telegram_user_id=user_id,
        direction="user",
        message_text=message_text,
        intent=intent,
        confidence=confidence,
        raw_payload={
            "mode": mode,
            "channel": channel,
            "entities": entities,
            "intent_source": intent_source,
            "degrade_reason": degrade_reason,
        },
    )
    store.log_copilot_event(
        event_type="message_received",
        telegram_user_id=user_id,
        conversation_id=conversation_id,
        payload={
            "mode": mode,
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "intent_source": intent_source,
            "llm": llm_meta,
            "degrade_reason": degrade_reason,
            "inflight": inflight,
        },
    )

    if intent == "domain_check":
        domain = str(entities.get("domain") or "").strip().lower()
        if not domain:
            reply = _t(lang, "domain_missing")
            store.log_conversation_message(
                conversation_id=conversation_id,
                telegram_user_id=user_id,
                direction="assistant",
                message_text=reply,
                intent=intent,
                confidence=confidence,
            )
            await _dec_inflight()
            return CopilotMessageResponse(
                conversation_id=conversation_id,
                reply=reply,
                intent=intent,
                confidence=confidence,
            )

        status, eta = await infer_status(domain, timeweb_client=timeweb_client)
        reply = f"{domain}: status={status}, score={score_domain(domain)}"
        if eta:
            reply += f", eta={eta.isoformat()}"
        store.log_copilot_event(
            event_type="domain_check_result",
            telegram_user_id=user_id,
            conversation_id=conversation_id,
            payload={"domain": domain, "status": status, "eta": eta.isoformat() if eta else None},
        )
        store.log_conversation_message(
            conversation_id=conversation_id,
            telegram_user_id=user_id,
            direction="assistant",
            message_text=reply,
            intent=intent,
            confidence=confidence,
        )
        await _dec_inflight()
        return CopilotMessageResponse(
            conversation_id=conversation_id,
            reply=reply,
            intent=intent,
            confidence=confidence,
        )

    if intent == "domain_suggest":
        raw_query = str(entities.get("query") or "").strip()
        normalized_query = _normalize_suggest_query(raw_query or message_text)
        if len(normalized_query) < 2:
            reply = _t(lang, "domain_suggest_missing")
            store.log_conversation_message(
                conversation_id=conversation_id,
                telegram_user_id=user_id,
                direction="assistant",
                message_text=reply,
                intent=intent,
                confidence=confidence,
            )
            await _dec_inflight()
            return CopilotMessageResponse(
                conversation_id=conversation_id,
                reply=reply,
                intent=intent,
                confidence=confidence,
            )

        tlds = entities.get("tlds") or []
        if not tlds:
            tlds = _parse_tlds_from_settings(settings.monitor_tlds)[:6] or [".com", ".io", ".ai", ".ru"]
        suggest_mode = str(entities.get("suggest_mode") or "prioritized").strip().lower()

        seeds = _build_suggest_seeds(normalized_query)
        candidates = [f"{seed}{tld}" for seed in seeds for tld in tlds][:48]
        query_terms = _suggest_query_terms(raw_query or message_text, normalized_query)
        sem = asyncio.Semaphore(8)

        async def check_one(fqdn: str) -> dict:
            async with sem:
                status, eta = await infer_status(fqdn, timeweb_client=timeweb_client)
                return {
                    "domain": fqdn,
                    "status": status,
                    "score": score_domain(fqdn),
                    "eta": eta.isoformat() if eta else None,
                }

        rows = await asyncio.gather(*(check_one(name) for name in candidates))
        actionable_rows = [item for item in rows if str(item.get("status")) in {"available", "pending_delete", "redemption", "client_hold"}]
        if suggest_mode == "available_only":
            picked_rows = actionable_rows
        else:
            picked_rows = rows if len(actionable_rows) < 8 else actionable_rows
        picked_rows.sort(key=lambda item: _domains_suggest_rank(item, query_terms))
        top = picked_rows[:8]

        lines = [
            f"{item['domain']} | {item['status']} | score {item['score']}"
            + (f" | eta {item['eta']}" if item["eta"] else "")
            for item in top
        ]
        mode_text = _t(lang, "domain_suggest_mode_available_only") if suggest_mode == "available_only" else _t(lang, "domain_suggest_mode_prioritized")
        body = "\n".join(lines) if lines else "-"
        reply = _t(lang, "domain_suggest_header") + "\n" + mode_text + "\n" + body
        store.log_copilot_event(
            event_type="domain_suggest_result",
            telegram_user_id=user_id,
            conversation_id=conversation_id,
            payload={"query": normalized_query, "tlds": tlds, "count": len(top), "suggest_mode": suggest_mode},
        )
        store.log_conversation_message(
            conversation_id=conversation_id,
            telegram_user_id=user_id,
            direction="assistant",
            message_text=reply,
            intent=intent,
            confidence=confidence,
            raw_payload={"query": normalized_query, "tlds": tlds, "top": top, "suggest_mode": suggest_mode},
        )
        await _dec_inflight()
        return CopilotMessageResponse(
            conversation_id=conversation_id,
            reply=reply,
            intent=intent,
            confidence=confidence,
        )

    action = _action_from_intent(intent, entities) if mode == "assistant" else None
    if action:
        action_type, action_payload = action
        if action_type == "register_domain" and not _can_register_domain(user_id):
            reply = _t(lang, "register_domain_forbidden")
            store.log_copilot_event(
                event_type="action_forbidden",
                telegram_user_id=user_id,
                conversation_id=conversation_id,
                payload={"action_type": action_type, "reason": "role_required"},
            )
            store.log_conversation_message(
                conversation_id=conversation_id,
                telegram_user_id=user_id,
                direction="assistant",
                message_text=reply,
                intent=intent,
                confidence=confidence,
                raw_payload={"action_type": action_type, "forbidden": True},
            )
            await _dec_inflight()
            return CopilotMessageResponse(
                conversation_id=conversation_id,
                reply=reply,
                intent=intent,
                confidence=confidence,
                requires_confirmation=False,
            )
        confirmation = store.create_copilot_confirmation(
            telegram_user_id=user_id,
            conversation_id=conversation_id,
            action_type=action_type,
            action_payload=action_payload,
            ttl_minutes=5,
        )
        if not confirmation:
            await _dec_inflight()
            raise HTTPException(status_code=500, detail="failed to prepare confirmation")

        reply = _assistant_text_for_intent_lang(intent, entities, lang)
        store.log_copilot_event(
            event_type="confirmation_requested",
            telegram_user_id=user_id,
            conversation_id=conversation_id,
            confirmation_token=confirmation["confirmation_token"],
            payload={"action_type": action_type, "action_payload": action_payload},
        )
        store.log_conversation_message(
            conversation_id=conversation_id,
            telegram_user_id=user_id,
            direction="assistant",
            message_text=reply,
            intent=intent,
            confidence=confidence,
            raw_payload={"confirmation_token": confirmation["confirmation_token"], "action_type": action_type},
        )
        await _dec_inflight()
        return CopilotMessageResponse(
            conversation_id=conversation_id,
            reply=reply,
            intent=intent,
            confidence=confidence,
            requires_confirmation=True,
            confirmation_token=confirmation["confirmation_token"],
            action_preview=_format_preview(action_type, action_payload),
        )

    reply = _assistant_text_for_intent_lang(intent, entities, lang)
    reply_style = "template"
    answer_source = "template"
    context_used = 0
    trim_reason = None
    if intent in {"help", "qa", "chat"} and settings.copilot_llm_nlu_enabled and not degrade_reason:
        history_limit = max(2, int(settings.copilot_llm_chat_context_messages))
        history = store.list_conversation_messages(
            conversation_id=conversation_id,
            telegram_user_id=user_id,
            limit=history_limit,
        )
        context_used = len(history)
        try:
            async with _LLM_SEMAPHORE:
                llm_reply = await generate_chat_reply_with_llm(
                    message=message_text,
                    intent=intent,
                    lang=lang,
                    history=history,
                )
            if llm_reply and llm_reply.reply:
                reply = llm_reply.reply
                reply_style = "natural"
                answer_source = f"llm:{llm_reply.provider}"
                trim_reason = llm_reply.trim_reason
            else:
                answer_source = "template_llm_empty"
        except Exception as exc:
            answer_source = "template_llm_failed"
            trim_reason = str(exc)[:160]
    elif degrade_reason:
        answer_source = "template_degraded"
        trim_reason = degrade_reason
        reply = _t(lang, "llm_degraded") + "\n" + reply

    store.log_conversation_message(
        conversation_id=conversation_id,
        telegram_user_id=user_id,
        direction="assistant",
        message_text=reply,
        intent=intent,
        confidence=confidence,
        raw_payload={
            "mode": mode,
            "reply_style": reply_style,
            "answer_source": answer_source,
            "context_used": context_used,
            "trim_reason": trim_reason,
        },
    )
    store.log_copilot_event(
        event_type="assistant_reply",
        telegram_user_id=user_id,
        conversation_id=conversation_id,
        payload={
            "intent": intent,
            "confidence": confidence,
            "reply_style": reply_style,
            "answer_source": answer_source,
            "context_used": context_used,
            "trim_reason": trim_reason,
            "degrade_reason": degrade_reason,
        },
    )
    await _dec_inflight()
    return CopilotMessageResponse(
        conversation_id=conversation_id,
        reply=reply,
        intent=intent,
        confidence=confidence,
    )


@router.post("/confirm", response_model=CopilotConfirmResponse)
async def copilot_confirm(payload: CopilotConfirmRequest, request: Request) -> CopilotConfirmResponse:
    user = _require_user(request)
    return await process_copilot_confirm(user.telegram_user_id, payload.confirmation_token, payload.decision)


async def process_copilot_confirm(user_id: str, confirmation_token: str, decision: str = "confirm") -> CopilotConfirmResponse:
    lang = _lang_for_user(user_id)
    decision = str(decision or "confirm").strip().lower()
    if decision not in {"confirm", "cancel"}:
        raise HTTPException(status_code=400, detail="decision must be confirm or cancel")

    item = store.get_copilot_confirmation(confirmation_token, telegram_user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail="confirmation not found")

    if item["status"] != "pending":
        return CopilotConfirmResponse(
            status=item["status"],
            message=_t(lang, "already_done").format(status=item["status"]),
            execution_result=item.get("result_payload") or None,
        )

    try:
        expires_at = datetime.fromisoformat(str(item["expires_at"]))
    except Exception:
        expires_at = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        store.update_copilot_confirmation_status(confirmation_token, "expired", error_message="token expired")
        store.log_copilot_event(
            event_type="confirmation_expired",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=confirmation_token,
            payload={},
        )
        return CopilotConfirmResponse(status="expired", message=_t(lang, "token_expired"))

    if decision == "cancel":
        store.update_copilot_confirmation_status(confirmation_token, "canceled")
        store.log_copilot_event(
            event_type="confirmation_canceled",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=confirmation_token,
            payload={},
        )
        return CopilotConfirmResponse(status="canceled", message=_t(lang, "action_canceled"))

    action_type = str(item["action_type"] or "").strip().lower()
    action_payload = item.get("action_payload") or {}
    execution_result: dict = {}
    try:
        if action_type == "create_watch":
            query = str(action_payload.get("query") or "").strip()
            tlds = action_payload.get("tlds") or []
            rule_id = store.add_watch_rule(
                telegram_user_id=user_id,
                watch_query=query,
                tlds=tlds,
            )
            if not rule_id:
                raise RuntimeError("failed to create watch rule")
            execution_result = {"rule_id": rule_id, "query": query}

        elif action_type == "toggle_alerts":
            enabled = bool(action_payload.get("enabled"))
            profile = store.get_telegram_user(user_id)
            chat_id = profile.telegram_chat_id if profile else None
            ok = store.set_telegram_alerts_enabled(
                telegram_user_id=user_id,
                telegram_chat_id=chat_id,
                enabled=enabled,
            )
            if not ok:
                raise RuntimeError("failed to switch alerts (possibly no profile/chat_id)")
            execution_result = {"enabled": enabled}

        elif action_type == "register_domain":
            if not _can_register_domain(user_id):
                raise PermissionError("role operator/admin/superadmin is required for register_domain")
            domain = str(action_payload.get("domain") or "").strip().lower()
            if not domain:
                raise RuntimeError("domain is empty")
            order = store.create_order(domain)
            from app.routers.registrations import execute_registration

            final = await execute_registration(order.order_id)
            execution_result = {
                "order_id": final.order_id,
                "status": final.status,
                "domain": domain,
                "registrar_response": final.registrar_response,
            }

        else:
            raise RuntimeError(f"unsupported action_type: {action_type}")

        store.update_copilot_confirmation_status(confirmation_token, "executed", result_payload=execution_result)
        store.log_copilot_event(
            event_type="action_executed",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=confirmation_token,
            payload={"action_type": action_type, "result": execution_result},
        )
        return CopilotConfirmResponse(status="executed", message=_t(lang, "action_done"), execution_result=execution_result)
    except Exception as exc:
        error_text = str(exc)
        store.update_copilot_confirmation_status(confirmation_token, "failed", error_message=error_text)
        store.log_copilot_event(
            event_type="action_failed",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=confirmation_token,
            payload={"action_type": action_type, "error": error_text},
        )
        return CopilotConfirmResponse(status="failed", message=error_text, execution_result=execution_result or None)
