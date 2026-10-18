"""QA areas 11, 12, 17: database writes/reads/transactions, history retrieval, CSV export + filters, duplicate-submission protection.

Category: synthetic_bundle. Tests marked [mock_ml-style fault injection] break the DATABASE layer on purpose; the model is untouched.
"""

import csv
import io
import threading
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import Prediction, UploadBatch
from app.main import create_app
from conftest import csv_text, make_settings, upload
from qa_support import make_assessment_body

KEY = "qa-idempotency-key-0001"


def db_counts(client) -> tuple[int, int]:
    with client.app.state.session_factory() as s:
        return s.scalar(select(func.count()).select_from(Prediction)), s.scalar(select(func.count()).select_from(UploadBatch))


def db_down(*a, **k):
    raise OperationalError("INSERT ...", {"motor": "SECRET-MOTOR"}, Exception("connection to server failed: password=hunter2"))


def parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


# =============================== AREA 11: writes, reads, transactions ===============================
def test_a11_single_prediction_row_is_complete_and_matches_the_response(client, readings):
    r = client.post("/api/predict", json={"record_id": "R-1", "motor_id": "M-1", "measured_at": "2025-04-01T07:20:00", "readings": readings}).json()
    with client.app.state.session_factory() as s:
        row = s.get(Prediction, r["prediction_id"])
        assert (row.source, row.record_id, row.motor_id, row.batch_id) == ("single", "R-1", "M-1", None)
        assert row.measured_at == datetime(2025, 4, 1, 7, 20) and row.created_at is not None
        assert row.predicted_condition == r["predicted_condition"] and row.scores == r["scores"] and row.model_version == "v9.9.9"
        assert row.input_readings is None, "sensor values must not be stored unless STORE_INPUT_READINGS=true"


def test_a11_batch_creates_one_batch_row_and_n_prediction_rows_linked_to_it(client, loaded):
    j = upload(client, csv_text(loaded, rows=5)).json()
    assert db_counts(client) == (5, 1)
    with client.app.state.session_factory() as s:
        b = s.get(UploadBatch, j["batch_id"])
        assert (b.filename, b.record_count, b.model_version) == ("data.csv", 5, "v9.9.9")
        assert s.scalar(select(func.count()).select_from(Prediction).where(Prediction.batch_id == j["batch_id"])) == 5
    assert [x["id"] for x in client.get("/api/batches").json()["items"]] == [j["batch_id"]]


def test_a11_data_survives_a_service_restart(tmp_path, bundle_dir, readings):
    url = f"sqlite:///{(tmp_path / 'keep.db').as_posix()}"
    with TestClient(create_app(make_settings(bundle_dir, database_url=url))) as c:
        pid = c.post("/api/predict", json={"motor_id": "M-KEEP", "readings": readings}).json()["prediction_id"]
    with TestClient(create_app(make_settings(bundle_dir, database_url=url, auto_create_tables=False))) as c:
        assert c.get(f"/api/predictions/{pid}").json()["motor_id"] == "M-KEEP"


@pytest.mark.parametrize("breakpoint", ["commit", "create_predictions"])
def test_a11_batch_database_failure_is_503_and_leaves_no_partial_data(bundle_dir, loaded, monkeypatch, caplog, breakpoint):
    """FAULT INJECTION. DEFECT D8: this used to answer HTTP 500 (the assessment endpoint already answered 503)."""
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        if breakpoint == "commit":
            monkeypatch.setattr(Session, "commit", db_down)
        else:
            from app.db import repository
            real = repository.create_predictions

            def write_then_fail(*a, **k):
                real(*a, **k)          # rows are flushed into the open transaction...
                db_down()              # ...then the database fails: everything must be rolled back
            monkeypatch.setattr("app.api.routes_predict.repo.create_predictions", write_then_fail)
        r = upload(c, csv_text(loaded, rows=4))
        monkeypatch.undo()
        assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
        assert "hunter2" not in r.text and "SECRET-MOTOR" not in r.text and "INSERT" not in r.text
        assert db_counts(c) == (0, 0), "a failed batch must leave neither predictions nor an orphan batch row"
        assert "hunter2" not in caplog.text and "SECRET-MOTOR" not in caplog.text, "driver error text must not reach the logs"
        assert upload(c, csv_text(loaded, rows=4)).status_code == 200          # and the service recovers


def test_a11_single_prediction_database_failure_is_503_and_stores_nothing(bundle_dir, readings, monkeypatch):
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        monkeypatch.setattr(Session, "commit", db_down)
        r = c.post("/api/predict", json={"readings": readings})
        monkeypatch.undo()
        assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
        assert db_counts(c) == (0, 0)


