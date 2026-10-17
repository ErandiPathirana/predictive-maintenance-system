"""Stage 2: manual assessments, recommendations wired to the real prediction path, saving, idempotency and failure handling."""
import dataclasses
import json
import logging

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app
from conftest import csv_text, make_settings, upload

URL = "/api/assessments"


def body(readings, **extra):
    return {"motor_id": "MOT01", "measured_at": "2025-04-01T07:20:00", **extra, "readings": readings}


def force_class(monkeypatch, k, n=3):
    """Makes the model 'predict' class k so every condition-to-recommendation path can be exercised without depending on random weights."""
    def fake(bundle, X):
        out = np.full((len(X), n), 0.05)
        out[:, k] = 0.9
        return out
    monkeypatch.setattr("app.api.routes_assessments.score_matrix", fake)


# ---------- valid assessment ----------
def test_valid_assessment_is_predicted_saved_and_returned_with_recommendations(client, readings):
    r = client.post(URL, json=body(readings, equipment_description="Pump 3 drive motor", recorded_by="E.P."), headers={"Idempotency-Key": "form-0001-abcd"})
    assert r.status_code == 201
    b = r.json()
    assert b["saved"] is True and b["duplicate"] is False and b["assessment_id"] >= 1
    assert b["motor_id"] == "MOT01" and b["measured_at"].startswith("2025-04-01T07:20") and b["model_version"] == "v9.9.9"
    assert b["predicted_condition"] in ("Normal", "Alert", "Danger") and b["recommendations"]["condition"] == b["predicted_condition"]
    assert b["recorded_by"] == "E.P." and b["recorded_by_verified"] is False and b["equipment_description"] == "Pump 3 drive motor"
    assert b["scores_are_calibrated_probabilities"] is False and abs(sum(b["scores"].values()) - 1) < 1e-6
    assert "NOT a confirmed machine failure" in b["interpretation_note"]
    assert b["readings"] == {k: float(v) for k, v in readings.items()} and b["readings_stored"] is False
    assert b["recommendations"]["items"] and b["recommendations"]["disclaimer"] and b["recommendations"]["threshold_note"]


def test_prediction_matches_the_batch_pipeline_for_the_same_readings(client, readings, loaded):
    one = client.post(URL, json=body(readings)).json()
    row = {"record_id": "R1", "motor_id": "MOT01", "measured_at": "2025-04-01 07:20:00", **{k: f"{v!r}" for k, v in readings.items()}}
    text = ",".join(row) + "\r\n" + ",".join(row.values()) + "\r\n"
    batch = upload(client, text).json()["results"][0]
    assert batch["predicted_condition"] == one["predicted_condition"]
    for c, s in one["scores"].items():
        assert abs(batch["scores"][c] - s) < 1e-9          # same preprocessing and model for manual entry and CSV


@pytest.mark.parametrize("k,name", [(0, "Normal"), (1, "Alert"), (2, "Danger")])
def test_each_predicted_class_gets_its_own_recommendations(client, readings, monkeypatch, k, name):
    force_class(monkeypatch, k)
    b = client.post(URL, json=body(readings)).json()
    assert b["predicted_condition"] == name and b["recommendations"]["condition"] == name
    rec = b["recommendations"]
    assert rec["urgent"] is (name == "Danger") and rec["available"] is True
    assert rec["items"][0]["priority"] == 1 and all(i["source"] == "general_guidance" and i["requires_confirmation"] for i in rec["items"])
    assert bool(rec["return_to_service"]) is (name != "Normal")


def test_danger_result_carries_the_safety_messages(client, readings, monkeypatch):
    force_class(monkeypatch, 2)
    rec = client.post(URL, json=body(readings)).json()["recommendations"]
    text = json.dumps(rec)
    assert "maintenance engineer immediately" in rec["items"][0]["action"] and rec["items"][0]["timing"] == "Immediate safety review"
    assert "lockout/tagout" in text and "not a safety-rated control system" in rec["disclaimer"] and "No approved engineering thresholds" in rec["threshold_note"]
    assert "qualified person has inspected" in " ".join(rec["return_to_service"])


def test_unknown_class_forced(client, readings, monkeypatch):
    reg = client.app.state.registry
    reg.bundle = dataclasses.replace(reg.bundle, class_names=["Normal", "Alert", "Critical"])
    force_class(monkeypatch, 2)
    b = client.post(URL, json=body(readings)).json()
    assert b["saved"] is True and b["predicted_condition"] == "Critical"
    assert b["recommendations"]["available"] is False and b["recommendations"]["items"] == [] and "No recommendation" in b["recommendations"]["headline"]


