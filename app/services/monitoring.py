from __future__ import annotations

import asyncio
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

    async def run_once(self) -> dict:
        candidates = self._build_candidates()
        interesting_statuses = {"available", "pending_delete", "redemption", "client_hold"}
        alerts_sent = 0

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
                if score < settings.monitor_alert_min_score:
                    return
                if not settings.telegram_chat_id and not settings.max_chat_id:
                    return
                if self.store.has_recent_alert(fqdn, within_minutes=settings.monitor_alert_cooldown_minutes):
                    return

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
