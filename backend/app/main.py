"""FastAPI application entry point.

Run from the backend/ folder:   python -m uvicorn app.main:app --reload
Swagger UI: http://localhost:8000/docs
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.api import routes_assessments, routes_history, routes_predict, routes_system
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging_utils import install_privacy_filters
from app.db.models import Base
from app.db.session import build_engine, build_session_factory
from app.services.artifacts import ModelRegistry
from app.services.recommendations import SiteGuidanceError, load_site_guidance

access_log = logging.getLogger("app.access")

DESCRIPTION = """
Research prototype: classifies **recorded motor condition** (class labels) from sensor readings.

* A prediction is a **predicted condition class, not a confirmed machine failure**.
* Scores are model outputs, **not calibrated probabilities**.
* Results flagged `demonstration_only` must not be used for operational decisions.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    install_privacy_filters()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_tables:
            Base.metadata.create_all(engine)
        elif not inspect(engine).has_table("predictions"):
            raise RuntimeError("STARTUP ABORTED: database tables are missing. Run 'alembic upgrade head' in the backend folder "
                               "(or set AUTO_CREATE_TABLES=true for local development only).")
        registry = ModelRegistry(settings)
        registry.load()                                   # loads once; never trains
        if not registry.is_ready and settings.require_model_at_startup:
            raise RuntimeError(f"STARTUP ABORTED: {registry.reason}")
        app.state.registry = registry
        app.state.site_guidance = None
        if settings.site_guidance_file:
            try:
                app.state.site_guidance = load_site_guidance(settings.site_guidance_file)
            except SiteGuidanceError as exc:
                raise RuntimeError(f"STARTUP ABORTED: site guidance file is not usable. {exc}") from exc
        yield
        engine.dispose()

    app = FastAPI(title=settings.app_name, version=settings.app_version, description=DESCRIPTION, lifespan=lifespan)
    app.state.settings, app.state.session_factory, app.state.engine = settings, session_factory, engine

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key"], expose_headers=["Content-Disposition", "X-Total-Matching", "X-Rows-Exported", "X-Export-Truncated", "X-Request-ID"])

    @app.middleware("http")
    async def log_and_harden(request: Request, call_next):
        rid, start = uuid.uuid4().hex[:12], time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            access_log.error("%s %s -> 500 [req %s]", request.method, request.url.path, rid)   # path only: never query strings, bodies or sensor data
            raise
        access_log.info("%s %s -> %s in %.0f ms [req %s]", request.method, request.url.path, response.status_code,
                        (time.perf_counter() - start) * 1000, rid)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    register_error_handlers(app)
    for r in (routes_system.router, routes_system.guarded, routes_predict.router, routes_assessments.router, routes_history.router):
        app.include_router(r)

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
