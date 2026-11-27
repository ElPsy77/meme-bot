from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    telegram_bot_token: str = ""
    telegram_admin_id: int = 0
    telegram_targets: str = ""
    discord_bot_token: str = ""
    discord_targets: str = ""
    meme_source: str = Field(default="telegram_inbox", validation_alias=AliasChoices("MEME_SOURCE", "PINTEREST_SOURCE"))
    media_folder: str = "./memes"
    media_archive_folder: str = "./data/media"
    pinterest_board_url: str = ""
    pinterest_board_id: str = ""
    pinterest_access_token: str = ""
    pinterest_rss_url: str = ""
    post_interval_minutes: int = Field(default=60, ge=1, le=10080)
    poll_interval_minutes: int = Field(default=15, ge=1, le=10080)
    new_pin_mode: str = "immediate"
    admin_username: str = "admin"
    admin_password_hash: str = ""
    secret_key: str = "change-me"
    cookie_https_only: bool = False
    database_url: str = "sqlite+aiosqlite:///./data/memovoz.db"
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    max_media_mb: int = Field(default=48, ge=1, le=500)
    inbox_max_mb: int = Field(default=18, ge=1, le=20)
    log_level: str = "INFO"

    @field_validator("meme_source")
    @classmethod
    def validate_meme_source(cls, value: str) -> str:
        value = value.lower().strip()
        value = {"api": "pinterest_api", "rss": "pinterest_rss"}.get(value, value)
        if value not in {"pinterest_api", "pinterest_rss", "folder", "telegram_inbox"}:
            raise ValueError("MEME_SOURCE must be 'pinterest_api', 'pinterest_rss', 'folder', or 'telegram_inbox'")
        return value

    @field_validator("new_pin_mode")
    @classmethod
    def validate_new_pin_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"immediate", "queue"}:
            raise ValueError("NEW_PIN_MODE must be 'immediate' or 'queue'")
        return value

    @staticmethod
    def parse_ids(value: str) -> list[str]:
        return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]

settings = Settings()
