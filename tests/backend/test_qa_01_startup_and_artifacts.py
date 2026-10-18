"""QA areas 1, 2, 3, 7: startup/shutdown, loading model + preprocessing artifacts, health and model-info, missing artifacts.

Categories: tests named *_real_* use the TRAINED bundle (BLOCKED/skipped if none exists).
            everything else is `synthetic_bundle` (real loader, made-up weights) or process-level.
"""

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import BACKEND_DIR
from app.main import create_app
from app.services.artifacts import ModelArtifactError, load_bundle
from conftest import CLASSES, FEATURES, make_bundle, make_settings
from qa_support import need_real_bundle

real = pytest.mark.real_artifacts


def _dir_fingerprint(d: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir()) if p.is_file()}


# =============================== AREA 1: startup and shutdown ===============================
def test_a01_startup_loads_model_once_and_reports_ready(bundle_dir):
    with TestClient(create_app(make_settings(bundle_dir))) as c:
        assert c.get("/api/health").json() == {**c.get("/api/health").json(), "status": "ok", "model_ready": True, "database": "ok"}
        assert c.app.state.registry.is_ready


def test_a01_startup_never_modifies_the_artifact_folder_and_never_trains(bundle_dir):
    before = _dir_fingerprint(bundle_dir)
    with TestClient(create_app(make_settings(bundle_dir))) as c:
        c.get("/api/health")
    assert _dir_fingerprint(bundle_dir) == before, "startup must treat the bundle as read-only"
    assert not any(m in sys.modules for m in ("tensorflow", "keras", "sklearn", "torch")), "the backend must not need a training framework"


def test_a01_shutdown_releases_the_database_engine(bundle_dir, monkeypatch):
    app = create_app(make_settings(bundle_dir))
    disposed = []
    real_dispose = app.state.engine.dispose
    monkeypatch.setattr(app.state.engine, "dispose", lambda *a, **k: (disposed.append(True), real_dispose(*a, **k))[1])
    with TestClient(app):
        assert not disposed
    assert disposed == [True]


def test_a01_two_start_stop_cycles_give_identical_models(bundle_dir, readings):
    out = []
    for _ in range(2):
        with TestClient(create_app(make_settings(bundle_dir))) as c:
            out.append(c.post("/api/predict", json={"readings": readings}).json()["scores"])
    assert out[0] == out[1]


def test_a01_startup_failure_leaves_no_half_started_app(tmp_path):
    """Missing model + require_model_at_startup=True: the process must refuse to start, not serve 503s."""
    with pytest.raises(RuntimeError, match="STARTUP ABORTED"):
        with TestClient(create_app(make_settings(tmp_path / "missing"))):
            pass


# =============================== AREA 7: missing / damaged artifacts ===============================
@pytest.mark.parametrize("victim", ["weights.npz", "preprocessing.json", "feature_schema.json", "class_mapping.json",
                                    "model_architecture.json", "training_metadata.json", "parity_probe.json", "MANIFEST.json"])
def test_a07_each_missing_artifact_blocks_startup_and_names_the_file(bundle_dir, victim):
    (bundle_dir / victim).unlink()
    with pytest.raises(RuntimeError) as e:
        with TestClient(create_app(make_settings(bundle_dir))):
            pass
    assert victim in str(e.value)


def test_a07_degraded_mode_never_fakes_a_prediction_and_hides_server_paths(tmp_path, readings):
    missing = tmp_path / "secret_server_dir" / "no_bundle_here"
    with TestClient(create_app(make_settings(missing, require_model_at_startup=False))) as c:
        health = c.get("/api/health")
        assert health.status_code == 200 and health.json()["status"] == "degraded" and health.json()["model_ready"] is False
        info = c.get("/api/model-info")
        assert info.status_code == 200 and info.json()["model_ready"] is False and info.json()["bundle"] is None
        for r in (c.post("/api/predict", json={"readings": readings}), c.get("/api/features"), c.get("/api/template.csv")):
            assert r.status_code == 503 and r.json()["error"]["code"] == "model_not_ready"
        for r in (health, info, c.get("/api/features")):
            assert "secret_server_dir" not in r.text and str(tmp_path) not in r.text


def test_a07_history_reads_still_work_without_a_model(tmp_path):
    """History/export only read the database, so a missing model must not take them down."""
    with TestClient(create_app(make_settings(tmp_path / "none", require_model_at_startup=False))) as c:
        for url in ("/api/predictions", "/api/batches", "/api/motors", "/api/reports/predictions.csv"):
            assert c.get(url).status_code == 200, url


def test_a07_changed_weights_after_export_are_caught(bundle_dir):
    p = bundle_dir / "weights.npz"
    p.write_bytes(p.read_bytes() + b"\x00")
    with pytest.raises(ModelArtifactError, match="Checksum mismatch"):
        load_bundle(bundle_dir)


def test_a07_bundle_folder_is_a_file_not_a_folder(tmp_path):
    f = tmp_path / "bundle"
    f.write_text("not a folder")
    with pytest.raises(ModelArtifactError, match="not found"):
        load_bundle(f)


# =============================== AREA 3: health and model-info ===============================
def test_a03_health_shape_and_no_secrets(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "app_name", "app_version", "environment", "model_ready", "database"}
    for forbidden in ("sqlite", "password", "predictions.db", "bundle", "/home", "\\Users"):
        assert forbidden not in r.text


