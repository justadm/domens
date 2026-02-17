from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class TimewebDomainCheckResult:
    available: bool | None
    status: str | None
    raw: dict[str, Any]


class TimewebApiClient:
    def __init__(self, base_url: str, api_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token)

    async def check_domain(self, fqdn: str) -> TimewebDomainCheckResult:
        if not self.is_configured:
            return TimewebDomainCheckResult(available=None, status=None, raw={"mode": "mock", "reason": "missing_token"})

        url = f"{self.base_url}/api/v1/check-domain/{fqdn}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, headers=headers)

        response.raise_for_status()
        payload = self._parse_json_safely(response)

        available = self._first_bool(payload, ["available", "is_available", "is_domain_available", "free"])
        status = self._first_str(payload, ["status", "domain_status", "state"])

        if available is None and isinstance(payload.get("result"), str):
            lowered = payload["result"].lower()
            if lowered in {"available", "free"}:
                available = True
            if lowered in {"registered", "taken", "busy"}:
                available = False

        return TimewebDomainCheckResult(available=available, status=status, raw=payload)

    async def add_domain(self, fqdn: str) -> dict[str, Any]:
        if not self.is_configured:
            return {"mode": "mock", "reason": "missing_token", "domain": fqdn}

        url = f"{self.base_url}/api/v1/add-domain/{fqdn}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json={})

        body = self._parse_json_safely(response)
        if not response.is_success:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": body if body else response.text,
                "domain": fqdn,
            }

        return {
            "ok": True,
            "status_code": response.status_code,
            "domain": fqdn,
            "response": body,
        }

    @staticmethod
    def _parse_json_safely(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {"data": value}

    @staticmethod
    def _first_bool(payload: dict[str, Any], keys: list[str]) -> bool | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                return value
        return None

    @staticmethod
    def _first_str(payload: dict[str, Any], keys: list[str]) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None
