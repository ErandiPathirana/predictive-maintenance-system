"""QA areas 14, 16, 13: CORS, environment-variable configuration, logging, exception handling, information leakage.

Category: synthetic_bundle, except the tests marked `mock_ml` (the model is replaced by a stub that fails; they check the backend's
reaction to a broken inference step, independent of what the real model would predict).
"""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from conftest import csv_text, make_settings, upload
from qa_support import make_assessment_body

ORIGIN = "http://localhost:5173"


def env_settings(monkeypatch, **env) -> Settings:
    for k in list(__import__("os").environ):
        if k.upper() in {"ENVIRONMENT", "MODEL_BUNDLE_DIR", "DATABASE_URL", "CORS_ORIGINS", "MAX_UPLOAD_BYTES", "MAX_BATCH_ROWS", "MAX_EXPORT_ROWS", "API_KEY",
                         "LOG_LEVEL", "STORE_INPUT_READINGS", "REQUIRE_MODEL_AT_STARTUP", "AUTO_CREATE_TABLES", "ALLOW_SMOKE_TEST_BUNDLE",
                         "FORCE_DEMONSTRATION_BANNER", "SITE_GUIDANCE_FILE"}:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)


# =============================== AREA 14: CORS ===============================
def test_a14_simple_request_only_the_listed_origin_is_echoed(client):
    ok = client.get("/api/health", headers={"Origin": ORIGIN})
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    for evil in ("http://evil.example", "http://localhost:5174", "https://localhost:5173", "http://localhost:5173.evil.example", "null"):
        r = client.get("/api/health", headers={"Origin": evil})
        assert "access-control-allow-origin" not in r.headers, evil


