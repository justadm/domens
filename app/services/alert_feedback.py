from __future__ import annotations

import re
from typing import Any


def _normalize_query(raw: str) -> str:
    value = re.sub(r"\s+", " ", raw.strip().lower())
    return value[:256]


def _domain_label(domain: str) -> str:
    return str(domain).strip().lower().split(".", 1)[0].replace("-", " ")


def _domain_tld(domain: str, explanation: dict | None) -> str | None:
    raw_tld = str((explanation or {}).get("tld") or "").strip().lower().lstrip(".")
    if not raw_tld and "." in str(domain):
        raw_tld = str(domain).rsplit(".", 1)[1].strip().lower().lstrip(".")
    if not raw_tld:
        return None
    return f".{raw_tld}"


def more_feedback_watch_spec(domain: str, explanation: dict | None) -> dict[str, Any] | None:
    matched_query = str((explanation or {}).get("matched_query") or "").strip()
    query = _normalize_query(matched_query or _domain_label(domain))
    if len(query) < 2:
        return None

    tld = _domain_tld(domain, explanation)
    return {
        "query": query,
        "tlds": [tld] if tld else [],
        "daily_alert_limit": 1,
    }


def _same_watch_rule(existing: dict, query: str, tlds: list[str]) -> bool:
    if str(existing.get("status") or "").lower() == "deleted":
        return False
    if _normalize_query(str(existing.get("query") or "")) != query:
        return False
    existing_tlds = {str(item).strip().lower() for item in (existing.get("tlds") or []) if str(item).strip()}
    requested_tlds = {str(item).strip().lower() for item in tlds if str(item).strip()}
    return not requested_tlds or not existing_tlds or bool(existing_tlds & requested_tlds)


def ensure_more_feedback_watch_rule(
    store: Any,
    telegram_user_id: str,
    domain: str,
    explanation: dict | None,
) -> dict[str, Any] | None:
    spec = more_feedback_watch_spec(domain, explanation)
    if not spec:
        return None

    existing_rules = store.list_watch_rules(telegram_user_id)
    for item in existing_rules:
        if _same_watch_rule(item, spec["query"], spec["tlds"]):
            return {
                "created": False,
                "rule_id": str(item.get("id") or ""),
                **spec,
            }

    rule_id = store.add_watch_rule(
        telegram_user_id,
        watch_query=spec["query"],
        tlds=spec["tlds"],
        daily_alert_limit=spec["daily_alert_limit"],
    )
    if not rule_id:
        return None
    return {
        "created": True,
        "rule_id": str(rule_id),
        **spec,
    }
