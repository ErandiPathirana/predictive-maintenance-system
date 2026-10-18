"""Starts the REAL FastAPI backend for browser tests, on a bundle that always predicts one chosen class.

Usage (from the repository root):   python tests/e2e/start_backend.py Danger [--port 8000] [--seed-history]
Classes: Normal | Alert | Danger | none   ('none' starts the server with NO model bundle, to test the 'model unavailable' screen).
The weights are made up. The output tests the SOFTWARE, never the model quality. A temporary SQLite file is used and deleted on exit.
"""
import argparse, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "tests" / "backend")]
os.environ.setdefault("PM_LOG_LEVEL", "WARNING")

import uvicorn  # noqa: E402
from qa_support import build_forced_bundle  # noqa: E402
from conftest import CLASSES, make_settings  # noqa: E402
from app.main import create_app  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("condition", choices=CLASSES + ["none"])
ap.add_argument("--port", type=int, default=8000)
ap.add_argument("--delay", type=float, default=0.0, help="seconds of artificial delay on every /api/* request (loading-state test)")
a = ap.parse_args()

tmp = Path(tempfile.mkdtemp(prefix="pm_e2e_"))
bundle = tmp / "bundle"
if a.condition != "none":
    build_forced_bundle(bundle, CLASSES.index(a.condition))
else:
    bundle.mkdir()
settings = make_settings(bundle, database_url=f"sqlite:///{(tmp / 'e2e.db').as_posix()}", cors_origins="http://localhost:5173,http://127.0.0.1:5173", require_model_at_startup=(a.condition != "none"))
app = create_app(settings)
if a.delay:
    import asyncio
    @app.middleware("http")
    async def slow(request, call_next):
        if request.url.path.startswith("/api/") and request.url.path != "/api/health":
            await asyncio.sleep(a.delay)
        return await call_next(request)
uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
