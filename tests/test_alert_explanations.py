import asyncio

from app.services.monitoring import DomainMonitoringService
from app.services.notifications import send_telegram_alert


def test_alert_explanation_contains_score_status_and_tld() -> None:
    explanation = DomainMonitoringService._build_alert_explanation(
        fqdn="stackai.ru",
        status="available",
        score=87.345,
        provider="timeweb",
        matched_query="ai tools",
    )

    assert explanation["score"] == 87.34 or explanation["score"] == 87.35
    assert explanation["status"] == "available"
    assert explanation["provider"] == "timeweb"
    assert explanation["tld"] == "ru"
    assert explanation["matched_query"] == "ai tools"
    assert explanation["risk"] == "provider_checked"


def test_telegram_alert_includes_explanation_in_mock_mode(monkeypatch) -> None:
    monkeypatch.setattr("app.services.notifications.settings.telegram_bot_token", "")

    result = asyncio.run(
        send_telegram_alert(
            "13903713",
            "stackai.ru",
            "cfm_token",
            explanation={"score": 87.35, "status": "available", "tld": "ru"},
        )
    )

    assert result["mode"] == "mock"
    assert "Score: 87.35" in result["text"]
    assert "Status: available" in result["text"]
    assert "TLD: .ru" in result["text"]
