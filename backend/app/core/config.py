"""Application configuration, loaded from the environment."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve upward from this file rather than trusting the process CWD, which
# differs between `uvicorn` from backend/, pytest from the repo root, and a
# demo script run from anywhere.
BACKEND_DIR = Path(__file__).resolve().parents[2]
#: The repository's own folder: the one holding backend/ and frontend/.
REPO_DIR = BACKEND_DIR.parent
#: Whatever the repository was cloned into. A key kept here is shared by
#: everything in that folder, which is how this checkout is actually set up.
PARENT_DIR = REPO_DIR.parent


def env_files(repo_dir: Path = REPO_DIR) -> tuple[Path, ...]:
    """The .env files to read, **lowest precedence first**.

    Two locations: the repository's own folder, and the folder above it. A
    .env beside the project wins, so a per-project key overrides a shared one
    without anyone having to move files around.

    The order looks backwards because pydantic-settings applies a sequence in
    order and lets *later* files override earlier ones. Reversing this tuple
    silently inverts the precedence, which is why test_config.py pins it.
    """
    return (repo_dir.parent / ".env", repo_dir / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_files(),
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
    #: bcrypt work factor. Deliberately slow in production; the test suite
    #: lowers it, since hashing a throwaway password 250 times is ~100s of
    #: pure waste and proves nothing.
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)
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
    #: Always enforceable, unlike the cost limit: token counts are known
    #: for every call whether or not a price is configured.
    max_total_tokens_per_meeting: int = 400_000
    #: JSON: {"model": {"input_per_million": x, "output_per_million": y}}.
    #: Unset means costs are recorded as unknown rather than as zero.
    model_prices: str | None = None

    # --- Uploads ---
    max_upload_bytes: int = 10 * 1024 * 1024
    #: Outside the package tree, so an uploaded file can never be imported.
    upload_dir: str = str(BACKEND_DIR / "var" / "uploads")

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
