from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from app.config import settings
from app.services.domain_checker import infer_status
from app.services.domain_scoring import score_domain
from app.services.notifications import (
    build_confirmation_token,
    send_max_alert,
    send_telegram_alert,
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
            for reason in ("same_domain", "user_never")
        )

    async def run_once(self) -> dict:
        if self._run_once_lock.locked():
            return {
                "checked": 0,
                "alerts_sent": 0,
                "skipped": "already_running",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        async with self._run_once_lock:
            global_candidates = self._build_candidates()
            watch_targets = self.store.list_active_watch_targets()
            admin_user_ids = self._admin_user_ids()
            admin_chat_ids = self.store.list_telegram_chats_by_user_ids(admin_user_ids)
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
            interesting_statuses = self._alert_statuses()
            alerts_sent = 0
            global_run_limit = max(1, int(settings.monitor_alert_global_run_limit))
            per_target_sent: dict[tuple[str, str], int] = {}
            per_target_daily_sent: dict[tuple[str, str], int] = {}
            per_target_run_limit = max(1, settings.monitor_alert_per_target_run_limit)
            per_target_daily_limit = max(per_target_run_limit, settings.monitor_alert_per_target_daily_limit)
            per_target_lock = asyncio.Lock()
            def dynamic_run_limit(daily_sent: int) -> int:
                threshold = int(per_target_daily_limit * 0.8)
                if daily_sent >= threshold:
                    return 1
                return per_target_run_limit

            sem = asyncio.Semaphore(12)

            async def process_domain(fqdn: str) -> None:
                nonlocal alerts_sent
                async with sem:
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

                    if status not in interesting_statuses:
                        return

                    # Global fallback channel behavior (legacy).
                    if score >= settings.monitor_alert_min_score and (settings.telegram_chat_id or settings.max_chat_id):
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
                                        destination = ""
                                    elif self._is_alert_suppressed(fqdn, destination):
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
                                            destination = ""
                                        elif per_target_daily_sent[destination_key] >= per_target_daily_limit:
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

                    # Personalized monitoring by active watch-rules and subscriptions.
                    sent_keys: set[tuple[str, str]] = set()
                    for target in watch_targets:
                        rule_id = str(target.get("rule_id"))
                        if fqdn not in rule_candidates_map.get(rule_id, []):
                            continue
                        if not self._query_matches_domain(str(target.get("query") or ""), fqdn):
                            continue
                        min_score = target.get("min_score")
                        if min_score is not None and score < float(min_score):
                            continue
                        max_length = target.get("max_length")
                        if max_length is not None and len(fqdn.split(".", 1)[0]) > int(max_length):
                            continue

                        channel_type = str(target.get("channel_type") or "").lower()
                        channel_target = str(target.get("channel_target") or "").strip()
                        if channel_type not in {"telegram", "max"} or not channel_target:
                            continue
                        key = (channel_type, channel_target)
                        if key in sent_keys:
                            continue
                        async with per_target_lock:
                            target_daily_limit = max(
                                1,
                                min(int(target.get("daily_alert_limit") or per_target_daily_limit), 10),
                            )
                            if alerts_sent >= global_run_limit:
                                continue
                            if key not in per_target_daily_sent:
                                per_target_daily_sent[key] = self.store.count_recent_alerts_for_destination(
                                    channel_target,
                                    within_hours=24,
                                    alert_type_prefix="watch_rule_match",
                                )
                            effective_limit = 1 if per_target_daily_sent[key] >= int(target_daily_limit * 0.8) else per_target_run_limit
                            if per_target_sent.get(key, 0) >= effective_limit:
                                continue
                            if per_target_daily_sent[key] >= target_daily_limit:
                                continue
                            if self.store.has_recent_alert_for_destination(
                                fqdn,
                                destination=channel_target,
                                within_minutes=settings.monitor_alert_cooldown_minutes,
                            ):
                                continue
                            if self._is_alert_suppressed(fqdn, channel_target):
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
                            await send_telegram_alert(channel_target, fqdn, token, explanation=explanation)
                        else:
                            await send_max_alert(channel_target, fqdn, token)
                        self.store.suppress_alert(fqdn, channel_target, reason="same_domain", days=30)

                        sent_keys.add(key)

                    # Admin fan-out: deliver a copy of every interesting event to configured admin chats.
                    for admin_chat_id in admin_chat_ids:
                        key = ("telegram", str(admin_chat_id))
                        if key in sent_keys:
                            continue
                        async with per_target_lock:
                            if alerts_sent >= global_run_limit:
                                continue
                            if key not in per_target_daily_sent:
                                per_target_daily_sent[key] = self.store.count_recent_alerts_for_destination(
                                    admin_chat_id,
                                    within_hours=24,
                                    alert_type_prefix="admin_fanout",
                                )
                            effective_limit = dynamic_run_limit(per_target_daily_sent[key])
                            if per_target_sent.get(key, 0) >= effective_limit:
                                continue
                            if per_target_daily_sent[key] >= per_target_daily_limit:
                                continue
                            if self.store.has_recent_alert_for_destination(
                                fqdn,
                                destination=admin_chat_id,
                                within_minutes=settings.monitor_alert_cooldown_minutes,
                            ):
                                continue
                            if self._is_alert_suppressed(fqdn, admin_chat_id):
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
                        sent_keys.add(key)

            await asyncio.gather(*(process_domain(fqdn) for fqdn in candidates))

            return {
                "checked": len(candidates),
                "alerts_sent": alerts_sent,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }

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