# ---------- persistence, history, export ----------
def test_saved_assessment_can_be_read_back_listed_and_exported(client, readings):
    made = client.post(URL, json=body(readings, equipment_description="=HYPERLINK(1)", recorded_by="E.P.")).json()
    got = client.get(f"{URL}/{made['assessment_id']}").json()
    assert got["predicted_condition"] == made["predicted_condition"] and got["recommendations"] == made["recommendations"]
    assert got["readings"] is None and got["readings_stored"] is False          # not stored by default
    hist = client.get("/api/predictions", params={"motor_id": "MOT01"}).json()
    item = hist["items"][0]
    assert hist["total"] == 1 and item["id"] == made["assessment_id"] and item["recommendation_summary"] == made["recommendations"]["summary"]
    assert item["ruleset_version"] == made["recommendations"]["ruleset_version"] and item["recorded_by"] == "E.P."
    csv = client.get("/api/reports/predictions.csv").text
    assert "recommendation_summary" in csv.splitlines()[0] and "recorded_by_unverified" in csv.splitlines()[0]
    assert "'=HYPERLINK(1)" in csv and ",=HYPERLINK" not in csv                  # spreadsheet formula injection is neutralised


def test_readings_are_stored_only_when_the_server_is_configured_to(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, store_input_readings=True))) as c:
        made = c.post(URL, json=body(readings)).json()
        assert made["readings_stored"] is True
        got = c.get(f"{URL}/{made['assessment_id']}").json()
        assert got["readings"] == {k: float(v) for k, v in readings.items()}


def test_missing_assessment_is_404(client):
    r = client.get(f"{URL}/9999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_batch_rows_store_a_summary_and_older_rows_are_regenerated_not_invented(client, loaded):
    r = upload(client, csv_text(loaded, rows=2)).json()
    item = client.get("/api/predictions").json()["items"][0]
    assert item["recommendation_summary"] and item["ruleset_version"]
    got = client.get(f"{URL}/{r['results'][0]['prediction_id']}").json()
    assert got["recommendations_regenerated"] is True and got["recommendations"]["condition"] == got["predicted_condition"]


def test_motor_list(client, readings):
    client.post(URL, json=body(readings))
    client.post(URL, json=body(readings, motor_id="MOT02"))
    items = client.get("/api/motors").json()["items"]
    assert [m["motor_id"] for m in items] == ["MOT01", "MOT02"] and items[0]["record_count"] == 1


# ---------- validation: nothing is predicted or saved ----------
def total(client):
    return client.get("/api/predictions").json()["total"]


def test_missing_sensor_value_is_rejected_and_not_saved(client, readings):
    del readings["de_h_ge"]
    r = client.post(URL, json=body(readings))
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_sensor_readings"
    assert r.json()["error"]["details"]["missing_features"] == ["de_h_ge"] and total(client) == 0


def test_unknown_sensor_name_is_rejected(client, readings):
    r = client.post(URL, json=body({**readings, "made_up": 1.0}))
    assert r.status_code == 422 and r.json()["error"]["details"]["unknown_features"] == ["made_up"] and total(client) == 0


@pytest.mark.parametrize("bad", ["abc", "", "12", True, None, [1], {"a": 1}])
def test_non_numeric_values_are_rejected(client, readings, bad):
    readings["de_h_ge"] = bad
    r = client.post(URL, json=body(readings))
    assert r.status_code == 422 and total(client) == 0


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_nan_and_infinity_are_rejected(client, readings, literal):
    raw = json.dumps(body(readings)).replace(f'"de_h_ge": {readings["de_h_ge"]}', f'"de_h_ge": {literal}')
    assert literal in raw
    r = client.post(URL, content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and total(client) == 0


@pytest.mark.parametrize("ts", ["yesterday", "2025-13-45T00:00:00", "", None, 12345.5, "2025-04-01 25:99"])
def test_bad_timestamps_are_rejected(client, readings, ts):
    b = body(readings)
    b["measured_at"] = ts
    r = client.post(URL, json=b)
    assert r.status_code == 422 and total(client) == 0


def test_timestamp_and_motor_are_required(client, readings):
    for field in ("measured_at", "motor_id"):
        b = body(readings)
        del b[field]
        assert client.post(URL, json=b).status_code == 422
    assert total(client) == 0


@pytest.mark.parametrize("field,value", [("motor_id", "bad id!"), ("motor_id", "x" * 65), ("equipment_description", "a\nb"), ("recorded_by", "a\x00b"),
                                          ("equipment_description", "x" * 121), ("recorded_by", "y" * 65)])
def test_text_fields_are_checked(client, readings, field, value):
    r = client.post(URL, json=body(readings, **{field: value}))
    assert r.status_code == 422 and total(client) == 0


def test_extra_fields_are_refused(client, readings):
    assert client.post(URL, json=body(readings, predicted_condition="Normal")).status_code == 422   # a client can never set the result


def test_timezone_aware_timestamps_are_stored_as_utc(client, readings):
    b = client.post(URL, json={**body(readings), "measured_at": "2025-04-01T10:00:00+05:30"}).json()
    assert b["measured_at"].startswith("2025-04-01T04:30:00")


def test_out_of_training_range_values_warn_but_are_accepted(client, readings):
    readings["de_h_ge"] = 1e6
    b = client.post(URL, json=body(readings)).json()
    assert b["saved"] is True and [w["feature"] for w in b["input_warnings"]] == ["de_h_ge"]
    assert any("measured and entered correctly" in i["action"] for i in b["recommendations"]["items"])


# ---------- idempotency ----------
def test_repeating_a_submission_with_the_same_key_saves_once(client, readings):
    h = {"Idempotency-Key": "form-aaaa-1111"}
    first = client.post(URL, json=body(readings), headers=h)
    second = client.post(URL, json=body(readings), headers=h)
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["duplicate"] is True and second.json()["assessment_id"] == first.json()["assessment_id"]
    assert total(client) == 1


def test_same_key_with_different_readings_is_a_conflict(client, readings):
    h = {"Idempotency-Key": "form-bbbb-2222"}
    client.post(URL, json=body(readings), headers=h)
    readings["de_h_ge"] += 1
    r = client.post(URL, json=body(readings), headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_conflict" and total(client) == 1


def test_bad_idempotency_key_is_rejected(client, readings):
    r = client.post(URL, json=body(readings), headers={"Idempotency-Key": "short"})
    assert r.status_code == 422 and total(client) == 0


def test_without_a_key_each_submission_is_separate(client, readings):
    client.post(URL, json=body(readings))
    client.post(URL, json=body(readings))
    assert total(client) == 2


# ---------- failures ----------
def test_database_failure_is_reported_as_not_saved(client, readings, monkeypatch):
    def boom(*a, **k):
        raise OperationalError("insert", {}, Exception("disk full"))
    monkeypatch.setattr("app.api.routes_assessments.repo.create_assessment", boom)
    r = client.post(URL, json=body(readings))
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable" and "nothing was recorded" in r.json()["error"]["message"]
    assert "disk full" not in r.text and "saved" not in r.json()                  # no success claim, no internal detail
    monkeypatch.undo()
    assert total(client) == 0


def test_model_unavailable_gives_an_error_not_a_fake_prediction(tmp_path, readings):
    s = make_settings(tmp_path / "missing", require_model_at_startup=False)
    with TestClient(create_app(s)) as c:
        r = c.post(URL, json=body(readings))
        assert r.status_code == 503 and r.json()["error"]["code"] == "model_not_ready"
        assert c.get("/api/predictions").json()["total"] == 0


def test_access_key_is_enforced_when_configured(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, api_key="k" * 24))) as c:
        assert c.post(URL, json=body(readings)).status_code == 401
        assert c.get("/api/motors").status_code == 401
        assert c.post(URL, json=body(readings), headers={"X-API-Key": "k" * 24}).status_code == 201


def test_cors_allows_the_idempotency_header(client):
    r = client.options(URL, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "idempotency-key,content-type"})
    assert r.status_code == 200 and "idempotency-key" in r.headers["access-control-allow-headers"].lower()


