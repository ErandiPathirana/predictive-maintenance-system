import json
from datetime import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.db.models import Prediction
from app.main import create_app
from conftest import FEATURES, csv_text, make_settings, reference_forward, upload


def post(client, readings, **extra):
    return client.post("/api/predict", json={"record_id": "R1", "motor_id": "M1", **extra, "readings": readings})


# ---------------- system ----------------
def test_health(client):
    b = client.get("/api/health").json()
    assert b["status"] == "ok" and b["model_ready"] is True and b["database"] == "ok"


def test_model_info_is_honest_about_status(client):
    b = client.get("/api/model-info").json()["bundle"]
    assert b["provisional_label_provenance"] is True and b["demonstration_only"] is True
    assert b["scores_are_calibrated_probabilities"] is False and b["deployable_for_decisions"] is False
    assert b["future_failure_prediction_supported"] is False
    assert b["classes"] == [{"id": 0, "name": "Normal"}, {"id": 1, "name": "Alert"}, {"id": 2, "name": "Danger"}]
    assert b["reported_test_metrics"] == {"n": 100, "accuracy": 0.5, "balanced_accuracy": 0.4, "macro_f1": 0.3}
    assert any("NOT a confirmed machine failure" in n for n in b["notes"])


def test_features_in_contract_order(client):
    f = client.get("/api/features").json()
    assert [x["name"] for x in f["features"]] == FEATURES and "NOT validity limits" in f["note"]


def test_template_csv_has_exact_columns(client):
    r = client.get("/api/template.csv")
    assert r.text.strip() == ",".join(["record_id", "motor_id", "measured_at", *FEATURES])
    assert "attachment" in r.headers["content-disposition"]


def test_swagger_and_openapi_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/api/health", "/api/model-info", "/api/features", "/api/template.csv", "/api/uploads/validate", "/api/predict",
              "/api/predict/batch", "/api/predictions", "/api/predictions/{prediction_id}", "/api/batches", "/api/reports/predictions.csv"]:
        assert p in paths, p


def test_security_headers_and_request_id(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store" and h["x-request-id"]


# ---------------- single prediction ----------------
def test_single_prediction_is_correct_and_stored(client, readings, truth):
    r = post(client, readings, measured_at="2025-04-01T10:00:00+02:00")
    assert r.status_code == 200
    b = r.json()
    expected = reference_forward(truth["mean"], truth["scale"], truth["layers"], np.array([[readings[n] for n in FEATURES]]))[0]
    assert b["scores"] == pytest.approx(dict(zip(["Normal", "Alert", "Danger"], expected)), abs=1e-9)
    assert sum(b["scores"].values()) == pytest.approx(1.0)
    assert b["predicted_condition"] == ["Normal", "Alert", "Danger"][int(expected.argmax())]
    assert b["scores_are_calibrated_probabilities"] is False and b["demonstration_only"] is True and b["model_version"] == "v9.9.9"
    assert "NOT a confirmed machine failure" in b["interpretation_note"]
    item = client.get(f"/api/predictions/{b['prediction_id']}").json()
    assert item["motor_id"] == "M1" and item["measured_at"] == "2025-04-01T08:00:00"    # timezone converted to UTC


def test_sensor_values_not_stored_by_default(client, readings):
    post(client, readings)
    with client.app.state.session_factory() as s:
        assert s.get(Prediction, 1).input_readings is None


def test_sensor_values_stored_only_when_enabled(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, store_input_readings=True))) as c:
        post(c, readings)
        with c.app.state.session_factory() as s:
            assert s.get(Prediction, 1).input_readings["de_h_ge"] == readings["de_h_ge"]


@pytest.mark.parametrize("bad", ["1.5", True, None, [1]])
def test_strict_numeric_types(client, readings, bad):
    r = post(client, {**readings, "de_h_ge": bad})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_integers_are_accepted(client, readings):
    assert post(client, {**readings, "rotational_speed_rpm": 1460}).status_code == 200


