import asyncio
from types import SimpleNamespace

from app.services import monitoring
from app.services.monitoring import DomainMonitoringService


class FakeStore:
    def __init__(self) -> None:
        self.alerts: list[dict] = []
        self.suppressions: set[tuple[str, str, str]] = set()

    def list_active_watch_targets(self) -> list[dict]:
        return []

    def list_telegram_chats_by_user_ids(self, _user_ids: list[str]) -> list[str]:
        return []

    def upsert_domain_snapshot(self, **_kwargs) -> None:
        return None

    def has_recent_alert(self, _fqdn: str, within_minutes: int = 60) -> bool:
        return False

    def count_recent_alerts_for_destination(
        self,
        _destination: str,
        within_hours: int = 24,
        alert_type_prefix: str | None = None,
    ) -> int:
        return 0

    def should_suppress_alert(self, fqdn: str, destination: str, reason: str) -> bool:
        return (fqdn, destination, reason) in self.suppressions

    def suppress_alert(self, fqdn: str, destination: str, reason: str, days: int = 30) -> None:
        self.suppressions.add((fqdn, destination, reason))

    def create_alert(self, **kwargs) -> SimpleNamespace:
        self.alerts.append(kwargs)
        return SimpleNamespace(alert_id="alert-1")


def test_same_domain_destination_is_suppressed_after_first_monitor_alert(monkeypatch) -> None:
    fake_store = FakeStore()
    service = DomainMonitoringService(fake_store)  # type: ignore[arg-type]
    service.timeweb_client = SimpleNamespace(is_configured=True)

    monkeypatch.setattr(service, "_build_candidates", lambda: ["stackai.ru"])
    async def fake_infer_status(*_args, **_kwargs) -> tuple[str, None]:
        return "available", None

    monkeypatch.setattr(monitoring, "infer_status", fake_infer_status)
    monkeypatch.setattr(monitoring, "score_domain", lambda _fqdn: 90.0)
    monkeypatch.setattr(monitoring, "build_confirmation_token", lambda: "cfm_token")

    async def fake_send(*_args, **_kwargs) -> dict:
        return {"mode": "mock"}

    monkeypatch.setattr(monitoring, "send_telegram_alert", fake_send)
    monkeypatch.setattr(monitoring.settings, "telegram_chat_id", "13903713")
    monkeypatch.setattr(monitoring.settings, "max_chat_id", "")
    monkeypatch.setattr(monitoring.settings, "telegram_admin_user_ids", "")
    monkeypatch.setattr(monitoring.settings, "monitor_tlds", ".ru")
    monkeypatch.setattr(monitoring.settings, "monitor_seed_words", "stack")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_min_score", 70.0)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_statuses", "available")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_global_run_limit", 3)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_run_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_daily_limit", 3)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_cooldown_minutes", 1440)
    monkeypatch.setattr(monitoring.settings, "monitor_require_provider_check", True)

    first = asyncio.run(service.run_once())
    second = asyncio.run(service.run_once())

    assert first["alerts_sent"] == 1
    assert second["alerts_sent"] == 0
    assert len(fake_store.alerts) == 1
    assert fake_store.alerts[0]["domain"] == "stackai.ru"
    assert fake_store.alerts[0]["telegram_chat_id"] == "13903713"
    assert fake_store.alerts[0]["explanation"]["status"] == "available"
    assert ("stackai.ru", "13903713", "same_domain") in fake_store.suppressions
