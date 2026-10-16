"""Application configuration.

All settings come from environment variables (or the project's .env file),
so no secret or machine-specific value is ever written in the source code.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # ignore VITE_* and other variables meant for other tools
        protected_namespaces=("settings_",),  # allow field names starting with "model_"
    )

    app_name: str = "Predictive Maintenance API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Comma-separated list of browser origins allowed to call this API.
    cors_origins: str = "http://localhost:5173"

    # Where the files exported from Google Colab live.
    model_dir: Path = PROJECT_ROOT / "ml" / "artifacts"
    model_filename: str = "model.joblib"
    schema_filename: str = "feature_schema.json"
    metadata_filename: str = "model_metadata.json"

    @field_validator("model_dir")
    @classmethod
    def _resolve_model_dir(cls, value: Path) -> Path:
        # A relative path in .env (e.g. ml/artifacts) is relative to the project root.
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def model_path(self) -> Path:
        return self.model_dir / self.model_filename

    @property
    def schema_path(self) -> Path:
        return self.model_dir / self.schema_filename

    @property
    def metadata_path(self) -> Path:
        return self.model_dir / self.metadata_filename


@lru_cache
def get_settings() -> Settings:
    return Settings()
