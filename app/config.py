from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_port: int = 8080

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    postgres_dsn: str = "postgresql://domens:domens@localhost:5432/domens"
    redis_url: str = "redis://localhost:6379/0"

    registrar_base_url: str = "https://api.registrar.example"
    registrar_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