def test_a14_preflight_rules(client):
    def pre(origin, method, headers):
        return client.options("/api/assessments", headers={"Origin": origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": headers})
    good = pre(ORIGIN, "POST", "content-type,idempotency-key,x-api-key")
    assert good.status_code == 200 and good.headers["access-control-allow-origin"] == ORIGIN
    assert pre("http://evil.example", "POST", "content-type").status_code == 400
    assert pre(ORIGIN, "DELETE", "content-type").status_code == 400                      # only GET/POST are allowed
    assert pre(ORIGIN, "PUT", "content-type").status_code == 400
    assert pre(ORIGIN, "POST", "x-custom-evil").status_code == 400
    assert "access-control-allow-credentials" not in good.headers, "cookies/credentials must not be enabled cross-origin"


def test_a14_response_headers_the_frontend_needs_are_exposed(client):
    exposed = client.get("/api/health", headers={"Origin": ORIGIN}).headers["access-control-expose-headers"].lower()
    for h in ("content-disposition", "x-total-matching", "x-rows-exported", "x-export-truncated", "x-request-id"):
        assert h in exposed


def test_a14_multiple_origins_whitespace_and_trailing_slash_are_normalised(bundle_dir):
    s = make_settings(bundle_dir, cors_origins=" http://a.example/ , https://b.example ,, ")
    assert s.cors_origin_list == ["http://a.example", "https://b.example"]
    with TestClient(create_app(s)) as c:
        assert c.get("/api/health", headers={"Origin": "http://a.example"}).headers["access-control-allow-origin"] == "http://a.example"
        assert c.get("/api/health", headers={"Origin": "https://b.example"}).headers["access-control-allow-origin"] == "https://b.example"
        assert "access-control-allow-origin" not in c.get("/api/health", headers={"Origin": "http://c.example"}).headers


def test_a14_cors_headers_are_present_on_error_responses_too(client):
    r = client.post("/api/predict", json={"readings": {}}, headers={"Origin": ORIGIN})
    assert r.status_code == 422 and r.headers["access-control-allow-origin"] == ORIGIN


# =============================== AREA 14: environment variables ===============================
def test_a14_every_documented_environment_variable_is_read(monkeypatch, tmp_path):
    s = env_settings(monkeypatch, ENVIRONMENT="production", MODEL_BUNDLE_DIR=str(tmp_path / "b"), DATABASE_URL="postgres://u:p@h:5432/db",
                     CORS_ORIGINS="https://app.example", MAX_UPLOAD_BYTES="123456", MAX_BATCH_ROWS="77", MAX_EXPORT_ROWS="88", API_KEY="k-123",
                     LOG_LEVEL="warning", STORE_INPUT_READINGS="true", REQUIRE_MODEL_AT_STARTUP="false")
    assert s.environment == "production" and s.model_bundle_dir == (tmp_path / "b").resolve()
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/db"
    assert s.cors_origin_list == ["https://app.example"]
    assert (s.max_upload_bytes, s.max_batch_rows, s.max_export_rows) == (123456, 77, 88)
    assert s.api_key == "k-123" and s.log_level == "WARNING" and s.store_input_readings is True and s.require_model_at_startup is False


def test_a14_safe_defaults_when_nothing_is_set(monkeypatch):
    s = env_settings(monkeypatch)
    assert s.environment == "development" and s.api_key is None and s.store_input_readings is False
    assert s.require_model_at_startup is True and s.allow_smoke_test_bundle is False and s.auto_create_tables is False
    assert s.cors_origin_list == ["http://localhost:5173"] and "*" not in s.cors_origins
    assert s.max_upload_bytes == 2_000_000 and s.max_batch_rows == 5_000


@pytest.mark.parametrize("name,value", [("MAX_UPLOAD_BYTES", "abc"), ("MAX_UPLOAD_BYTES", "0"), ("MAX_UPLOAD_BYTES", "-5"), ("MAX_BATCH_ROWS", "0"),
                                        ("MAX_BATCH_ROWS", "-1"), ("MAX_EXPORT_ROWS", "0"), ("ENVIRONMENT", "staging"), ("STORE_INPUT_READINGS", "maybe"),
                                        ("LOG_LEVEL", "LOUD")])
def test_a14_invalid_configuration_stops_the_app_at_startup_instead_of_misbehaving_later(monkeypatch, name, value):
    """DEFECT D9: zero/negative limits and unknown log levels were accepted, which silently rejected every upload or crashed with an unclear error."""
    with pytest.raises(ValidationError):
        env_settings(monkeypatch, **{name: value})


def test_a14_production_mode_refuses_unsafe_combinations(monkeypatch):
    for env in ({"CORS_ORIGINS": "*"}, {"CORS_ORIGINS": ""}, {"CORS_ORIGINS": "https://ok.example", "ALLOW_SMOKE_TEST_BUNDLE": "true"},
                {"CORS_ORIGINS": "https://ok.example", "AUTO_CREATE_TABLES": "true"}):
        with pytest.raises(ValidationError):
            env_settings(monkeypatch, ENVIRONMENT="production", **env)
    assert env_settings(monkeypatch, ENVIRONMENT="production", CORS_ORIGINS="https://ok.example").environment == "production"


def test_a14_validation_error_for_bad_config_does_not_print_secrets(monkeypatch):
    with pytest.raises(ValidationError) as e:
        env_settings(monkeypatch, API_KEY="super-secret-key-value", MAX_UPLOAD_BYTES="abc")
    assert "super-secret-key-value" not in str(e.value)


def test_a14_configured_limits_really_change_the_running_app(bundle_dir, loaded):
    with TestClient(create_app(make_settings(bundle_dir, max_batch_rows=1, store_input_readings=True))) as c:
        assert upload(c, csv_text(loaded, rows=2)).status_code == 422
        r = upload(c, csv_text(loaded, rows=1))
        pid = r.json()["results"][0]["prediction_id"]
        with c.app.state.session_factory() as s:
            from app.db.models import Prediction
            assert s.get(Prediction, pid).input_readings is not None


# =============================== AREA 16: API key ===============================
def test_a16_api_key_edge_cases(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, api_key="s3cret-Key-9"))) as c:
        assert c.get("/api/model-info", headers={"X-API-Key": "s3cret-Key-9"}).status_code == 200
        for bad in (b"", b" ", b"s3cret-Key", b"S3CRET-KEY-9", b"s3cret-Key-9 ", b"x" * 10_000, b"\xff\xfe", "s3cret-Key-ü".encode("utf-8")):
            r = c.get("/api/model-info", headers={"X-API-Key": bad})
            assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized", bad[:20]
        assert c.get("/api/model-info").status_code == 401
        assert "s3cret" not in c.get("/api/model-info").text


def test_a16_a_non_ascii_api_key_is_refused_at_startup_because_no_client_could_ever_send_it(monkeypatch):
    with pytest.raises(ValidationError):
        env_settings(monkeypatch, API_KEY="clé-secrète")


