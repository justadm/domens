from __future__ import annotations

from typing import Any

import httpx


class SelectelApiClient:
    def __init__(
        self,
        base_url: str,
        auth_token: str = "",
        static_token: str = "",
        domains_base_url: str = "https://api.selectel.ru/domains/v2",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.domains_base_url = domains_base_url.rstrip("/")
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

    async def list_zones(self) -> dict[str, Any]:
        if not self.auth_token:
            return {"ok": False, "reason": "missing_selectel_auth_token_for_domains"}

        url = f"{self.domains_base_url}/zones"
        headers = {"X-Auth-Token": self.auth_token, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)

        if not response.is_success:
            return {"ok": False, "status_code": response.status_code, "error": response.text}
        payload = response.json()
        items = payload if isinstance(payload, list) else payload.get("result", [])
        return {"ok": True, "zones": items}

    async def ensure_zone(self, fqdn: str) -> dict[str, Any]:
        """
        Reserve path: create DNS zone in Selectel DNS Hosting if absent.
        This does not register a domain in registry, only prepares DNS control.
        """
        if not self.auth_token:
            return {"ok": False, "reason": "missing_selectel_auth_token_for_domains", "domain": fqdn}

        zone_name = fqdn.strip().lower().rstrip(".") + "."
        zones_resp = await self.list_zones()
        if zones_resp.get("ok"):
            zones = zones_resp.get("zones", [])
            for item in zones:
                if str(item.get("name", "")).lower() == zone_name:
                    return {"ok": True, "result": "zone_exists", "zone": item, "domain": fqdn}

        url = f"{self.domains_base_url}/zones"
        headers = {"X-Auth-Token": self.auth_token, "Content-Type": "application/json"}
        payload = {"name": zone_name}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if not response.is_success:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": response.text,
                "domain": fqdn,
            }

        body = response.json() if response.content else {}
        return {"ok": True, "result": "zone_created", "zone": body, "domain": fqdn}
