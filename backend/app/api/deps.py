import secrets
from collections.abc import Iterator

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthError, ModelNotReadyError
from app.services.artifacts import LoadedBundle, ModelRegistry

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


def require_bundle(registry: ModelRegistry = Depends(get_registry)) -> LoadedBundle:
    if not registry.is_ready:
        raise ModelNotReadyError(registry.public_reason)
    return registry.bundle  # type: ignore[return-value]


def api_key_guard(key: str | None = Security(api_key_header), settings: Settings = Depends(get_settings_dep)) -> None:
    if settings.api_key and not (key and secrets.compare_digest(key.encode(), settings.api_key.encode())):
        raise AuthError("A valid X-API-Key header is required.")
