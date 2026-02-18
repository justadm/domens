from __future__ import annotations

import httpx

from app.config import settings


async def fetch_external_ecom_stats() -> dict:
    if not settings.ecom_stats_enabled:
        return {}
    base = str(settings.ecom_stats_base_url or "").strip().rstrip("/")
    if not base:
        return {}
    path = str(settings.ecom_stats_path or "/admin/stats").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base}{path}"
    headers: dict[str, str] = {}
    token = str(settings.ecom_stats_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        timeout = max(2, int(settings.ecom_stats_timeout_seconds))
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            return {"ecom_error": f"http_{response.status_code}"}
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            return {"ecom_error": "invalid_payload"}
        return payload
    except Exception as exc:
        return {"ecom_error": str(exc)}
