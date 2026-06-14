import asyncio

from app.services.monitoring import DomainMonitoringService
from app.services.notifications import send_telegram_alert, send_telegram_digest


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
    monkeypatch.setattr("app.services.notifications.settings.registration_enabled", False)

    result = asyncio.run(
        send_telegram_alert(
            "13903713",
            "stackai.ru",
            "cfm_token",
            explanation={
                "score": 87.35,
                "status": "available",
                "tld": "ru",
                "matched_query": "ai tools",
                "risk": "provider_checked",
            },
        )
    )

    assert result["mode"] == "mock"
    assert "Почему интересно:" in result["text"]
    assert "score: 87.35" in result["text"]
    assert "статус: available" in result["text"]
    assert "TLD: .ru" in result["text"]
    assert "watch: ai tools" in result["text"]
    assert "риск: provider_checked" in result["text"]
    assert "Регистрация сейчас выключена" in result["text"]
    assert f"register:cfm_token" not in result["buttons"]
    assert f"skip:cfm_token" in result["buttons"]
    assert f"feedback:more:cfm_token" in result["buttons"]
    assert f"feedback:less:cfm_token" in result["buttons"]
    assert f"feedback:why:cfm_token" in result["buttons"]


def test_telegram_alert_shows_register_button_when_registration_enabled(monkeypatch) -> None:
    monkeypatch.setattr("app.services.notifications.settings.telegram_bot_token", "")
    monkeypatch.setattr("app.services.notifications.settings.registration_enabled", True)

    result = asyncio.run(send_telegram_alert("13903713", "stackai.ru", "cfm_token"))

    assert f"register:cfm_token" in result["buttons"]


def test_telegram_digest_groups_candidates_with_feedback_buttons(monkeypatch) -> None:
    monkeypatch.setattr("app.services.notifications.settings.telegram_bot_token", "")

    result = asyncio.run(
        send_telegram_digest(
            "13903713",
            [
                {
                    "domain": "stackai.ru",
                    "token": "cfm_1",
                    "explanation": {
                        "score": 91.0,
                        "status": "available",
                        "tld": "ru",
                        "matched_query": "ai tools",
                    },
                },
                {
                    "domain": "stackai.io",
                    "token": "cfm_2",
                    "explanation": {
                        "score": 95.0,
                        "status": "available",
                        "tld": "io",
                        "matched_query": "ai tools",
                    },
                },
            ],
        )
    )

    assert result["mode"] == "mock"
    assert result["items_count"] == 2
    assert "Дайджест радара:" in result["text"]
    assert "1. stackai.io | score 95.0 | available | .io" in result["text"]
    assert "2. stackai.ru | score 91.0 | available | .ru" in result["text"]
    assert "watch: ai tools" in result["text"]
    assert "feedback:why:cfm_1" in result["buttons"]
    assert "feedback:more:cfm_1" in result["buttons"]
    assert "feedback:less:cfm_1" in result["buttons"]
    assert "feedback:never:cfm_1" in result["buttons"]