def test_logs_never_contain_sensor_values(client, readings, caplog):
    readings["de_h_ge"] = 123.456789
    with caplog.at_level(logging.DEBUG):
        client.post(URL, json=body(readings, equipment_description="Secret pump", recorded_by="E.P."))
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "123.456789" not in logged and "Secret pump" not in logged and "assessment" in logged.lower()


# ---------- site-approved guidance wiring ----------
GUIDE = {"guidance_version": "SITE-1", "approved_by": "Maintenance Manager", "approved_on": "2026-03-01",
         "conditions": {"Alert": [{"action": "Complete form MI-12.", "reason": "Site routine.", "responsible_role": "Responsible maintenance engineer",
                                   "timing": "Prompt engineering assessment", "procedure_ref": "MP-014 rev 3"}]}}


def test_site_guidance_file_adds_labelled_site_actions(bundle_dir, readings, tmp_path, monkeypatch):
    f = tmp_path / "guide.json"
    f.write_text(json.dumps(GUIDE))
    with TestClient(create_app(make_settings(bundle_dir, site_guidance_file=f))) as c:
        force_class(monkeypatch, 1)
        rec = c.post(URL, json=body(readings)).json()["recommendations"]
        site = [i for i in rec["items"] if i["source"] == "site_approved"]
        assert len(site) == 1 and "MP-014 rev 3" in site[0]["source_detail"] and rec["site_guidance_version"] == "SITE-1"


def test_invalid_site_guidance_file_stops_startup(bundle_dir, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({**GUIDE, "approved_by": ""}))
    with pytest.raises(RuntimeError, match="site guidance file is not usable"):
        with TestClient(create_app(make_settings(bundle_dir, site_guidance_file=f))):
            pass
