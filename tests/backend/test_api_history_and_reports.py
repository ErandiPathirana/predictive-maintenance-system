import csv
import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.models import Prediction
from app.main import create_app
from conftest import FEATURES, make_settings


@pytest.fixture
def seeded(client, readings):
    """Three stored predictions: motors A1, B1, A1 (readings differ so classes can differ)."""
    ids = []
    for motor, rid, bump in [("A1", "R1", 0), ("B1", "R2", 40), ("A1", "R3", 0)]:
        r = client.post("/api/predict", json={"record_id": rid, "motor_id": motor, "measured_at": "2025-04-01T08:00:00",
                                              "readings": {k: v + bump * 100 for k, v in readings.items()}})
        assert r.status_code == 200
        ids.append(r.json()["prediction_id"])
    return ids


def set_dates(client, pid, created=None, measured=None):
    with client.app.state.session_factory() as s:
        row = s.get(Prediction, pid)
        if created: row.created_at = created
        if measured: row.measured_at = measured
        s.commit()


def test_history_newest_first_with_pagination(client, seeded):
    body = client.get("/api/predictions", params={"limit": 2}).json()
    assert body["total"] == 3 and [i["id"] for i in body["items"]] == [seeded[2], seeded[1]]
    assert [i["id"] for i in client.get("/api/predictions", params={"limit": 2, "offset": 2}).json()["items"]] == [seeded[0]]


def test_filter_by_motor_record_and_class(client, seeded):
    assert client.get("/api/predictions", params={"motor_id": "A1"}).json()["total"] == 2
    assert client.get("/api/predictions", params={"record_id": "R2"}).json()["total"] == 1
    assert client.get("/api/predictions", params={"motor_id": "NOPE"}).json()["items"] == []
    cls = client.get("/api/predictions/%d" % seeded[0]).json()["predicted_condition"]
    assert all(i["predicted_condition"] == cls for i in client.get("/api/predictions", params={"predicted_condition": cls}).json()["items"])


def test_filter_by_prediction_date(client, seeded):
    set_dates(client, seeded[0], created=datetime(2020, 1, 15, 23, 59))
    assert client.get("/api/predictions", params={"date_to": "2020-01-15"}).json()["total"] == 1       # inclusive end date
    assert client.get("/api/predictions", params={"date_to": "2020-01-14"}).json()["total"] == 0
    assert client.get("/api/predictions", params={"date_from": "2020-01-16"}).json()["total"] == 2
    assert client.get("/api/predictions", params={"date_from": "2020-01-15", "date_to": "2020-01-15", "motor_id": "A1"}).json()["total"] == 1


def test_filter_by_measurement_date(client, seeded):
    set_dates(client, seeded[1], measured=datetime(2024, 6, 1, 12, 0))
    assert client.get("/api/predictions", params={"measured_from": "2024-06-01", "measured_to": "2024-06-01"}).json()["total"] == 1


@pytest.mark.parametrize("params", [{"date_from": "2025-02-01", "date_to": "2025-01-01"}, {"date_from": "not-a-date"},
                                    {"limit": 0}, {"limit": 501}, {"offset": -1}, {"motor_id": "x" * 65}])
def test_bad_history_queries_are_422(client, params):
    r = client.get("/api/predictions", params=params)
    assert r.status_code == 422 and "error" in r.json()


def test_unknown_prediction_is_404(client):
    r = client.get("/api/predictions/999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def parse(resp):
    return list(csv.reader(io.StringIO(resp.text)))


def test_export_csv_contents(client, seeded):
    r = client.get("/api/reports/predictions.csv")
    rows = parse(r)
    assert r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    assert rows[0][:5] == ["prediction_id", "batch_id", "source", "record_id", "motor_id"]
    for col in ("model_score_Normal", "model_score_Alert", "model_score_Danger", "predicted_condition", "model_version", "demonstration_only", "note"):
        assert col in rows[0]
    assert len(rows) == 4 and r.headers["x-total-matching"] == "3" and r.headers["x-export-truncated"] == "false"
    assert "NOT a confirmed machine failure" in rows[1][-1]


def test_export_respects_filters(client, seeded):
    rows = parse(client.get("/api/reports/predictions.csv", params={"motor_id": "B1"}))
    assert len(rows) == 2 and rows[1][4] == "B1"
    assert len(parse(client.get("/api/reports/predictions.csv", params={"motor_id": "none"}))) == 1   # header only


def test_export_is_safe_against_formula_injection(client, readings):
    client.post("/api/predict", json={"record_id": "-R1", "motor_id": "-X1", "readings": readings})
    row = parse(client.get("/api/reports/predictions.csv"))[1]
    assert row[3] == "'-R1" and row[4] == "'-X1"


def test_export_row_limit_is_reported(bundle_dir, readings):
    with TestClient(create_app(make_settings(bundle_dir, max_export_rows=2))) as c:
        for i in range(3):
            c.post("/api/predict", json={"record_id": f"R{i}", "readings": readings})
        r = c.get("/api/reports/predictions.csv")
        assert len(parse(r)) == 3 and r.headers["x-export-truncated"] == "true" and r.headers["x-total-matching"] == "3"
