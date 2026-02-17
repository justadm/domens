from app.config import settings
from app.services.reg_ru_api import RegRuApiClient
from app.services.selectel_api import SelectelApiClient
from app.services.timeweb_api import TimewebApiClient


class RegistrarClient:
    def __init__(self, provider: str = "timeweb") -> None:
        self.provider = provider
        self.timeweb_client = TimewebApiClient(
            base_url=settings.timeweb_api_base_url,
            api_token=settings.timeweb_api_token,
        )
        self.selectel_client = SelectelApiClient(
            base_url=settings.selectel_api_base_url,
            auth_token=settings.selectel_auth_token,
            static_token=settings.selectel_static_token,
            domains_base_url=settings.selectel_domains_base_url,
        )
        self.reg_ru_client = RegRuApiClient(
            base_url=settings.reg_ru_api_base_url,
            username=settings.reg_ru_username,
            password=settings.reg_ru_password,
        )

    async def _register_timeweb(self, domain: str) -> dict:
        result = await self.timeweb_client.add_domain(domain)
        if result.get("ok"):
            return {
                "provider": "timeweb",
                "domain": domain,
                "result": "registered",
                "external_order_id": f"timeweb:{domain}",
                "raw": result.get("response", {}),
            }
        return {
            "provider": "timeweb",
            "domain": domain,
            "result": "failed",
            "error": result.get("error", "unknown error"),
            "status_code": result.get("status_code"),
        }

    async def _register_reg_ru(self, domain: str) -> dict:
        result = await self.reg_ru_client.create_domain(domain)
        if result.get("ok"):
            return {
                "provider": "reg_ru",
                "domain": domain,
                "result": "registered",
                "external_order_id": f"reg_ru:{domain}",
                "raw": result.get("response", {}),
            }
        return {
            "provider": "reg_ru",
            "domain": domain,
            "result": "failed",
            "error": result,
        }

    async def _reserve_selectel_zone(self, domain: str) -> dict:
        fallback = await self.selectel_client.ensure_zone(domain)
        if fallback.get("ok"):
            return {
                "provider": "selectel_dns",
                "domain": domain,
                "result": "reserved_dns_zone",
                "external_order_id": f"selectel-zone:{domain}",
                "raw": fallback,
            }
        return {
            "provider": "selectel_dns",
            "domain": domain,
            "result": "failed",
            "error": fallback,
        }

    async def register_domain(self, domain: str) -> dict:
        if self.provider == "timeweb":
            primary = await self._register_timeweb(domain)
            if primary.get("result") == "registered" or not settings.registrar_fallback_enabled:
                return primary

            if self.reg_ru_client.is_configured:
                reg_ru = await self._register_reg_ru(domain)
                if reg_ru.get("result") == "registered":
                    reg_ru["primary_error"] = primary
                    return reg_ru
                primary["reg_ru_fallback_error"] = reg_ru

            selectel = await self._reserve_selectel_zone(domain)
            if selectel.get("result") == "reserved_dns_zone":
                selectel["primary_error"] = primary
                return selectel
            primary["selectel_fallback_error"] = selectel
            return primary

        if self.provider == "reg_ru":
            return await self._register_reg_ru(domain)

        if self.provider == "selectel":
            return await self._reserve_selectel_zone(domain)

        return {
            "provider": self.provider,
            "domain": domain,
            "result": "mock_registered",
            "external_order_id": f"mock:{domain}",
        }
