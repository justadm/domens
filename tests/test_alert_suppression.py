import asyncio
from types import SimpleNamespace

from app.services import monitoring
from app.services.monitoring import DomainMonitoringService


class FakeStore:
    def __init__(self) -> None:
        self.alerts: list[dict] = []
        self.suppressions: set[tuple[str, str, str]] = set()
        self.events: list[dict] = []
        self.watch_targets: list[dict] = []
        self.admin_chats: list[str] = []

    def list_active_watch_targets(self) -> list[dict]:
        return self.watch_targets

    def list_telegram_chats_by_user_ids(self, _user_ids: list[str]) -> list[str]:
        return self.admin_chats

    def log_bot_event(self, event_type: str, **kwargs) -> None:
        self.events.append({"event_type": event_type, **kwargs})

    def upsert_domain_snapshot(self, **_kwargs) -> None:
        return None

    def has_recent_alert(self, _fqdn: str, within_minutes: int = 60) -> bool:
        return False

    def has_recent_alert_for_destination(
        self,
        _fqdn: str,
        destination: str,
        within_minutes: int = 60,
    ) -> bool:
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
    monkeypatch.setattr(monitoring.settings, "monitor_watchlist_only", False)
    monkeypatch.setattr(monitoring.settings, "monitor_admin_fanout_enabled", False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_enabled", True)

    first = asyncio.run(service.run_once())
    second = asyncio.run(service.run_once())

    assert first["alerts_sent"] == 1
    assert second["alerts_sent"] == 0
    assert len(fake_store.alerts) == 1
    assert fake_store.alerts[0]["domain"] == "stackai.ru"
    assert fake_store.alerts[0]["telegram_chat_id"] == "13903713"
    assert fake_store.alerts[0]["explanation"]["status"] == "available"
    assert ("stackai.ru", "13903713", "same_domain") in fake_store.suppressions


def test_user_never_suppression_blocks_future_monitor_alert(monkeypatch) -> None:
    fake_store = FakeStore()
    fake_store.suppressions.add(("stackai.ru", "13903713", "user_never"))
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
    monkeypatch.setattr(monitoring.settings, "monitor_watchlist_only", False)
    monkeypatch.setattr(monitoring.settings, "monitor_admin_fanout_enabled", False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_enabled", True)

    result = asyncio.run(service.run_once())

    assert result["alerts_sent"] == 0
    assert fake_store.alerts == []


def test_user_less_suppression_blocks_future_monitor_alert(monkeypatch) -> None:
    fake_store = FakeStore()
    fake_store.suppressions.add(("stackai.ru", "13903713", "user_less"))
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
    monkeypatch.setattr(monitoring.settings, "monitor_watchlist_only", False)
    monkeypatch.setattr(monitoring.settings, "monitor_admin_fanout_enabled", False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_enabled", True)

    result = asyncio.run(service.run_once())

    assert result["alerts_sent"] == 0
    assert fake_store.alerts == []


def test_watchlist_only_canary_ignores_global_candidates_and_admin_fanout(monkeypatch) -> None:
    fake_store = FakeStore()
    fake_store.watch_targets = [
        {
            "rule_id": "rule-1",
            "telegram_user_id": "13903713",
            "query": "focus stack",
            "tlds": [".ru"],
            "min_score": None,
            "max_length": None,
            "daily_alert_limit": 1,
            "channel_type": "telegram",
            "channel_target": "13903713",
        }
    ]
    fake_store.admin_chats = ["13903713"]
    service = DomainMonitoringService(fake_store)  # type: ignore[arg-type]
    service.timeweb_client = SimpleNamespace(is_configured=True)

    checked: list[str] = []

    monkeypatch.setattr(service, "_build_candidates", lambda: ["globalnoise.ru"])
    monkeypatch.setattr(service, "_build_query_candidates", lambda _query, _tlds: ["focusstack.ru"])

    async def fake_infer_status(fqdn: str, **_kwargs) -> tuple[str, None]:
        checked.append(fqdn)
        return "available", None

    monkeypatch.setattr(monitoring, "infer_status", fake_infer_status)
    monkeypatch.setattr(monitoring, "score_domain", lambda _fqdn: 90.0)
    monkeypatch.setattr(monitoring, "build_confirmation_token", lambda: "cfm_token")

    async def fake_send(*_args, **_kwargs) -> dict:
        return {"mode": "mock"}

    monkeypatch.setattr(monitoring, "send_telegram_alert", fake_send)
    monkeypatch.setattr(monitoring.settings, "telegram_chat_id", "legacy-chat")
    monkeypatch.setattr(monitoring.settings, "max_chat_id", "")
    monkeypatch.setattr(monitoring.settings, "telegram_admin_user_ids", "13903713")
    monkeypatch.setattr(monitoring.settings, "monitor_tlds", ".ru")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_min_score", 70.0)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_statuses", "available")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_global_run_limit", 3)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_run_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_daily_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_cooldown_minutes", 1440)
    monkeypatch.setattr(monitoring.settings, "monitor_require_provider_check", True)
    monkeypatch.setattr(monitoring.settings, "monitor_watchlist_only", True, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_admin_fanout_enabled", False, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_enabled", True, raising=False)

    result = asyncio.run(service.run_once())

    assert checked == ["focusstack.ru"]
    assert result["checked"] == 1
    assert result["alerts_sent"] == 1
    assert [alert["alert_type"] for alert in fake_store.alerts] == ["watch_rule_match:rule-1"]
    assert fake_store.alerts[0]["telegram_chat_id"] == "13903713"


def test_monitoring_run_writes_compact_summary_without_per_candidate_events(monkeypatch) -> None:
    fake_store = FakeStore()
    fake_store.watch_targets = [
        {
            "rule_id": "rule-1",
            "telegram_user_id": "13903713",
            "query": "audit stack",
            "tlds": [".ru"],
            "min_score": None,
            "max_length": None,
            "daily_alert_limit": 1,
            "channel_type": "telegram",
            "channel_target": "13903713",
        }
    ]
    service = DomainMonitoringService(fake_store)  # type: ignore[arg-type]
    service.timeweb_client = SimpleNamespace(is_configured=True)

    monkeypatch.setattr(service, "_build_candidates", lambda: [])
    monkeypatch.setattr(service, "_build_query_candidates", lambda _query, _tlds: ["auditstack.ru", "auditbusy.ru"])

    async def fake_infer_status(fqdn: str, **_kwargs) -> tuple[str, None]:
        return ("registered" if fqdn == "auditbusy.ru" else "available"), None

    monkeypatch.setattr(monitoring, "infer_status", fake_infer_status)
    monkeypatch.setattr(monitoring, "score_domain", lambda _fqdn: 91.0)
    monkeypatch.setattr(monitoring, "build_confirmation_token", lambda: "cfm_token")

    async def fake_send(*_args, **_kwargs) -> dict:
        return {"mode": "mock"}

    monkeypatch.setattr(monitoring, "send_telegram_alert", fake_send)
    monkeypatch.setattr(monitoring.settings, "telegram_chat_id", "")
    monkeypatch.setattr(monitoring.settings, "max_chat_id", "")
    monkeypatch.setattr(monitoring.settings, "telegram_admin_user_ids", "")
    monkeypatch.setattr(monitoring.settings, "monitor_tlds", ".ru")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_statuses", "available")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_global_run_limit", 3)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_run_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_daily_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_cooldown_minutes", 1440)
    monkeypatch.setattr(monitoring.settings, "monitor_require_provider_check", True)
    monkeypatch.setattr(monitoring.settings, "monitor_watchlist_only", True, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_admin_fanout_enabled", False, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_enabled", True, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_detail", False, raising=False)

    result = asyncio.run(service.run_once())

    event_types = [event["event_type"] for event in fake_store.events]
    assert result["alerts_sent"] == 1
    assert "monitor_run_started" in event_types
    assert "monitor_candidates_built" in event_types
    assert "monitor_alert_sent" in event_types
    assert "monitor_run_finished" in event_types
    assert "monitor_candidate_checked" not in event_types
    assert "monitor_alert_skipped" not in event_types

    finished_event = next(event for event in fake_store.events if event["event_type"] == "monitor_run_finished")
    assert finished_event["payload"]["status_counts"] == {"available": 1, "registered": 1}
    assert finished_event["payload"]["skip_reasons"] == {"status_not_interesting": 1}
    assert finished_event["payload"]["checked"] == 2
    assert finished_event["payload"]["alerts_sent"] == 1

    sent_event = next(event for event in fake_store.events if event["event_type"] == "monitor_alert_sent")
    assert sent_event["payload"]["fqdn"] == "auditstack.ru"
    assert sent_event["payload"]["alert_type"] == "watch_rule_match:rule-1"


def test_monitoring_detail_logging_writes_per_candidate_events(monkeypatch) -> None:
    fake_store = FakeStore()
    fake_store.watch_targets = [
        {
            "rule_id": "rule-1",
            "telegram_user_id": "13903713",
            "query": "audit stack",
            "tlds": [".ru"],
            "min_score": None,
            "max_length": None,
            "daily_alert_limit": 1,
            "channel_type": "telegram",
            "channel_target": "13903713",
        }
    ]
    service = DomainMonitoringService(fake_store)  # type: ignore[arg-type]
    service.timeweb_client = SimpleNamespace(is_configured=True)

    monkeypatch.setattr(service, "_build_candidates", lambda: [])
    monkeypatch.setattr(service, "_build_query_candidates", lambda _query, _tlds: ["auditbusy.ru"])

    async def fake_infer_status(*_args, **_kwargs) -> tuple[str, None]:
        return "registered", None

    monkeypatch.setattr(monitoring, "infer_status", fake_infer_status)
    monkeypatch.setattr(monitoring, "score_domain", lambda _fqdn: 91.0)
    monkeypatch.setattr(monitoring.settings, "telegram_chat_id", "")
    monkeypatch.setattr(monitoring.settings, "max_chat_id", "")
    monkeypatch.setattr(monitoring.settings, "telegram_admin_user_ids", "")
    monkeypatch.setattr(monitoring.settings, "monitor_tlds", ".ru")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_statuses", "available")
    monkeypatch.setattr(monitoring.settings, "monitor_alert_global_run_limit", 3)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_run_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_per_target_daily_limit", 1)
    monkeypatch.setattr(monitoring.settings, "monitor_alert_cooldown_minutes", 1440)
    monkeypatch.setattr(monitoring.settings, "monitor_require_provider_check", True)
    monkeypatch.setattr(monitoring.settings, "monitor_watchlist_only", True, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_admin_fanout_enabled", False, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_enabled", True, raising=False)
    monkeypatch.setattr(monitoring.settings, "monitor_event_logging_detail", True, raising=False)

    result = asyncio.run(service.run_once())

    event_types = [event["event_type"] for event in fake_store.events]
    assert result["alerts_sent"] == 0
    assert "monitor_candidate_checked" in event_types
    assert "monitor_alert_skipped" in event_types
