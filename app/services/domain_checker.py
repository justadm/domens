from datetime import datetime, timedelta, timezone


def infer_status(domain: str) -> tuple[str, datetime | None]:
    """
    MVP heuristic:
    - if endswith 'ai' and name length <= 10 => pending_delete soon
    - if contains 'free' => available
    - else registered
    Replace with RDAP/registrar API in production.
    """
    lowered = domain.lower()
    if lowered.endswith(".ai") and len(lowered.split(".")[0]) <= 10:
        return "pending_delete", datetime.now(timezone.utc) + timedelta(hours=36)
    if "free" in lowered:
        return "available", None
    return "registered", None
