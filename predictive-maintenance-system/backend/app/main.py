"""FastAPI application entry point.

Run from the backend/ folder:
    python -m uvicorn app.main:app --reload
Interactive API docs:  http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.services.model_loader import ModelRegistry


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry = ModelRegistry(settings)
        registry.load()  # never raises; a missing model just means "not ready"
        app.state.registry = registry
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Proactive machine failure prediction API (research prototype). "
            "Predictions are decision support only, not a safety system."
        ),
        lifespan=lifespan,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
