from __future__ import annotations

import json
from typing import Any

import httpx


class RegRuApiClient:
    def __init__(self, base_url: str, username: str = "", password: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    async def _call(self, command: str, input_data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured:
            return {"ok": False, "reason": "missing_reg_ru_credentials"}

        url = f"{self.base_url}/{command}"
        payload = {
            "username": self.username,
            "password": self.password,
            "input_data": json.dumps(input_data),
            "output_content_type": "json",
            "input_format": "json",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, data=payload)

        body: dict[str, Any]
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if not response.is_success:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": body,
            }

        if isinstance(body, dict) and body.get("error"):
            return {"ok": False, "error": body.get("error"), "raw": body}

        return {"ok": True, "response": body}

    async def check_domain(self, fqdn: str) -> dict[str, Any]:
        return await self._call("domain/check", {"domains": [{"dname": fqdn}]})

    async def create_domain(self, fqdn: str, period: int = 1) -> dict[str, Any]:
        return await self._call(
            "domain/create",
            {
                "domains": [{"dname": fqdn, "period": period}],
            },
        )
