from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved relative to this file (not the process cwd) so `.env` is found
# regardless of the directory the server was launched from.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str = "sqlite:///./financial_records.db"

    ai_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # Records below this AI-reported confidence are forced to NEEDS_REVIEW
    # even if all required fields are technically present.
    extraction_confidence_threshold: float = 0.75

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
