import secrets
from collections.abc import Iterator

from fastapi import Depends, Path, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthError, ModelNotReadyError
from app.services.artifacts import LoadedBundle, ModelRegistry

# A database row ID. The upper bound stops values that no database integer column can hold from reaching the driver (SQLite raised OverflowError).
def row_id():
    """A fresh Path() per parameter: FastAPI binds the parameter name into the object, so one instance must not be shared."""
    return Path(ge=1, le=2**63 - 1, description="Numeric ID (1 or greater).")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Only required when the server sets API_KEY.")


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_site_guidance(request: Request):
    return getattr(request.app.state, "site_guidance", None)


def require_bundle(registry: ModelRegistry = Depends(get_registry)) -> LoadedBundle:
    if not registry.is_ready:
        raise ModelNotReadyError(registry.public_reason)
    return registry.bundle  # type: ignore[return-value]


def api_key_guard(key: str | None = Security(api_key_header), settings: Settings = Depends(get_settings_dep)) -> None:
    if settings.api_key and not (key and secrets.compare_digest(key.encode(), settings.api_key.encode())):
        raise AuthError("A valid X-API-Key header is required.")
