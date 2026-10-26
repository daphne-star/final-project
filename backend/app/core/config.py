"""Application configuration, loaded from the environment."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo keeps a single .env at the course-root level (one above final-project),
# so resolve upward from this file rather than assuming the process CWD.
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
REPO_ROOT = PROJECT_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Ghost Board"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api"

    # --- Database ---
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:ghostboard@localhost:5432/ghostboard"
    )

    # --- Auth ---
    secret_key: str = Field(default="dev-only-insecure-change-me")
    access_token_expire_minutes: int = 60 * 24 * 7
    jwt_algorithm: str = "HS256"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- AI provider ---
    # AGENTS.md pins this project to OpenAI-compatible calls routed through Portkey.
    portkey_api_key: str | None = None
    portkey_base_url: str = "https://api.portkey.ai/v1"
    default_model: str = "gpt-6-luna"
    # gpt-6-luna rejects function tools on /v1/chat/completions unless
    # reasoning effort is off; structured output is a function tool.
    openai_reasoning_effort: str = "none"

    # --- Cost / execution controls (spec section 6) ---
    max_debate_rounds: int = 2
    max_model_requests_per_meeting: int = 60
    max_tool_calls_per_meeting: int = 40
    model_timeout_seconds: int = 120
    meeting_cost_limit_usd: float = 5.00

    # --- Uploads ---
    max_upload_bytes: int = 10 * 1024 * 1024

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
