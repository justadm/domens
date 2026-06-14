from app.config import Settings


def test_monitoring_is_off_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.monitor_enabled is False
    assert settings.registration_enabled is False
    assert settings.monitor_alert_cooldown_minutes == 1440
    assert settings.monitor_alert_per_target_run_limit == 1
    assert settings.monitor_alert_per_target_daily_limit == 3
    assert settings.monitor_alert_global_run_limit == 3
    assert settings.monitor_watchlist_only is True
    assert settings.monitor_admin_fanout_enabled is False
    assert settings.monitor_digest_enabled is True
    assert settings.monitor_event_logging_enabled is True
    assert settings.monitor_event_logging_detail is False