def test_a03_model_info_matches_the_loaded_bundle(client, loaded):
    info = client.get("/api/model-info").json()
    b = info["bundle"]
    assert info["model_ready"] is True
    assert b["bundle_version"] == loaded.version and b["features"] == loaded.feature_names == FEATURES
    assert [c["name"] for c in b["classes"]] == CLASSES == loaded.class_names
    assert [c["id"] for c in b["classes"]] == [0, 1, 2] and b["feature_count"] == 14
    assert b["scores_are_calibrated_probabilities"] is False and b["future_failure_prediction_supported"] is False


def test_a03_model_info_is_honest_about_synthetic_or_unverified_labels(client):
    b = client.get("/api/model-info").json()["bundle"]
    assert b["provisional_label_provenance"] is True and b["demonstration_only"] is True and b["deployable_for_decisions"] is False
    assert any("NOT a confirmed machine failure" in n for n in b["notes"])


def test_a03_health_reports_database_trouble_instead_of_crashing(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    def down(self, *a, **k):
        raise OperationalError("SELECT 1", {}, Exception("connection refused password=hunter2"))
    monkeypatch.setattr(Session, "execute", down)
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "degraded" and r.json()["database"] == "unavailable"
    assert "hunter2" not in r.text


# =============================== AREA 1/14: the real process ===============================
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_a01_real_uvicorn_process_starts_serves_and_stops_cleanly(tmp_path):
    """Process-level smoke test (synthetic bundle): proves the real entry point `app.main:app` honours environment variables."""
    d = tmp_path / "bundle"
    make_bundle(d)
    port = _free_port()
    env = {**os.environ, "ENVIRONMENT": "test", "MODEL_BUNDLE_DIR": str(d), "DATABASE_URL": f"sqlite:///{(tmp_path / 'proc.db').as_posix()}",
           "AUTO_CREATE_TABLES": "true", "CORS_ORIGINS": "http://localhost:5173", "LOG_LEVEL": "WARNING"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--host", "127.0.0.1"], cwd=BACKEND_DIR, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        body = None
        for _ in range(100):
            if proc.poll() is not None:
                pytest.fail("server exited during startup:\n" + proc.stdout.read())
            try:
                body = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2).read())
                break
            except OSError:
                time.sleep(0.2)
        assert body and body["status"] == "ok" and body["model_ready"] is True and body["environment"] == "test"
        info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/model-info", timeout=5).read())
        assert info["bundle"]["bundle_version"] == "v9.9.9"           # proves MODEL_BUNDLE_DIR from the environment was used
    finally:
        proc.terminate()
        try:
            output, _ = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("server did not shut down within 15 s of a terminate signal")
    if sys.platform != "win32":
        # uvicorn finishes its shutdown and then re-raises the signal, so the exit status is 0 or -SIGTERM; both mean "stopped on request".
        assert proc.returncode in (0, -15), f"unexpected exit status {proc.returncode}"
        assert "Application shutdown complete" in output, "the shutdown hook (lifespan) did not finish"


def test_a01_real_uvicorn_process_refuses_to_start_without_a_model(tmp_path):
    port = _free_port()
    env = {**os.environ, "ENVIRONMENT": "test", "MODEL_BUNDLE_DIR": str(tmp_path / "nothing"), "DATABASE_URL": f"sqlite:///{(tmp_path / 'p2.db').as_posix()}",
           "AUTO_CREATE_TABLES": "true"}
    proc = subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0 and "STARTUP ABORTED" in (proc.stdout + proc.stderr)


# =============================== AREA 2: the TRAINED model (BLOCKED when absent) ===============================
@real
def test_a02_real_bundle_passes_the_full_contract():
    b = load_bundle(need_real_bundle(), allow_smoke_test=False)
    assert b.feature_names == FEATURES, "feature names/order differ from the notebook contract"
    assert b.class_names == CLASSES
    assert b.fast_debug is False


@real
def test_a02_real_bundle_starts_the_application():
    with TestClient(create_app(make_settings(need_real_bundle()))) as c:
        h = c.get("/api/health").json()
        assert h["status"] == "ok" and h["model_ready"] is True
        info = c.get("/api/model-info").json()["bundle"]
        assert info["feature_count"] == 14 and info["smoke_test_bundle"] is False


@real
def test_a02_real_bundle_reproduces_the_notebooks_own_parity_probes_through_the_api():
    d = need_real_bundle()
    probes = json.loads((d / "parity_probe.json").read_text())
    tol = float(probes.get("tolerance", 1e-5))
    with TestClient(create_app(make_settings(d))) as c:
        for p in probes["probes"]:
            r = c.post("/api/predict", json={"readings": p["readings"]})
            assert r.status_code == 200, p["name"]
            got = r.json()["scores"]
            assert all(abs(got[k] - v) <= tol for k, v in p["expected_probabilities"].items()), p["name"]


@real
def test_a02_real_bundle_loads_in_a_fresh_python_process():
    d = need_real_bundle()
    code = ("import sys; sys.path.insert(0, r'%s'); from app.services.artifacts import load_bundle; "
            "b = load_bundle(r'%s'); print(b.version, len(b.feature_names), len(b.class_names))" % (BACKEND_DIR, d))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[1:] == ["14", "3"]