def test_nan_is_rejected(client, readings):
    body = json.dumps({"readings": {**readings, "de_h_ge": 0}}).replace('"de_h_ge": 0', '"de_h_ge": NaN')
    r = client.post("/api/predict", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["error"]["code"] in ("invalid_sensor_readings", "invalid_request")


def test_missing_and_unknown_features_reported(client, readings):
    r = post(client, {k: v for k, v in readings.items() if k != "load_percent"} | {"typo": 1.0})
    d = r.json()["error"]
    assert r.status_code == 422 and d["code"] == "invalid_sensor_readings"
    assert d["details"]["missing_features"] == ["load_percent"] and d["details"]["unknown_features"] == ["typo"]


def test_invalid_input_stores_nothing(client, readings):
    post(client, {"de_h_ge": 1.0})
    assert client.get("/api/predictions").json()["total"] == 0


def test_extra_top_level_fields_and_bad_ids_rejected(client, readings):
    assert client.post("/api/predict", json={"readings": readings, "admin": True}).status_code == 422
    assert post(client, readings, motor_id="bad id!").status_code == 422


def test_out_of_training_range_warns_but_still_predicts(client, readings, loaded):
    far = loaded.observed_ranges["de_h_ge"][1] + 100
    b = post(client, {**readings, "de_h_ge": far}).json()
    assert [w["feature"] for w in b["input_warnings"]] == ["de_h_ge"] and "extrapolating" in b["input_warnings"][0]["message"]


# ---------------- CSV upload ----------------
def test_batch_prediction(client, loaded):
    r = upload(client, csv_text(loaded, rows=4))
    assert r.status_code == 200
    b = r.json()
    assert b["record_count"] == 4 and sum(b["class_counts"].values()) == 4 and [x["record_id"] for x in b["results"]] == ["REC001", "REC002", "REC003", "REC004"]
    assert all(x["prediction_id"] for x in b["results"]) and b["demonstration_only"] is True
    assert client.get("/api/predictions", params={"batch_id": b["batch_id"]}).json()["total"] == 4
    assert client.get("/api/batches").json()["items"][0]["id"] == b["batch_id"]


def test_batch_results_match_single_endpoint(client, loaded, readings):
    row = upload(client, csv_text(loaded, rows=1, mutate=lambda r, v: v.update({n: repr(readings[n]) for n in FEATURES}))).json()["results"][0]
    single = post(client, readings).json()
    assert row["scores"] == pytest.approx(single["scores"], abs=1e-9)


def test_invalid_batch_is_all_or_nothing(client, loaded):
    r = upload(client, csv_text(loaded, rows=3, mutate=lambda r, v: v.update(de_h_ge="oops") if r == 1 else None))
    e = r.json()["error"]
    assert r.status_code == 422 and e["code"] == "invalid_csv" and e["details"]["issues"][0]["row"] == 3
    assert client.get("/api/predictions").json()["total"] == 0 and client.get("/api/batches").json()["items"] == []


def test_validate_endpoint_is_a_dry_run(client, loaded):
    ok = upload(client, csv_text(loaded), url="/api/uploads/validate").json()
    bad = upload(client, csv_text(loaded, drop_cols=("de_h_ge",)), url="/api/uploads/validate").json()
    assert ok["valid"] is True and bad["valid"] is False and bad["issues"][0]["column"] == "de_h_ge"
    assert client.get("/api/predictions").json()["total"] == 0


@pytest.mark.parametrize("name,data,ctype,status", [
    ("data.xlsx", b"x", "text/csv", 415), ("data.csv", b"x", "image/png", 415), ("data.csv", b"PK\x03\x04zip", "text/csv", 415),
    ("data.csv", b"a,b\x00\n1,2\n", "text/csv", 415), ("data.csv", b"MZ\x90\x00", "application/octet-stream", 415),
    ("data.csv", b"   \n", "text/csv", 422), ("data", b"a,b\n", "text/csv", 415)])
def test_unsupported_files(client, name, data, ctype, status):
    r = upload(client, data, name=name, ctype=ctype)
    assert r.status_code == status and "error" in r.json()


def test_windows_csv_content_type_is_accepted(client, loaded):
    assert upload(client, csv_text(loaded), ctype="application/vnd.ms-excel").status_code == 200


def test_file_too_large(bundle_dir, loaded):
    with TestClient(create_app(make_settings(bundle_dir, max_upload_bytes=500))) as c:
        r = upload(c, csv_text(loaded, rows=5))
        assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_record_limit(bundle_dir, loaded):
    with TestClient(create_app(make_settings(bundle_dir, max_batch_rows=3))) as c:
        r = upload(c, csv_text(loaded, rows=4))
        assert r.status_code == 422 and "Too many records" in json.dumps(r.json())


def test_uploaded_filename_is_sanitised(client, loaded):
    b = upload(client, csv_text(loaded), name="..\\..\\evil<name>.csv").json()
    assert b["filename"] == "evil_name_.csv"
