from datetime import datetime, timedelta, timezone

from app.services.timeweb_api import TimewebApiClient


async def infer_status(
    domain: str,
    timeweb_client: TimewebApiClient | None = None,
    allow_heuristic_fallback: bool = True,
) -> tuple[str, datetime | None]:
    """
    MVP heuristic:
    - if endswith 'ai' and name length <= 10 => pending_delete soon
    - if contains 'free' => available
    - else registered
    Replace with RDAP/registrar API in production.
    """
    if timeweb_client and timeweb_client.is_configured:
        try:
            result = await timeweb_client.check_domain(domain)
            if result.available is True:
                return "available", None
            if result.available is False:
                return "registered", None
            if result.status:
                normalized = result.status.strip().lower().replace(" ", "_")
                if normalized in {"pending_delete", "redemption", "client_hold"}:
                    if normalized == "pending_delete":
                        return "pending_delete", datetime.now(timezone.utc) + timedelta(hours=36)
                    return normalized, None
            if not allow_heuristic_fallback:
                return "registered", None
        except Exception:
            # Fallback to heuristic flow if provider check fails.
            if not allow_heuristic_fallback:
                return "registered", None

    if not allow_heuristic_fallback:
        return "registered", None
    lowered = domain.lower()
    if lowered.endswith(".ai") and len(lowered.split(".")[0]) <= 10:
        return "pending_delete", datetime.now(timezone.utc) + timedelta(hours=36)
    if "free" in lowered:
        return "available", None
    return "registered", None
