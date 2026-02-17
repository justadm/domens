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

    auth_jwt_secret: str = "change_me"
    auth_jwt_ttl_seconds: int = 604800

    monitor_enabled: bool = True
    monitor_interval_seconds: int = 300
    monitor_tlds: str = ".com,.io,.ai,.ru"
    monitor_seed_words: str = "agent,cloud,data,stack,flow,grid,lab,core"
    monitor_alert_min_score: float = 70.0
    monitor_alert_cooldown_minutes: int = 180
    monitor_alert_per_target_run_limit: int = 5
    monitor_alert_per_target_daily_limit: int = 25

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
