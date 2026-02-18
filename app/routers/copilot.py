from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.auth import AuthUserResponse, get_authenticated_user
from app.services.domain_checker import infer_status
from app.services.domain_scoring import score_domain
from app.services.timeweb_api import TimewebApiClient
from app.state import store

router = APIRouter(prefix="/v1/copilot", tags=["copilot"])

timeweb_client = TimewebApiClient(
    base_url=settings.timeweb_api_base_url,
    api_token=settings.timeweb_api_token,
)

DOMAIN_PATTERN = re.compile(r"\b[a-z0-9][a-z0-9-]{0,61}\.[a-z0-9.-]{2,24}\b", re.IGNORECASE)


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


def _require_user(request: Request) -> AuthUserResponse:
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


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
    if intent == "help":
        return (
            "Я могу: объяснить логику сервиса, проверить домен, предложить watch-правило, "
            "включить/выключить алерты и подготовить регистрацию домена с подтверждением."
        )
    if intent == "qa":
        return "Принято. Сформулируйте вопрос подробнее, и я отвечу по данным системы."
    if intent == "chat":
        return "Понял. Можем обсудить идею или задачу; для действий я сначала запрошу подтверждение."
    if intent == "domain_check":
        return "Сейчас проверю домен и верну статус."
    if intent == "create_watch":
        return f"Понял как создание watch-правила: `{entities.get('query')}`. Подтвердите выполнение."
    if intent == "toggle_alerts":
        return "Понял запрос на переключение алертов. Подтвердите выполнение."
    if intent == "register_domain":
        return f"Понял запрос на регистрацию: `{entities.get('domain')}`. Подтвердите выполнение."
    return "Запрос получен."


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
    user_id = user.telegram_user_id
    mode = str(payload.mode or "assistant").strip().lower()
    if mode not in {"ask", "chat", "assistant"}:
        mode = "assistant"

    conversation_id = str(payload.conversation_id or "").strip()
    if conversation_id:
        conversation = store.get_conversation(conversation_id, telegram_user_id=user_id)
        if not conversation:
            conversation_id = ""
    if not conversation_id:
        conversation_id = store.create_conversation(user_id, channel=payload.channel)

    message_text = payload.message.strip()
    intent, confidence, entities = _detect_intent(message_text, mode)
    store.log_conversation_message(
        conversation_id=conversation_id,
        telegram_user_id=user_id,
        direction="user",
        message_text=message_text,
        intent=intent,
        confidence=confidence,
        raw_payload={"mode": mode, "channel": payload.channel, "entities": entities},
    )
    store.log_copilot_event(
        event_type="message_received",
        telegram_user_id=user_id,
        conversation_id=conversation_id,
        payload={"mode": mode, "intent": intent, "confidence": confidence, "entities": entities},
    )

    if intent == "domain_check":
        domain = str(entities.get("domain") or "").strip().lower()
        if not domain:
            reply = "Не вижу домен в запросе. Пример: `проверь freebrand.com`."
            store.log_conversation_message(
                conversation_id=conversation_id,
                telegram_user_id=user_id,
                direction="assistant",
                message_text=reply,
                intent=intent,
                confidence=confidence,
            )
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
        return CopilotMessageResponse(
            conversation_id=conversation_id,
            reply=reply,
            intent=intent,
            confidence=confidence,
        )

    action = _action_from_intent(intent, entities) if mode == "assistant" else None
    if action:
        action_type, action_payload = action
        confirmation = store.create_copilot_confirmation(
            telegram_user_id=user_id,
            conversation_id=conversation_id,
            action_type=action_type,
            action_payload=action_payload,
            ttl_minutes=5,
        )
        if not confirmation:
            raise HTTPException(status_code=500, detail="failed to prepare confirmation")

        reply = _assistant_text_for_intent(intent, entities)
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
        return CopilotMessageResponse(
            conversation_id=conversation_id,
            reply=reply,
            intent=intent,
            confidence=confidence,
            requires_confirmation=True,
            confirmation_token=confirmation["confirmation_token"],
            action_preview=_format_preview(action_type, action_payload),
        )

    reply = _assistant_text_for_intent(intent, entities)
    store.log_conversation_message(
        conversation_id=conversation_id,
        telegram_user_id=user_id,
        direction="assistant",
        message_text=reply,
        intent=intent,
        confidence=confidence,
        raw_payload={"mode": mode},
    )
    store.log_copilot_event(
        event_type="assistant_reply",
        telegram_user_id=user_id,
        conversation_id=conversation_id,
        payload={"intent": intent, "confidence": confidence},
    )
    return CopilotMessageResponse(
        conversation_id=conversation_id,
        reply=reply,
        intent=intent,
        confidence=confidence,
    )


@router.post("/confirm", response_model=CopilotConfirmResponse)
async def copilot_confirm(payload: CopilotConfirmRequest, request: Request) -> CopilotConfirmResponse:
    user = _require_user(request)
    user_id = user.telegram_user_id
    decision = str(payload.decision or "confirm").strip().lower()
    if decision not in {"confirm", "cancel"}:
        raise HTTPException(status_code=400, detail="decision must be confirm or cancel")

    item = store.get_copilot_confirmation(payload.confirmation_token, telegram_user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail="confirmation not found")

    if item["status"] != "pending":
        return CopilotConfirmResponse(
            status=item["status"],
            message=f"Запрос уже обработан: {item['status']}",
            execution_result=item.get("result_payload") or None,
        )

    try:
        expires_at = datetime.fromisoformat(str(item["expires_at"]))
    except Exception:
        expires_at = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        store.update_copilot_confirmation_status(payload.confirmation_token, "expired", error_message="token expired")
        store.log_copilot_event(
            event_type="confirmation_expired",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=payload.confirmation_token,
            payload={},
        )
        return CopilotConfirmResponse(status="expired", message="Срок подтверждения истек.")

    if decision == "cancel":
        store.update_copilot_confirmation_status(payload.confirmation_token, "canceled")
        store.log_copilot_event(
            event_type="confirmation_canceled",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=payload.confirmation_token,
            payload={},
        )
        return CopilotConfirmResponse(status="canceled", message="Действие отменено.")

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

        store.update_copilot_confirmation_status(payload.confirmation_token, "executed", result_payload=execution_result)
        store.log_copilot_event(
            event_type="action_executed",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=payload.confirmation_token,
            payload={"action_type": action_type, "result": execution_result},
        )
        return CopilotConfirmResponse(status="executed", message="Действие выполнено.", execution_result=execution_result)
    except Exception as exc:
        error_text = str(exc)
        store.update_copilot_confirmation_status(payload.confirmation_token, "failed", error_message=error_text)
        store.log_copilot_event(
            event_type="action_failed",
            telegram_user_id=user_id,
            conversation_id=item["conversation_id"],
            confirmation_token=payload.confirmation_token,
            payload={"action_type": action_type, "error": error_text},
        )
        return CopilotConfirmResponse(status="failed", message=error_text, execution_result=execution_result or None)
