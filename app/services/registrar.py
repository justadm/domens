import uuid


class RegistrarClient:
    def __init__(self, provider: str = "MockRegistrar") -> None:
        self.provider = provider

    async def register_domain(self, domain: str) -> dict:
        # Stub adapter for registrar API.
        return {
            "provider": self.provider,
            "external_order_id": f"MR-{uuid.uuid4().hex[:10].upper()}",
            "domain": domain,
            "result": "registered",
        }
