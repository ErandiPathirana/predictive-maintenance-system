import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import csv_text, make_bundle, make_settings, upload


# ---------------- CORS ----------------
def test_cors_allows_only_listed_origin(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173" and "access-control-allow-origin" not in bad.headers


def test_cors_preflight(client):
    r = client.options("/api/predict", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                                "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:5173"


# ---------------- optional API key ----------------
def test_api_key_protects_everything_except_health(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, api_key="s3cret-key"))) as c:
        assert c.get("/api/health").status_code == 200 and c.get("/docs").status_code == 200
        for method, url in [("get", "/api/model-info"), ("get", "/api/predictions"), ("get", "/api/reports/predictions.csv")]:
            r = getattr(c, method)(url)
            assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
        assert c.post("/api/predict", json={"readings": readings}).status_code == 401
        assert c.get("/api/model-info", headers={"X-API-Key": "wrong"}).status_code == 401
        assert c.get("/api/model-info", headers={"X-API-Key": "s3cret-key"}).status_code == 200
        assert c.post("/api/predict", json={"readings": readings}, headers={"X-API-Key": "s3cret-key"}).status_code == 200


# ---------------- no internals leaked ----------------
def test_internal_errors_are_hidden(bundle_dir, readings, monkeypatch):
    def boom(*a, **k): raise RuntimeError("secret internal detail /etc/passwd")
    monkeypatch.setattr("app.api.routes_predict.score_matrix", boom)
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        r = c.post("/api/predict", json={"readings": readings})
        assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
        assert "secret" not in r.text and "Traceback" not in r.text and "passwd" not in r.text


def test_validation_errors_do_not_echo_submitted_values(client, readings):
    r = client.post("/api/predict", json={"readings": {**readings, "de_h_ge": "TOPSECRETVALUE"}})
    assert r.status_code == 422 and "TOPSECRETVALUE" not in r.text


# ---------------- logging ----------------
def test_logs_do_not_contain_sensor_data_or_ids(client, readings, loaded, caplog):
    caplog.set_level(logging.DEBUG)
    client.post("/api/predict", json={"record_id": "SECRETREC9", "motor_id": "SECRETMOTOR9", "readings": readings})
    upload(client, csv_text(loaded, ids=("SECRETBATCHREC{:03d}", "SECRETMOTOR{:02d}")), name="confidential_motors.csv")
    log = caplog.text
    assert "POST /api/predict" in log                                           # something was logged...
    for secret in ("SECRETREC9", "SECRETMOTOR", "SECRETBATCHREC", "confidential_motors", str(readings["de_h_ge"]), str(readings["load_percent"])):
        assert secret not in log, secret                                        # ...but never the confidential parts


# ---------------- startup behaviour ----------------
def test_missing_model_stops_startup_with_clear_message(tmp_path):
    with pytest.raises(RuntimeError, match="STARTUP ABORTED.*not found"):
        with TestClient(create_app(make_settings(tmp_path / "missing"))):
            pass


def test_incomplete_bundle_stops_startup(bundle_dir):
    (bundle_dir / "weights.npz").unlink()
    with pytest.raises(RuntimeError, match="weights.npz"):
        with TestClient(create_app(make_settings(bundle_dir))):
            pass


def test_smoke_test_bundle_stops_startup(tmp_path):
    make_bundle(tmp_path / "b", fast_debug=True)
    with pytest.raises(RuntimeError, match="smoke-test"):
        with TestClient(create_app(make_settings(tmp_path / "b"))):
            pass


def test_missing_database_tables_stop_startup_with_instructions(bundle_dir):
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        with TestClient(create_app(make_settings(bundle_dir, auto_create_tables=False))):
            pass


def test_degraded_mode_when_model_not_required(tmp_path, readings):
    with TestClient(create_app(make_settings(tmp_path / "missing", require_model_at_startup=False))) as c:
        h = c.get("/api/health").json()
        assert h["status"] == "degraded" and h["model_ready"] is False
        info = c.get("/api/model-info").json()
        assert info["model_ready"] is False and "missing" not in info["reason"] and "/" not in info["reason"]
        for r in (c.post("/api/predict", json={"readings": readings}), c.get("/api/features"), upload(c, "a,b\n1,2\n")):
            assert r.status_code == 503 and r.json()["error"]["code"] == "model_not_ready"
        assert c.get("/api/predictions").status_code == 200       # history still works without a model


# ---------------- demonstration flag ----------------
def test_demonstration_flag_logic(tmp_path, readings):
    make_bundle(tmp_path / "verified", provisional=False)
    with TestClient(create_app(make_settings(tmp_path / "verified"))) as c:
        assert c.post("/api/predict", json={"readings": readings}).json()["demonstration_only"] is False
    with TestClient(create_app(make_settings(tmp_path / "verified", force_demonstration_banner=True))) as c:
        assert c.post("/api/predict", json={"readings": readings}).json()["demonstration_only"] is True


def test_query_strings_are_not_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    client.get("/api/predictions", params={"motor_id": "SECRETMOTOR7", "record_id": "SECRETREC7"})
    client.get("/api/reports/predictions.csv", params={"motor_id": "SECRETMOTOR7"})
    # inspect only the application's own loggers (the httpx TEST CLIENT logs its own URLs, which is not the server)
    ours = "\n".join(r.getMessage() for r in caplog.records if not r.name.startswith("httpx"))
    assert "GET /api/predictions" in ours
    assert "SECRETMOTOR7" not in ours and "SECRETREC7" not in ours


def test_uvicorn_access_log_query_strings_are_stripped(client):
    """uvicorn writes the full request line itself; our filter must strip the query string."""
    from app.core.logging_utils import QueryStringStripFilter
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", "/api/predictions?motor_id=SECRETMOTOR7&limit=1", "1.1", 200), None)
    assert QueryStringStripFilter().filter(rec) is True
    assert "SECRETMOTOR7" not in rec.getMessage() and "/api/predictions" in rec.getMessage()
    assert any(isinstance(f, QueryStringStripFilter) for f in logging.getLogger("uvicorn.access").filters)   # installed by create_app
