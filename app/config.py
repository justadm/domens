from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_port: int = 8080

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_chat_id: str = ""
    telegram_disclaimer_version: str = "v1"
    telegram_polling_enabled: bool = False
    telegram_polling_timeout_seconds: int = 25
    telegram_polling_allowed_updates: str = "message,callback_query"
    telegram_admin_user_ids: str = ""

    postgres_dsn: str = "postgresql://domens:domens@localhost:5432/domens"
    redis_url: str = "redis://localhost:6379/0"

    timeweb_api_base_url: str = "https://api.timeweb.cloud"
    timeweb_api_token: str = ""
    timeweb_app_id: str = ""

    selectel_api_base_url: str = "https://api.selectel.ru"
    selectel_domains_base_url: str = "https://api.selectel.ru/domains/v2"
    selectel_auth_token: str = ""
    selectel_static_token: str = ""
    selectel_deploy_start_path: str = ""
    selectel_deploy_status_path_template: str = ""
    selectel_deploy_logs_path_template: str = ""

    registrar_provider: str = "timeweb"
    registrar_fallback_enabled: bool = True
    registration_enabled: bool = False
    registration_require_available_check: bool = True
    reg_ru_api_base_url: str = "https://api.reg.ru/api/regru2"
    reg_ru_username: str = ""
    reg_ru_password: str = ""

    max_base_url: str = "https://platform-api.max.ru"
    max_token: str = ""
    max_chat_id: str = ""
    max_oauth_enabled: bool = False
    max_oauth_authorize_url: str = ""
    max_oauth_token_url: str = ""
    max_oauth_userinfo_url: str = ""
    max_oauth_client_id: str = ""
    max_oauth_client_secret: str = ""
    max_oauth_redirect_uri: str = ""
    max_oauth_scope: str = "openid profile"
    max_oauth_state_ttl_seconds: int = 600

    ecom_stats_enabled: bool = False
    ecom_stats_base_url: str = ""
    ecom_stats_path: str = "/admin/stats"
    ecom_stats_token: str = ""
    ecom_stats_timeout_seconds: int = 8

    auth_jwt_secret: str = "change_me"
    auth_jwt_ttl_seconds: int = 604800
    web_guest_auth_enabled: bool = False
    web_guest_user_id: str = ""
    web_guest_is_admin: bool = False

    monitor_enabled: bool = False
    monitor_interval_seconds: int = 300
    monitor_tlds: str = ".com,.io,.ai,.ru"
    monitor_seed_words: str = "agent,cloud,data,stack,flow,grid,lab,core"
    monitor_alert_min_score: float = 70.0
    monitor_alert_statuses: str = "available,pending_delete"
    monitor_require_provider_check: bool = True
    monitor_alert_cooldown_minutes: int = 1440
    monitor_alert_per_target_run_limit: int = 1
    monitor_alert_per_target_daily_limit: int = 3
    monitor_alert_global_run_limit: int = 3
    monitor_watchlist_only: bool = True
    monitor_admin_fanout_enabled: bool = False
    monitor_event_logging_enabled: bool = True
    monitor_event_logging_detail: bool = False

    copilot_llm_nlu_enabled: bool = False
    copilot_llm_provider: str = "ollama"
    copilot_llm_timeout_seconds: int = 12
    copilot_llm_confidence_threshold: float = 0.65
    copilot_llm_max_parallel: int = 1
    copilot_llm_chat_context_messages: int = 5
    copilot_llm_reply_max_chars: int = 700
    copilot_llm_ollama_base_url: str = "http://localhost:11434"
    copilot_llm_ollama_model: str = "qwen2.5:7b-instruct"
    copilot_llm_intent_model: str = "qwen2.5:0.5b"
    copilot_llm_reply_model: str = "qwen2.5:7b-instruct"
    copilot_llm_intent_timeout_seconds: int = 12
    copilot_llm_reply_timeout_seconds: int = 35
    copilot_llm_knowledge_enabled: bool = True
    copilot_llm_knowledge_files: str = "README.md,docs/copilot_feature.md,docs/api_contracts.md,docs/telegram_bot_scope.md"
    copilot_llm_knowledge_max_chars: int = 2400
    copilot_llm_fallback_enabled: bool = False
    copilot_llm_fallback_base_url: str = "https://openrouter.ai/api/v1"
    copilot_llm_fallback_api_key: str = ""
    copilot_llm_fallback_model: str = "qwen/qwen2.5-7b-instruct:free"
    copilot_rate_limit_window_seconds: int = 60
    copilot_rate_limit_requests: int = 12
    copilot_degrade_inflight_threshold: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