def test_a11_assessment_database_failure_says_nothing_was_recorded(bundle_dir, readings, monkeypatch):
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        monkeypatch.setattr(Session, "commit", db_down)
        r = c.post("/api/assessments", json=make_assessment_body(readings))
        monkeypatch.undo()
        assert r.status_code == 503 and "nothing was recorded" in r.json()["error"]["message"] and db_counts(c) == (0, 0)


@pytest.mark.parametrize("url", ["/api/predictions", "/api/predictions/1", "/api/batches", "/api/motors", "/api/reports/predictions.csv"])
def test_a11_read_failures_are_503_not_500(bundle_dir, readings, monkeypatch, url):
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        c.post("/api/predict", json={"readings": readings})
        monkeypatch.setattr(Session, "scalar", db_down)
        monkeypatch.setattr(Session, "scalars", db_down)
        monkeypatch.setattr(Session, "execute", db_down)
        monkeypatch.setattr(Session, "get", db_down)
        r = c.get(url)
        assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable" and "hunter2" not in r.text


def test_a11_missing_tables_stop_startup_with_instructions(bundle_dir):
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        with TestClient(create_app(make_settings(bundle_dir, auto_create_tables=False))):
            pass


def test_a11_committed_data_is_visible_to_a_second_independent_session(client, readings):
    pid = client.post("/api/assessments", json=make_assessment_body(readings)).json()["assessment_id"]
    with client.app.state.session_factory() as other:
        assert other.get(Prediction, pid) is not None


# =============================== AREA 11/12: history ===============================
@pytest.fixture
def seeded(client, loaded):
    """6 predictions: 3 motors x 2 days of measurement, via CSV so measured_at is controlled."""
    rows = [("R1", "MOT-A", "2025-04-01 08:00:00"), ("R2", "MOT-A", "2025-04-02 23:59:59"), ("R3", "MOT-B", "2025-04-02 00:00:00"),
            ("R4", "MOT-B", "2025-04-03 00:00:00"), ("R5", "MOT-C", "2025-04-03 12:00:00"), ("R6", "MOT-C", "2025-04-04 12:00:00")]
    lines = ["record_id,motor_id,measured_at," + ",".join(loaded.feature_names)]
    for rid, mid, ts in rows:
        lines.append(",".join([rid, mid, ts, *[f"{m:.3f}" for m in loaded.mean]]))
    assert upload(client, "\r\n".join(lines) + "\r\n").status_code == 200
    return client


def test_a12_history_is_newest_first_and_paging_is_gapless(seeded):
    ids = []
    for off in range(0, 6, 2):
        page = seeded.get("/api/predictions", params={"limit": 2, "offset": off}).json()
        assert page["total"] == 6 and len(page["items"]) == 2
        ids += [i["id"] for i in page["items"]]
    assert ids == sorted(ids, reverse=True) and len(set(ids)) == 6
    assert seeded.get("/api/predictions", params={"limit": 2, "offset": 6}).json()["items"] == []
    assert seeded.get("/api/predictions", params={"limit": 500}).status_code == 200


def test_a12_filter_by_motor_is_exact_not_partial(seeded):
    assert {i["motor_id"] for i in seeded.get("/api/predictions", params={"motor_id": "MOT-A"}).json()["items"]} == {"MOT-A"}
    assert seeded.get("/api/predictions", params={"motor_id": "MOT"}).json()["total"] == 0
    assert seeded.get("/api/predictions", params={"motor_id": "mot-a"}).json()["total"] == 0          # case-sensitive by design
    assert seeded.get("/api/predictions", params={"motor_id": "' OR 1=1 --"}).json()["total"] == 0


def test_a12_measured_date_range_is_inclusive_on_both_ends_and_includes_the_whole_last_day(seeded):
    def rec_ids(**p):
        return sorted(i["record_id"] for i in seeded.get("/api/predictions", params=p, ).json()["items"])
    assert rec_ids(measured_from="2025-04-02", measured_to="2025-04-02") == ["R2", "R3"]          # 00:00:00 and 23:59:59 both inside
    assert rec_ids(measured_from="2025-04-03") == ["R4", "R5", "R6"]
    assert rec_ids(measured_to="2025-04-01") == ["R1"]
    assert rec_ids(measured_from="2025-04-05") == []
    assert rec_ids(measured_from="2025-04-02", measured_to="2025-04-03", motor_id="MOT-B") == ["R3", "R4"]


