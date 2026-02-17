from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_port: int = 8080

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    postgres_dsn: str = "postgresql://domens:domens@localhost:5432/domens"
    redis_url: str = "redis://localhost:6379/0"

    timeweb_api_base_url: str = "https://api.timeweb.cloud"
    timeweb_api_token: str = ""
    timeweb_app_id: str = ""

    selectel_api_base_url: str = "https://api.selectel.ru"
    selectel_auth_token: str = ""
    selectel_static_token: str = ""
    selectel_deploy_start_path: str = ""
    selectel_deploy_status_path_template: str = ""
    selectel_deploy_logs_path_template: str = ""

    registrar_provider: str = "timeweb"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
