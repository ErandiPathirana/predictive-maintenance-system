"""Application settings, read from environment variables (or the project .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # ignore VITE_* and other variables meant for other tools
        protected_namespaces=("settings_",),  # allow field names that start with "model_"
    )

    app_name: str = "Motor Condition Prediction API"
    app_version: str = "0.2.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Explicit, comma-separated list of frontend origins allowed to call the API.
    cors_origins: str = "http://localhost:5173"

    # Folder produced by the Colab notebook (relative paths are relative to the project root).
    model_bundle_dir: Path = PROJECT_ROOT / "ml" / "artifacts" / "pm_condition_ann_v1.0.0"
    require_model_at_startup: bool = True      # True: refuse to start if the bundle is missing/invalid
    allow_smoke_test_bundle: bool = False      # a FAST_DEBUG notebook bundle is refused unless this is True
    force_demonstration_banner: bool | None = None  # None = decide automatically from bundle metadata

    # Optional approved maintenance guidance (JSON). Unset = only the built-in general guidance is used. An invalid file stops startup.
    site_guidance_file: Path | None = None

    # Database. SQLite for local work; PostgreSQL URL for hosted deployment.
    database_url: str = "sqlite:///predictions.db"
    auto_create_tables: bool = False           # development convenience only; use Alembic otherwise
    store_input_readings: bool = False         # False = sensor values are NOT written to the database

    # Upload and export limits
    max_upload_bytes: int = Field(2_000_000, gt=0)     # zero or negative would silently reject every upload, so it is a startup error
    max_batch_rows: int = Field(5_000, gt=0)
    max_export_rows: int = Field(50_000, gt=0)

    # Optional shared secret. When set, every endpoint except /api/health needs header X-API-Key.
    api_key: str | None = None

    @field_validator("model_bundle_dir")
    @classmethod
    def _resolve_bundle_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @field_validator("site_guidance_file", mode="before")
    @classmethod
    def _resolve_site_guidance(cls, value):
        if value in (None, ""):
            return None
        p = Path(value)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, url: str) -> str:
        url = url.strip()
        # Hosted providers often hand out "postgres://" or "postgresql://"; SQLAlchemy 2 + psycopg 3 needs this form.
        for old in ("postgres://", "postgresql://"):
            if url.startswith(old):
                return "postgresql+psycopg://" + url[len(old):]
        if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
            raw = url[len("sqlite:///"):]
            if raw and not Path(raw).is_absolute() and not (len(raw) > 1 and raw[1] == ":"):
                return "sqlite:///" + (BACKEND_DIR / raw).as_posix()
        return url

    @field_validator("log_level", mode="before")
    @classmethod
    def _log_level_any_case(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("api_key")
    @classmethod
    def _blank_key_is_none(cls, v: str | None) -> str | None:
        v = v or None
        if v is not None and not (v.isascii() and v.isprintable()):
            # The key travels in an HTTP header, which can only carry ASCII reliably; a non-ASCII key could never be matched by any client.
            raise ValueError("API_KEY must contain only printable ASCII characters.")
        return v

    @model_validator(mode="after")
    def _production_rules(self) -> "Settings":
        if self.environment == "production":
            origins = self.cors_origin_list
            if not origins or "*" in origins:
                raise ValueError("In production CORS_ORIGINS must list explicit frontend origins (no '*', not empty).")
            if self.allow_smoke_test_bundle:
                raise ValueError("ALLOW_SMOKE_TEST_BUNDLE must be false in production.")
            if self.auto_create_tables:
                raise ValueError("AUTO_CREATE_TABLES must be false in production; use 'alembic upgrade head'.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
