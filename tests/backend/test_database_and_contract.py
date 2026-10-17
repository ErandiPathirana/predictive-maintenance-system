import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.models import Base

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def alembic_cfg(db_path):
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def test_migration_creates_exactly_the_model_schema(tmp_path):
    db = tmp_path / "m.db"
    command.upgrade(alembic_cfg(db), "head")
    engine = create_engine(f"sqlite:///{db.as_posix()}")
    insp = inspect(engine)
    assert {"predictions", "upload_batches", "alembic_version"} <= set(insp.get_table_names())
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []      # migration == models


def test_migration_downgrade_removes_tables(tmp_path):
    db = tmp_path / "m.db"
    cfg = alembic_cfg(db)
    command.upgrade(cfg, "head"); command.downgrade(cfg, "base")
    assert {"predictions", "upload_batches"}.isdisjoint(inspect(create_engine(f"sqlite:///{db.as_posix()}")).get_table_names())


def test_app_starts_on_a_migrated_database(tmp_path, bundle_dir):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import make_settings
    db = tmp_path / "m.db"
    command.upgrade(alembic_cfg(db), "head")
    with TestClient(create_app(make_settings(bundle_dir, database_url=f"sqlite:///{db.as_posix()}", auto_create_tables=False))) as c:
        assert c.get("/api/health").json()["database"] == "ok"


@pytest.mark.skipif(not os.environ.get("PM_TEST_BUNDLE_DIR"), reason="set PM_TEST_BUNDLE_DIR to check a real notebook bundle")
def test_real_notebook_bundle_satisfies_the_contract():
    from app.services.artifacts import load_bundle
    b = load_bundle(Path(os.environ["PM_TEST_BUNDLE_DIR"]), allow_smoke_test=os.environ.get("PM_TEST_ALLOW_SMOKE") == "1")
    assert b.n_features == 14 and b.class_names == ["Normal", "Alert", "Danger"]