def test_a12_prediction_date_filter_uses_utc_creation_time(seeded):
    today = datetime.utcnow().date().isoformat()
    assert seeded.get("/api/predictions", params={"date_from": today, "date_to": today}).json()["total"] == 6
    assert seeded.get("/api/predictions", params={"date_to": "2000-01-01"}).json()["total"] == 0
    assert seeded.get("/api/predictions", params={"date_from": "2999-01-01"}).json()["total"] == 0


def test_a12_condition_batch_and_record_filters_combine_with_and(seeded):
    page = seeded.get("/api/predictions").json()["items"]
    cond, batch = page[0]["predicted_condition"], page[0]["batch_id"]
    n = sum(i["predicted_condition"] == cond for i in page)
    assert seeded.get("/api/predictions", params={"predicted_condition": cond, "batch_id": batch}).json()["total"] == n
    assert seeded.get("/api/predictions", params={"record_id": "R3", "motor_id": "MOT-A"}).json()["total"] == 0
    assert seeded.get("/api/predictions", params={"record_id": "R3"}).json()["total"] == 1


# =============================== AREA 12: CSV export ===============================
def test_a12_export_has_the_documented_header_and_matches_the_history(seeded):
    r = seeded.get("/api/reports/predictions.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].count(".csv") == 1 and "predictions_" in r.headers["content-disposition"]
    rows = parse_csv(r.text)
    hist = seeded.get("/api/predictions", params={"limit": 500}).json()["items"]
    assert len(rows) == len(hist) == 6 == int(r.headers["x-rows-exported"]) == int(r.headers["x-total-matching"])
    assert r.headers["x-export-truncated"] == "false"
    assert {x["prediction_id"] for x in rows} == {str(h["id"]) for h in hist}
    for needed in ("record_id", "motor_id", "measured_at", "predicted_condition", "model_score_Normal", "model_score_Alert", "model_score_Danger",
                   "model_version", "demonstration_only", "note"):
        assert needed in rows[0], needed
    assert "NOT a confirmed machine failure" in rows[0]["note"]


def test_a12_export_applies_the_same_filters_as_history(seeded):
    params = {"motor_id": "MOT-B", "measured_from": "2025-04-02", "measured_to": "2025-04-02"}
    rows = parse_csv(seeded.get("/api/reports/predictions.csv", params=params).text)
    assert [x["record_id"] for x in rows] == ["R3"]
    assert seeded.get("/api/reports/predictions.csv", params={"motor_id": "NOBODY"}).headers["x-total-matching"] == "0"
    assert parse_csv(seeded.get("/api/reports/predictions.csv", params={"motor_id": "NOBODY"}).text) == []
    assert seeded.get("/api/reports/predictions.csv", params={"date_from": "2025-02-01", "date_to": "2025-01-01"}).status_code == 422


def test_a12_export_row_limit_is_reported_not_silent(bundle_dir, loaded):
    with TestClient(create_app(make_settings(bundle_dir, max_export_rows=2))) as c:
        upload(c, csv_text(loaded, rows=5))
        r = c.get("/api/reports/predictions.csv")
        assert len(parse_csv(r.text)) == 2 and r.headers["x-total-matching"] == "5" and r.headers["x-export-truncated"] == "true"


def test_a12_export_is_safe_in_spreadsheets_and_keeps_unicode(client, readings):
    nasty = {"equipment_description": "=HYPERLINK(\"http://evil\",\"x\")", "recorded_by": "@SUM(A1)"}
    client.post("/api/assessments", json=make_assessment_body(readings, **nasty))
    client.post("/api/assessments", json=make_assessment_body(readings, equipment_description="Pümpe – Ölkühler 東京"))
    rows = parse_csv(client.get("/api/reports/predictions.csv").content.decode("utf-8"))
    assert rows[0]["equipment_description"].startswith("'=") and rows[0]["recorded_by_unverified"].startswith("'@")
    assert rows[1]["equipment_description"] == "Pümpe – Ölkühler 東京"


def test_a12_every_export_row_round_trips_scores_to_six_decimals(seeded):
    rows = parse_csv(seeded.get("/api/reports/predictions.csv").text)
    hist = {str(h["id"]): h for h in seeded.get("/api/predictions", params={"limit": 500}).json()["items"]}
    for r in rows:
        for c in ("Normal", "Alert", "Danger"):
            assert abs(float(r[f"model_score_{c}"]) - hist[r["prediction_id"]]["scores"][c]) < 1e-6


# =============================== AREA 17: duplicates and invalid requests ===============================
def test_a17_same_idempotency_key_saves_once_and_replays_the_original(client, readings):
    h = {"Idempotency-Key": KEY}
    first = client.post("/api/assessments", json=make_assessment_body(readings), headers=h)
    second = client.post("/api/assessments", json=make_assessment_body(readings), headers=h)
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["duplicate"] is True and second.json()["assessment_id"] == first.json()["assessment_id"]
    assert second.json()["scores"] == first.json()["scores"] and db_counts(client)[0] == 1


def test_a17_same_key_with_any_changed_field_is_409(client, readings):
    h = {"Idempotency-Key": KEY}
    client.post("/api/assessments", json=make_assessment_body(readings), headers=h)
    for change in ({"motor_id": "OTHER"}, {"measured_at": "2025-04-01T07:21:00"}, {"recorded_by": "ZZ"}, {"readings": {**readings, "load_percent": 1.0}}):
        body = {**make_assessment_body(readings), **change}
        r = client.post("/api/assessments", json=body, headers=h)
        assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_conflict", change
    assert db_counts(client)[0] == 1


@pytest.mark.parametrize("bad", ["short", "has space in it", "x" * 65, "semi;colon-key1", "ключ-ключ-ключ", "bad\nkey-1234"])
def test_a17_malformed_idempotency_keys_are_rejected(client, readings, bad):
    try:
        r = client.post("/api/assessments", json=make_assessment_body(readings), headers={"Idempotency-Key": bad})
    except (UnicodeEncodeError, ValueError):           # the HTTP client itself refuses some header values
        return
    assert r.status_code == 422 and db_counts(client)[0] == 0


def test_a17_a_failed_first_attempt_does_not_burn_the_key(bundle_dir, readings, monkeypatch):
    with TestClient(create_app(make_settings(bundle_dir)), raise_server_exceptions=False) as c:
        monkeypatch.setattr(Session, "commit", db_down)
        assert c.post("/api/assessments", json=make_assessment_body(readings), headers={"Idempotency-Key": KEY}).status_code == 503
        monkeypatch.undo()
        retry = c.post("/api/assessments", json=make_assessment_body(readings), headers={"Idempotency-Key": KEY})
        assert retry.status_code == 201 and retry.json()["duplicate"] is False and db_counts(c)[0] == 1


def test_a17_eight_simultaneous_identical_submissions_save_exactly_one_row(tmp_path, bundle_dir, readings):
    """Concurrency: file-based SQLite and real threads. Exactly one request may create the row; the rest must replay it."""
    url = f"sqlite:///{(tmp_path / 'race.db').as_posix()}"
    with TestClient(create_app(make_settings(bundle_dir, database_url=url)), raise_server_exceptions=False) as c:
        results, barrier = [], threading.Barrier(8)

        def go():
            barrier.wait()
            r = c.post("/api/assessments", json=make_assessment_body(readings), headers={"Idempotency-Key": KEY})
            results.append((r.status_code, r.json().get("assessment_id")))
        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        codes = sorted(s for s, _ in results)
        assert codes.count(201) == 1 and all(s in (200, 201) for s in codes), codes
        assert len({i for _, i in results}) == 1
        assert db_counts(c)[0] == 1


def test_a17_without_a_key_two_identical_assessments_are_two_records(client, readings):
    for _ in range(2):
        assert client.post("/api/assessments", json=make_assessment_body(readings)).status_code == 201
    assert db_counts(client)[0] == 2


@pytest.mark.xfail(strict=True, reason="KNOWN GAP (risk R1): POST /api/predict and /api/predict/batch accept no Idempotency-Key, so a double-click or "
                                       "network retry stores the same upload twice. Only /api/assessments is protected.")
def test_a17_known_gap_identical_csv_upload_twice_is_stored_twice(client, loaded):
    text = csv_text(loaded, rows=3)
    upload(client, text)
    upload(client, text)
    assert db_counts(client) == (3, 1), "a repeated identical upload should not create a second batch"


def test_a17_invalid_requests_never_write_anything(client, readings, loaded):
    client.post("/api/predict", json={"readings": {}})
    client.post("/api/assessments", json={"motor_id": "bad id", "measured_at": "x", "readings": readings})
    upload(client, csv_text(loaded, rows=3, mutate=lambda r, v: v.update(de_h_ge="nan")))
    upload(client, b"%PDF-1.4 junk", name="x.csv")
    assert db_counts(client) == (0, 0)
