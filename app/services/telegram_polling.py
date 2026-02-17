from __future__ import annotations

import asyncio

import httpx

from app.config import settings
from app.routers.telegram import process_telegram_update


class TelegramPollingService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._offset: int | None = None

    @staticmethod
    def _allowed_updates() -> list[str]:
        raw = settings.telegram_polling_allowed_updates.strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    async def _delete_webhook(self, client: httpx.AsyncClient) -> None:
        token = settings.telegram_bot_token.strip()
        if not token:
            return
        url = f"https://api.telegram.org/bot{token}/deleteWebhook"
        try:
            await client.post(url, json={"drop_pending_updates": False})
        except Exception:
            # Keep polling loop resilient even if webhook cleanup fails.
            pass

    async def _poll_once(self, client: httpx.AsyncClient) -> None:
        token = settings.telegram_bot_token.strip()
        if not token:
            await asyncio.sleep(2)
            return

        payload: dict = {
            "timeout": max(1, settings.telegram_polling_timeout_seconds),
            "allowed_updates": self._allowed_updates(),
        }
        if self._offset is not None:
            payload["offset"] = self._offset

        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json() if response.content else {}

        if not data.get("ok"):
            await asyncio.sleep(2)
            return

        updates = data.get("result") or []
        for item in updates:
            if not isinstance(item, dict):
                continue

            update_id = item.get("update_id")
            if isinstance(update_id, int):
                self._offset = update_id + 1

            try:
                await process_telegram_update(item)
            except Exception:
                # Ignore single update failure to keep poller alive.
                continue

    async def _run_loop(self) -> None:
        timeout_seconds = max(5, settings.telegram_polling_timeout_seconds + 10)
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            await self._delete_webhook(client)
            while not self._stop_event.is_set():
                try:
                    await self._poll_once(client)
                except Exception:
                    await asyncio.sleep(2)

    async def start(self) -> None:
        if not settings.telegram_polling_enabled:
            return
        if not settings.telegram_bot_token.strip():
            return
        if self._task and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="telegram-polling")

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