def test_a16_every_data_endpoint_is_protected_when_a_key_is_set(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, api_key="k-1234567"))) as c:
        open_paths = {"/api/health"}
        spec = c.get("/openapi.json").json()
        for path, ops in spec["paths"].items():
            for method in ops:
                if path in open_paths:
                    continue
                url = path.replace("{prediction_id}", "1").replace("{assessment_id}", "1")
                r = c.request(method.upper(), url, json={} if method == "post" else None)
                assert r.status_code == 401, f"{method.upper()} {path} is reachable without the API key (status {r.status_code})"


def test_a16_api_key_is_never_logged(bundle_dir, caplog):
    caplog.set_level(logging.DEBUG)
    with TestClient(create_app(make_settings(bundle_dir, api_key="log-me-not-12345"))) as c:
        c.get("/api/model-info", headers={"X-API-Key": "wrong-guess-98765"})
        c.get("/api/model-info", headers={"X-API-Key": "log-me-not-12345"})
    assert "wrong-guess-98765" not in caplog.text and "log-me-not-12345" not in caplog.text


# =============================== AREA 16/13: every response carries the safety headers ===============================
def _responses_with_every_status(client, loaded, readings):
    big = b"a,b\n" + b"1,2\n" * 1_000_000
    return {
        200: client.get("/api/health"), 201: client.post("/api/assessments", json=make_assessment_body(readings)),
        404: client.get("/api/nothing-here"), 405: client.delete("/api/predictions/1"), 422: client.post("/api/predict", json={}),
        415: upload(client, b"x", name="x.txt"),
    }


def test_a16_request_id_and_hardening_headers_on_success_and_error_responses(client, loaded, readings):
    seen = set()
    for status, r in _responses_with_every_status(client, loaded, readings).items():
        assert r.status_code == status
        assert r.headers.get("x-content-type-options") == "nosniff" and r.headers.get("cache-control") == "no-store", status
        rid = r.headers.get("x-request-id")
        assert rid and len(rid) >= 8, status
        seen.add(rid)
    assert len(seen) == 6, "request IDs must be unique per request"


