from __future__ import annotations

from typing import Any

import httpx


class SelectelApiClient:
    def __init__(self, base_url: str, auth_token: str = "", static_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.static_token = static_token

    @property
    def is_configured(self) -> bool:
        return bool(self.auth_token or self.static_token)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["X-Auth-Token"] = self.auth_token
        if self.static_token:
            headers["X-Token"] = self.static_token
        return headers

    async def ping(self) -> dict[str, Any]:
        if not self.is_configured:
            return {"ok": False, "reason": "missing_selectel_tokens"}

        url = f"{self.base_url}/v3/balances"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=self._headers())

        return {"ok": response.is_success, "status_code": response.status_code}
