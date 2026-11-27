from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    telegram_bot_token: str = ""
    telegram_admin_id: int = 0
    telegram_targets: str = ""
    discord_bot_token: str = ""
    discord_targets: str = ""
    pinterest_source: str = "api"
    pinterest_board_url: str = ""
    pinterest_board_id: str = ""
    pinterest_access_token: str = ""
    pinterest_rss_url: str = ""
    post_interval_minutes: int = 60
    poll_interval_minutes: int = 15
    new_pin_mode: str = "immediate"
    admin_username: str = "admin"
    admin_password_hash: str = ""
    secret_key: str = "change-me"
    database_url: str = "sqlite+aiosqlite:///./data/memovoz.db"
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    max_media_mb: int = 48
    log_level: str = "INFO"

    @staticmethod
    def parse_ids(value: str) -> list[str]:
        return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]

settings = Settings()