@pytest.mark.mock_ml
def test_a16_request_id_and_headers_are_also_on_500_and_503_responses(bundle_dir, readings, monkeypatch):
    """MOCK (inference stub raises, to produce a 500). DEFECT D5: the outermost 500 handler bypassed the middleware, so a 500 had no X-Request-ID (nothing to quote to the operator),
    no nosniff and no no-store."""
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        monkeypatch.setattr("app.api.routes_predict.score_matrix", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        r500 = c.post("/api/predict", json={"readings": readings})
        monkeypatch.undo()
        monkeypatch.setattr(Session, "commit", lambda self: (_ for _ in ()).throw(OperationalError("x", {}, Exception("down"))))
        r503 = c.post("/api/predict", json={"readings": readings})
        monkeypatch.undo()
        r_model = TestClient(create_app(make_settings(Path("/nonexistent/x"), require_model_at_startup=False)))
        with r_model as m:
            r503b = m.get("/api/features")
    for r, status in ((r500, 500), (r503, 503), (r503b, 503)):
        assert r.status_code == status
        assert r.headers.get("x-request-id") and r.headers.get("x-content-type-options") == "nosniff" and r.headers.get("cache-control") == "no-store", status


def test_a16_every_error_uses_the_same_envelope(client, readings, loaded):
    errors = [client.get("/api/nothing"), client.delete("/api/predict"), client.post("/api/predict", json={}), client.get("/api/predictions/0"),
              client.get("/api/assessments/99999"), upload(client, b"x", name="x.txt"), upload(client, b"", name="x.csv"),
              client.post("/api/assessments", json={}), client.get("/api/predictions", params={"limit": "many"})]
    for r in errors:
        assert r.status_code >= 400
        body = r.json()
        assert list(body) == ["error"] and set(body["error"]) <= {"code", "message", "details"} and isinstance(body["error"]["code"], str)


# =============================== AREA 16: exception handling and leakage ===============================
@pytest.mark.mock_ml
def test_a16_broken_inference_gives_a_generic_500_logs_the_cause_server_side_and_stores_nothing(bundle_dir, readings, monkeypatch, caplog):
    """MOCK: inference is replaced by a function that raises, to test the backend's reaction independently of the real model."""
    caplog.set_level(logging.ERROR)

    def explode(*a, **k):
        raise RuntimeError("internal detail: /srv/secret/path/weights.npz line 42 password=hunter2")
    monkeypatch.setattr("app.api.routes_predict.score_matrix", explode)
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        r = c.post("/api/predict", json={"record_id": "REC-LEAK", "readings": readings})
        assert r.status_code == 500 and r.json() == {"error": {"code": "internal_error", "message": "Something went wrong on the server. Please try again."}}
        for secret in ("/srv/secret", "hunter2", "weights.npz", "RuntimeError", "Traceback", "line 42"):
            assert secret not in r.text
        assert c.get("/api/predictions").json()["total"] == 0
    assert "Unhandled RuntimeError" in caplog.text, "the operator must be able to find the cause in the server log"
    assert "REC-LEAK" not in caplog.text and str(readings["de_h_ge"]) not in caplog.text


@pytest.mark.mock_ml
def test_a16_model_returning_nan_for_sane_input_is_a_server_error_not_blamed_on_the_user_and_nothing_is_saved(bundle_dir, readings, monkeypatch):
    """MOCK: the forward pass returns NaN even though the input is finite (a corrupt-model situation, not a user mistake)."""
    import numpy as np
    monkeypatch.setattr("app.services.predictions.forward", lambda b, X: np.full((len(X), 3), np.nan))
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        r = c.post("/api/assessments", json=make_assessment_body(readings))
        assert r.status_code == 500 and r.json()["error"]["code"] == "prediction_failed"
        assert c.get("/api/predictions").json()["total"] == 0


@pytest.mark.mock_ml
def test_a16_response_shape_is_independent_of_the_model_when_scores_are_stubbed(bundle_dir, readings, monkeypatch):
    """MOCK: fixed scores [0.1, 0.2, 0.7]. Proves the API layer maps argmax -> 'Danger' and echoes scores untouched."""
    import numpy as np
    monkeypatch.setattr("app.api.routes_predict.score_matrix", lambda b, X: np.tile([0.1, 0.2, 0.7], (len(X), 1)))
    with TestClient(create_app(make_settings(bundle_dir))) as c:
        j = c.post("/api/predict", json={"readings": readings}).json()
        assert j["predicted_condition"] == "Danger" and j["predicted_class_id"] == 2 and j["scores"] == {"Normal": 0.1, "Alert": 0.2, "Danger": 0.7}


def test_a16_no_server_paths_or_internals_in_any_response(tmp_path, bundle_dir, readings, loaded):
    with TestClient(create_app(make_settings(bundle_dir))) as c:
        texts = [c.get(u).text for u in ("/api/health", "/api/model-info", "/api/features", "/api/template.csv", "/api/motors", "/api/batches",
                                         "/api/predictions", "/api/reports/predictions.csv", "/openapi.json", "/")]
        texts += [c.post("/api/predict", json={"readings": {}}).text, upload(c, b"%PDF junk", name="x.csv").text,
                  upload(c, csv_text(loaded, rows=1, mutate=lambda r, v: v.update(de_h_ge="bad"))).text]
    for t in texts:
        for leak in (str(tmp_path), str(bundle_dir), "/home/", "C:\\Users", "Traceback", 'File "', "sqlalchemy", "sqlite:///", "MANIFEST"):
            assert leak not in t, leak


def test_a16_logs_contain_no_query_strings_filenames_ids_or_secrets_for_failed_requests_either(client, readings, loaded, caplog):
    caplog.set_level(logging.DEBUG)
    client.get("/api/predictions", params={"motor_id": "SECRET-MOTOR-QS"})
    client.post("/api/predict", json={"motor_id": "SECRET-MOTOR-422", "readings": {**readings, "de_h_ge": "SECRET-VALUE-422"}})
    upload(client, csv_text(loaded, rows=1, mutate=lambda r, v: v.update(de_h_ge="SECRET-CELL")), name="secret-file-name.csv")
    server = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith(("app", "uvicorn")))     # SERVER logs (the test client's own httpx log is not the server)
    for s in ("SECRET-MOTOR-QS", "SECRET-MOTOR-422", "SECRET-VALUE-422", "SECRET-CELL", "secret-file-name"):
        assert s not in server, s
    assert "GET /api/predictions" in server and "-> 422" in server


def test_a16_idempotency_key_and_equipment_text_are_not_logged(client, readings, caplog):
    caplog.set_level(logging.DEBUG)
    client.post("/api/assessments", json=make_assessment_body(readings, equipment_description="SECRET-EQUIPMENT", recorded_by="SECRET-PERSON"),
                headers={"Idempotency-Key": "secret-idem-key-123"})
    for s in ("SECRET-EQUIPMENT", "SECRET-PERSON", "secret-idem-key-123"):
        assert s not in caplog.text, s
