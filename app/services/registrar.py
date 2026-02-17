from app.config import settings
from app.services.timeweb_api import TimewebApiClient


class RegistrarClient:
    def __init__(self, provider: str = "timeweb") -> None:
        self.provider = provider
        self.timeweb_client = TimewebApiClient(
            base_url=settings.timeweb_api_base_url,
            api_token=settings.timeweb_api_token,
        )

    async def register_domain(self, domain: str) -> dict:
        if self.provider == "timeweb":
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

        return {
            "provider": self.provider,
            "domain": domain,
            "result": "mock_registered",
            "external_order_id": f"mock:{domain}",
        }
