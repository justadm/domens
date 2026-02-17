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
        self.timeweb_client = TimewebApiClient(
            base_url=settings.timeweb_api_base_url,
            api_token=settings.timeweb_api_token,
        )

    @staticmethod
    def _parse_csv(raw: str) -> list[str]:
        return [item.strip().lower() for item in raw.split(",") if item.strip()]

    def _build_candidates(self) -> list[str]:
        tlds = self._parse_csv(settings.monitor_tlds)
        seeds = self._parse_csv(settings.monitor_seed_words)
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
        words = [part for part in re.split(r"[^a-z0-9]+", query.lower()) if len(part) >= 2]
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
    def _query_matches_domain(query: str, fqdn: str) -> bool:
        name = fqdn.split(".", 1)[0].lower()
        words = [part for part in re.split(r"[^a-z0-9]+", query.lower()) if len(part) >= 2]
        if not words:
            return False
        return any(word in name for word in words)

    async def run_once(self) -> dict:
        global_candidates = self._build_candidates()
        watch_targets = self.store.list_active_watch_targets()
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
        interesting_statuses = {"available", "pending_delete", "redemption", "client_hold"}
        alerts_sent = 0
        per_target_sent: dict[tuple[str, str], int] = {}
        per_target_run_limit = 5
        per_target_lock = asyncio.Lock()

        sem = asyncio.Semaphore(12)

        async def process_domain(fqdn: str) -> None:
            nonlocal alerts_sent
            async with sem:
                status, eta = await infer_status(fqdn, timeweb_client=self.timeweb_client)
                score = score_domain(fqdn)
                self.store.upsert_domain_snapshot(
                    fqdn=fqdn,
                    status=status,
                    score=score,
                    drop_time_estimated_at=eta,
                    source="monitor",
                    provider="timeweb" if self.timeweb_client.is_configured else "heuristic",
                )

                if status not in interesting_statuses:
                    return

                # Global fallback channel behavior (legacy).
                if score >= settings.monitor_alert_min_score and (settings.telegram_chat_id or settings.max_chat_id):
                    if not self.store.has_recent_alert(fqdn, within_minutes=settings.monitor_alert_cooldown_minutes):
                        token = build_confirmation_token()
                        destination = settings.telegram_chat_id or settings.max_chat_id
                        self.store.create_alert(
                            domain=fqdn,
                            telegram_chat_id=destination,
                            token=token,
                            alert_type="monitor_match",
                        )
                        if settings.telegram_chat_id:
                            await send_telegram_alert(settings.telegram_chat_id, fqdn, token)
                        if settings.max_chat_id:
                            await send_max_alert(settings.max_chat_id, fqdn, token)
                        alerts_sent += 1

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

                    channel_type = str(target.get("channel_type") or "").lower()
                    channel_target = str(target.get("channel_target") or "").strip()
                    if channel_type not in {"telegram", "max"} or not channel_target:
                        continue
                    key = (channel_type, channel_target)
                    if key in sent_keys:
                        continue
                    async with per_target_lock:
                        if per_target_sent.get(key, 0) >= per_target_run_limit:
                            continue
                        if self.store.has_recent_alert_for_destination(
                            fqdn,
                            destination=channel_target,
                            within_minutes=settings.monitor_alert_cooldown_minutes,
                        ):
                            continue
                        per_target_sent[key] = per_target_sent.get(key, 0) + 1

                    token = build_confirmation_token()
                    self.store.create_alert(
                        domain=fqdn,
                        telegram_chat_id=channel_target,
                        token=token,
                        alert_type=f"watch_rule_match:{rule_id}",
                    )

                    if channel_type == "telegram":
                        await send_telegram_alert(channel_target, fqdn, token)
                    else:
                        await send_max_alert(channel_target, fqdn, token)

                    sent_keys.add(key)
                    alerts_sent += 1

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
