from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.services.domain_checker import infer_status
from app.services.domain_scoring import score_domain
from app.services.notifications import (
    build_confirmation_token,
    send_max_alert,
    send_telegram_alert,
    send_telegram_digest,
)
from app.services.store import PostgresStore
from app.services.timeweb_api import TimewebApiClient


class DomainMonitoringService:
    def __init__(self, store: PostgresStore) -> None:
        self.store = store
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._run_once_lock = asyncio.Lock()
        self.timeweb_client = TimewebApiClient(
            base_url=settings.timeweb_api_base_url,
            api_token=settings.timeweb_api_token,
        )

    @staticmethod
    def _parse_csv(raw: str) -> list[str]:
        return [item.strip().lower() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _query_tokens(query: str, min_len: int = 3) -> list[str]:
        generic = {"ai", "io", "com", "net", "ru", "www", "app"}
        return [
            part
            for part in re.split(r"[^a-z0-9]+", query.lower())
            if len(part) >= min_len and part not in generic
        ]

    @staticmethod
    def _sanitize_seed_words(words: list[str]) -> list[str]:
        generic = {"ai", "io", "com", "net", "ru", "app", "web", "www"}
        return [word for word in words if len(word) >= 3 and word not in generic]

    def _build_candidates(self) -> list[str]:
        tlds = self._parse_csv(settings.monitor_tlds)
        seeds = self._sanitize_seed_words(self._parse_csv(settings.monitor_seed_words))
        words: set[str] = set(seeds)

        # Basic brand-like expansions to improve recall in MVP.
        for seed in seeds:
            words.add(f"{seed}ai")
            words.add(f"{seed}lab")
            words.add(f"{seed}hub")
            words.add(f"my{seed}")

        candidates = [f"{word}{tld}" for word in sorted(words) for tld in tlds]
        return candidates

    def _build_query_candidates(self, query: str, tlds: list[str]) -> list[str]:
        words = self._query_tokens(query, min_len=3)
        if not words:
            return []

        seeds: set[str] = set(words[:3])
        for word in words[:3]:
            seeds.add(f"{word}ai")
            seeds.add(f"{word}lab")
            seeds.add(f"{word}hub")
            seeds.add(f"my{word}")
        return [f"{seed}{tld}" for seed in sorted(seeds) for tld in tlds]

    @staticmethod
    def _alert_statuses() -> set[str]:
        raw = (settings.monitor_alert_statuses or "").strip().lower()
        if not raw:
            return {"available", "pending_delete"}
        values = {item.strip().replace(" ", "_") for item in raw.split(",") if item.strip()}
        return values or {"available", "pending_delete"}

    @staticmethod
    def _admin_user_ids() -> list[str]:
        raw = (settings.telegram_admin_user_ids or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _query_matches_domain(query: str, fqdn: str) -> bool:
        name = fqdn.split(".", 1)[0].lower()
        words = DomainMonitoringService._query_tokens(query, min_len=3)
        if not words:
            return False
        return any(word in name for word in words)

    @staticmethod
    def _build_alert_explanation(
        fqdn: str,
        status: str,
        score: float,
        provider: str,
        matched_query: str | None,
    ) -> dict:
        name, _, tld = fqdn.partition(".")
        return {
            "score": round(float(score), 2),
            "status": status,
            "provider": provider,
            "matched_query": matched_query,
            "tld": tld,
            "length": len(name),
            "risk": "provider_check_required" if provider == "heuristic" else "provider_checked",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _is_alert_suppressed(self, fqdn: str, destination: str) -> bool:
        return any(
            self.store.should_suppress_alert(fqdn, destination, reason=reason)
            for reason in ("same_domain", "user_less", "user_never")
        )

    def _log_monitor_event(
        self,
        event_type: str,
        payload: dict,
        telegram_user_id: str | None = None,
        telegram_chat_id: str | None = None,
    ) -> None:
        if not settings.monitor_event_logging_enabled:
            return
        try:
            self.store.log_bot_event(
                event_type,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                payload=payload,
            )
        except Exception:
            # Monitoring must not stop because audit logging is temporarily unavailable.
            pass

    async def run_once(self) -> dict:
        run_id = str(uuid.uuid4())
        if self._run_once_lock.locked():
            self._log_monitor_event(
                "monitor_run_skipped",
                {
                    "run_id": run_id,
                    "reason": "already_running",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return {
                "checked": 0,
                "alerts_sent": 0,
                "skipped": "already_running",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        async with self._run_once_lock:
            started_at = datetime.now(timezone.utc).isoformat()
            watchlist_only = bool(settings.monitor_watchlist_only)
            admin_fanout_enabled = bool(settings.monitor_admin_fanout_enabled)
            digest_enabled = bool(settings.monitor_digest_enabled)
            detail_logging = bool(settings.monitor_event_logging_detail)
            self._log_monitor_event(
                "monitor_run_started",
                {
                    "run_id": run_id,
                    "started_at": started_at,
                    "watchlist_only": watchlist_only,
                    "admin_fanout_enabled": admin_fanout_enabled,
                    "global_run_limit": settings.monitor_alert_global_run_limit,
                    "per_target_run_limit": settings.monitor_alert_per_target_run_limit,
                    "per_target_daily_limit": settings.monitor_alert_per_target_daily_limit,
                    "cooldown_minutes": settings.monitor_alert_cooldown_minutes,
                    "require_provider_check": settings.monitor_require_provider_check,
                    "digest_enabled": digest_enabled,
                    "detail_logging": detail_logging,
                },
            )
            global_candidates = [] if watchlist_only else self._build_candidates()
            watch_targets = self.store.list_active_watch_targets()
            admin_user_ids = self._admin_user_ids()
            admin_chat_ids = (
                self.store.list_telegram_chats_by_user_ids(admin_user_ids)
                if admin_fanout_enabled
                else []
            )
            rule_candidates_map: dict[str, list[str]] = {}
            personal_candidates: set[str] = set()

            default_tlds = self._parse_csv(settings.monitor_tlds)
            for target in watch_targets:
                tlds = [str(item).strip().lower() for item in (target.get("tlds") or []) if str(item).strip()]
                tlds = tlds or default_tlds
                query = str(target.get("query") or "").strip()
                if not query:
                    continue
                rc = self._build_query_candidates(query, tlds[:8])
                if not rc:
                    continue
                rule_candidates_map[str(target["rule_id"])] = rc
                personal_candidates.update(rc)

            candidates = sorted(set(global_candidates) | personal_candidates)
            self._log_monitor_event(
                "monitor_candidates_built",
                {
                    "run_id": run_id,
                    "global_candidates_count": len(global_candidates),
                    "personal_candidates_count": len(personal_candidates),
                    "candidates_count": len(candidates),
                    "watch_targets_count": len(watch_targets),
                    "admin_chat_ids_count": len(admin_chat_ids),
                    "watchlist_only": watchlist_only,
                    "admin_fanout_enabled": admin_fanout_enabled,
                },
            )
            interesting_statuses = self._alert_statuses()
            alerts_sent = 0
            status_counts: dict[str, int] = {}
            skip_reasons: dict[str, int] = {}
            global_run_limit = max(1, int(settings.monitor_alert_global_run_limit))
            per_target_sent: dict[tuple[str, str], int] = {}
            per_target_daily_sent: dict[tuple[str, str], int] = {}
            per_target_cooldown_active: dict[tuple[str, str], bool] = {}
            per_target_run_limit = max(1, settings.monitor_alert_per_target_run_limit)
            per_target_daily_limit = max(per_target_run_limit, settings.monitor_alert_per_target_daily_limit)
            per_target_cooldown_minutes = max(0, int(settings.monitor_alert_target_cooldown_minutes))
            per_target_lock = asyncio.Lock()
            digest_items: dict[str, list[dict]] = {}
            digest_lock = asyncio.Lock()
            def dynamic_run_limit(daily_sent: int) -> int:
                threshold = int(per_target_daily_limit * 0.8)
                if daily_sent >= threshold:
                    return 1
                return per_target_run_limit

            sem = asyncio.Semaphore(12)

            def log_skip(fqdn: str, reason: str, payload: dict | None = None) -> None:
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                if detail_logging:
                    self._log_monitor_event(
                        "monitor_alert_skipped",
                        {"run_id": run_id, "fqdn": fqdn, "reason": reason, **(payload or {})},
                    )

            async def process_domain(fqdn: str) -> None:
                nonlocal alerts_sent
                async with sem:
                    try:
                        status, eta = await infer_status(
                            fqdn,
                            timeweb_client=self.timeweb_client,
                            allow_heuristic_fallback=not settings.monitor_require_provider_check,
                        )
                        score = score_domain(fqdn)
                        provider = "timeweb" if self.timeweb_client.is_configured else "heuristic"
                        self.store.upsert_domain_snapshot(
                            fqdn=fqdn,
                            status=status,
                            score=score,
                            drop_time_estimated_at=eta,
                            source="monitor",
                            provider=provider,
                        )
                        status_counts[str(status)] = status_counts.get(str(status), 0) + 1
                        if detail_logging:
                            self._log_monitor_event(
                                "monitor_candidate_checked",
                                {
                                    "run_id": run_id,
                                    "fqdn": fqdn,
                                    "status": status,
                                    "score": round(float(score), 2),
                                    "provider": provider,
                                    "drop_time_estimated_at": eta.isoformat() if eta else None,
                                },
                            )
                    except Exception as exc:
                        self._log_monitor_event(
                            "monitor_candidate_error",
                            {"run_id": run_id, "fqdn": fqdn, "error": str(exc)},
                        )
                        raise

                    if status not in interesting_statuses:
                        log_skip(fqdn, "status_not_interesting", {"status": status})
                        return

                    # Global fallback channel behavior (legacy).
                    if (
                        not watchlist_only
                        and score >= settings.monitor_alert_min_score
                        and (settings.telegram_chat_id or settings.max_chat_id)
                    ):
                        if not self.store.has_recent_alert(fqdn, within_minutes=settings.monitor_alert_cooldown_minutes):
                            token = build_confirmation_token()
                            destination = settings.telegram_chat_id or settings.max_chat_id
                            if destination:
                                destination_key = (
                                    "telegram" if settings.telegram_chat_id else "max",
                                    destination,
                                )
                                explanation = self._build_alert_explanation(
                                    fqdn=fqdn,
                                    status=status,
                                    score=score,
                                    provider=provider,
                                    matched_query=None,
                                )
                                async with per_target_lock:
                                    if alerts_sent >= global_run_limit:
                                        log_skip(fqdn, "global_run_limit", {"destination": destination})
                                        destination = ""
                                    elif self._is_alert_suppressed(fqdn, destination):
                                        log_skip(fqdn, "suppressed", {"destination": destination, "scope": "global"})
                                        destination = ""
                                    else:
                                        if destination_key not in per_target_daily_sent:
                                            per_target_daily_sent[destination_key] = self.store.count_recent_alerts_for_destination(
                                                destination,
                                                within_hours=24,
                                                alert_type_prefix="monitor_match",
                                            )
                                        effective_limit = dynamic_run_limit(per_target_daily_sent[destination_key])
                                        if per_target_sent.get(destination_key, 0) >= effective_limit:
                                            log_skip(fqdn, "per_target_run_limit", {"destination": destination, "scope": "global"})
                                            destination = ""
                                        elif per_target_daily_sent[destination_key] >= per_target_daily_limit:
                                            log_skip(fqdn, "per_target_daily_limit", {"destination": destination, "scope": "global"})
                                            destination = ""
                                        else:
                                            per_target_sent[destination_key] = per_target_sent.get(destination_key, 0) + 1
                                            per_target_daily_sent[destination_key] += 1
                                            alerts_sent += 1
                                if destination:
                                    self.store.create_alert(
                                        domain=fqdn,
                                        telegram_chat_id=destination,
                                        token=token,
                                        alert_type="monitor_match",
                                        explanation=explanation,
                                    )
                                    if settings.telegram_chat_id:
                                        await send_telegram_alert(settings.telegram_chat_id, fqdn, token, explanation=explanation)
                                    if settings.max_chat_id:
                                        await send_max_alert(settings.max_chat_id, fqdn, token)
                                    self.store.suppress_alert(fqdn, destination, reason="same_domain", days=30)
                                    self._log_monitor_event(
                                        "monitor_alert_sent",
                                        {
                                            "run_id": run_id,
                                            "fqdn": fqdn,
                                            "destination": destination,
                                            "channel_type": "telegram" if settings.telegram_chat_id else "max",
                                            "alert_type": "monitor_match",
                                            "token": token,
                                            "explanation": explanation,
                                        },
                                        telegram_chat_id=destination if settings.telegram_chat_id else None,
                                    )
                        else:
                            log_skip(fqdn, "recent_alert", {"scope": "global"})
                    elif not watchlist_only and score < settings.monitor_alert_min_score:
                        log_skip(fqdn, "score_below_global_threshold", {"score": round(float(score), 2)})

                    # Personalized monitoring by active watch-rules and subscriptions.
                    sent_keys: set[tuple[str, str]] = set()
                    for target in watch_targets:
                        rule_id = str(target.get("rule_id"))
                        if fqdn not in rule_candidates_map.get(rule_id, []):
                            continue
                        if not self._query_matches_domain(str(target.get("query") or ""), fqdn):
                            log_skip(
                                fqdn,
                                "watch_query_mismatch",
                                {"rule_id": rule_id, "query": str(target.get("query") or "")},
                            )
                            continue
                        min_score = target.get("min_score")
                        if min_score is not None and score < float(min_score):
                            log_skip(
                                fqdn,
                                "watch_min_score",
                                {"rule_id": rule_id, "score": round(float(score), 2), "min_score": float(min_score)},
                            )
                            continue
                        max_length = target.get("max_length")
                        if max_length is not None and len(fqdn.split(".", 1)[0]) > int(max_length):
                            log_skip(
                                fqdn,
                                "watch_max_length",
                                {"rule_id": rule_id, "max_length": int(max_length)},
                            )
                            continue

                        channel_type = str(target.get("channel_type") or "").lower()
                        channel_target = str(target.get("channel_target") or "").strip()
                        if channel_type not in {"telegram", "max"} or not channel_target:
                            log_skip(fqdn, "watch_invalid_channel", {"rule_id": rule_id, "channel_type": channel_type})
                            continue
                        key = (channel_type, channel_target)
                        if key in sent_keys:
                            log_skip(fqdn, "watch_duplicate_destination", {"rule_id": rule_id, "channel_target": channel_target})
                            continue
                        async with per_target_lock:
                            target_daily_limit = max(
                                1,
                                min(int(target.get("daily_alert_limit") or per_target_daily_limit), 10),
                            )
                            if alerts_sent >= global_run_limit:
                                log_skip(fqdn, "global_run_limit", {"rule_id": rule_id, "channel_target": channel_target})
                                continue
                            if key not in per_target_daily_sent:
                                per_target_daily_sent[key] = self.store.count_recent_alerts_for_destination(
                                    channel_target,
                                    within_hours=24,
                                    alert_type_prefix="watch_rule_match",
                                )
                            if key not in per_target_cooldown_active:
                                per_target_cooldown_active[key] = (
                                    per_target_cooldown_minutes > 0
                                    and self.store.has_recent_alert_for_destination_type(
                                        channel_target,
                                        within_minutes=per_target_cooldown_minutes,
                                        alert_type_prefix="watch_rule_match",
                                    )
                                )
                            effective_limit = 1 if per_target_daily_sent[key] >= int(target_daily_limit * 0.8) else per_target_run_limit
                            if per_target_sent.get(key, 0) >= effective_limit:
                                log_skip(fqdn, "per_target_run_limit", {"rule_id": rule_id, "channel_target": channel_target})
                                continue
                            if per_target_daily_sent[key] >= target_daily_limit:
                                log_skip(fqdn, "watch_daily_limit", {"rule_id": rule_id, "channel_target": channel_target})
                                continue
                            if per_target_cooldown_active[key]:
                                log_skip(
                                    fqdn,
                                    "target_cooldown",
                                    {
                                        "rule_id": rule_id,
                                        "channel_target": channel_target,
                                        "cooldown_minutes": per_target_cooldown_minutes,
                                    },
                                )
                                continue
                            if self.store.has_recent_alert_for_destination(
                                fqdn,
                                destination=channel_target,
                                within_minutes=settings.monitor_alert_cooldown_minutes,
                            ):
                                log_skip(fqdn, "recent_alert", {"rule_id": rule_id, "channel_target": channel_target})
                                continue
                            if self._is_alert_suppressed(fqdn, channel_target):
                                log_skip(fqdn, "suppressed", {"rule_id": rule_id, "channel_target": channel_target})
                                continue
                            per_target_sent[key] = per_target_sent.get(key, 0) + 1
                            per_target_daily_sent[key] += 1
                            alerts_sent += 1

                        token = build_confirmation_token()
                        explanation = self._build_alert_explanation(
                            fqdn=fqdn,
                            status=status,
                            score=score,
                            provider=provider,
                            matched_query=str(target.get("query") or "") or None,
                        )
                        self.store.create_alert(
                            domain=fqdn,
                            telegram_chat_id=channel_target,
                            token=token,
                            alert_type=f"watch_rule_match:{rule_id}",
                            explanation=explanation,
                        )

                        if channel_type == "telegram":
                            if digest_enabled:
                                async with digest_lock:
                                    digest_items.setdefault(channel_target, []).append(
                                        {
                                            "domain": fqdn,
                                            "token": token,
                                            "rule_id": rule_id,
                                            "explanation": explanation,
                                        }
                                    )
                            else:
                                await send_telegram_alert(channel_target, fqdn, token, explanation=explanation)
                        else:
                            await send_max_alert(channel_target, fqdn, token)
                        self.store.suppress_alert(fqdn, channel_target, reason="same_domain", days=30)
                        self._log_monitor_event(
                            "monitor_alert_sent",
                            {
                                "run_id": run_id,
                                "fqdn": fqdn,
                                "destination": channel_target,
                                "channel_type": channel_type,
                                "alert_type": f"watch_rule_match:{rule_id}",
                                "rule_id": rule_id,
                                "token": token,
                                "explanation": explanation,
                            },
                            telegram_user_id=str(target.get("telegram_user_id") or "") or None,
                            telegram_chat_id=channel_target if channel_type == "telegram" else None,
                        )

                        sent_keys.add(key)

                    # Admin fan-out: deliver a copy of every interesting event to configured admin chats.
                    for admin_chat_id in admin_chat_ids:
                        key = ("telegram", str(admin_chat_id))
                        if key in sent_keys:
                            continue
                        async with per_target_lock:
                            if alerts_sent >= global_run_limit:
                                log_skip(fqdn, "global_run_limit", {"admin_chat_id": admin_chat_id, "scope": "admin_fanout"})
                                continue
                            if key not in per_target_daily_sent:
                                per_target_daily_sent[key] = self.store.count_recent_alerts_for_destination(
                                    admin_chat_id,
                                    within_hours=24,
                                    alert_type_prefix="admin_fanout",
                                )
                            effective_limit = dynamic_run_limit(per_target_daily_sent[key])
                            if per_target_sent.get(key, 0) >= effective_limit:
                                log_skip(fqdn, "per_target_run_limit", {"admin_chat_id": admin_chat_id, "scope": "admin_fanout"})
                                continue
                            if per_target_daily_sent[key] >= per_target_daily_limit:
                                log_skip(fqdn, "per_target_daily_limit", {"admin_chat_id": admin_chat_id, "scope": "admin_fanout"})
                                continue
                            if self.store.has_recent_alert_for_destination(
                                fqdn,
                                destination=admin_chat_id,
                                within_minutes=settings.monitor_alert_cooldown_minutes,
                            ):
                                log_skip(fqdn, "recent_alert", {"admin_chat_id": admin_chat_id, "scope": "admin_fanout"})
                                continue
                            if self._is_alert_suppressed(fqdn, admin_chat_id):
                                log_skip(fqdn, "suppressed", {"admin_chat_id": admin_chat_id, "scope": "admin_fanout"})
                                continue
                            per_target_sent[key] = per_target_sent.get(key, 0) + 1
                            per_target_daily_sent[key] += 1
                            alerts_sent += 1

                        token = build_confirmation_token()
                        explanation = self._build_alert_explanation(
                            fqdn=fqdn,
                            status=status,
                            score=score,
                            provider=provider,
                            matched_query=None,
                        )
                        self.store.create_alert(
                            domain=fqdn,
                            telegram_chat_id=admin_chat_id,
                            token=token,
                            alert_type="admin_fanout",
                            explanation=explanation,
                        )
                        await send_telegram_alert(admin_chat_id, fqdn, token, explanation=explanation)
                        self.store.suppress_alert(fqdn, admin_chat_id, reason="same_domain", days=30)
                        self._log_monitor_event(
                            "monitor_alert_sent",
                            {
                                "run_id": run_id,
                                "fqdn": fqdn,
                                "destination": admin_chat_id,
                                "channel_type": "telegram",
                                "alert_type": "admin_fanout",
                                "token": token,
                                "explanation": explanation,
                            },
                            telegram_chat_id=admin_chat_id,
                        )
                        sent_keys.add(key)

            try:
                await asyncio.gather(*(process_domain(fqdn) for fqdn in candidates))
                for chat_id, items in digest_items.items():
                    sorted_items = sorted(
                        items,
                        key=lambda item: float((item.get("explanation") or {}).get("score") or 0),
                        reverse=True,
                    )[:5]
                    delivery = await send_telegram_digest(chat_id, sorted_items)
                    self._log_monitor_event(
                        "monitor_digest_sent",
                        {
                            "run_id": run_id,
                            "destination": chat_id,
                            "items_count": len(sorted_items),
                            "domains": [str(item.get("domain") or "") for item in sorted_items],
                            "delivery": delivery,
                        },
                        telegram_chat_id=chat_id,
                    )
            except Exception as exc:
                self._log_monitor_event(
                    "monitor_run_failed",
                    {
                        "run_id": run_id,
                        "error": str(exc),
                        "checked": len(candidates),
                        "alerts_sent": alerts_sent,
                        "status_counts": dict(sorted(status_counts.items())),
                        "skip_reasons": dict(sorted(skip_reasons.items())),
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise

            result = {
                "checked": len(candidates),
                "alerts_sent": alerts_sent,
                "status_counts": dict(sorted(status_counts.items())),
                "skip_reasons": dict(sorted(skip_reasons.items())),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self._log_monitor_event("monitor_run_finished", {"run_id": run_id, **result})
            return result

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                # Keep loop alive; errors are visible in container logs.
                pass

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=settings.monitor_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def start(self) -> None:
        if not settings.monitor_enabled:
            return
        if self._task and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="domain-monitor")

    async def stop(self) -> None:
        if not self._task:
            return

        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
