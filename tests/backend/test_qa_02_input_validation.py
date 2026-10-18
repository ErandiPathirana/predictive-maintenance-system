"""QA areas 4, 6, 13: manual-assessment / single-prediction endpoints and their input validation.

Category: synthetic_bundle (real validation + inference code, made-up weights).
Every rejected request must (a) return a 4xx with the standard error envelope, never 500, (b) store nothing, (c) not echo submitted values.
"""

import json

import pytest

from conftest import FEATURES
from qa_support import make_assessment_body

ENDPOINTS = {
    "predict": ("/api/predict", lambda r, **o: {"readings": r, **o}),
    "assessment": ("/api/assessments", lambda r, **o: make_assessment_body(r, **o)),
}
both = pytest.mark.parametrize("ep", list(ENDPOINTS))


def post(client, ep, readings, **extra):
    url, build = ENDPOINTS[ep]
    return client.post(url, json=build(readings, **extra))


def post_raw(client, ep, raw_json: str):
    return client.post(ENDPOINTS[ep][0], content=raw_json, headers={"content-type": "application/json"})


def stored(client) -> int:
    return client.get("/api/predictions").json()["total"]


def assert_clean_client_error(r, *, status=422):
    assert r.status_code == status, r.text[:300]
    err = r.json()["error"]
    assert set(err) >= {"code", "message"} and err["message"]
    assert "Traceback" not in r.text


# =============================== AREA 4: manual assessment happy path ===============================
def test_a04_assessment_returns_all_documented_parts(client, readings):
    r = client.post("/api/assessments", json=make_assessment_body(readings, equipment_description="Pump 7", recorded_by="AB"))
    assert r.status_code == 201
    j = r.json()
    assert j["saved"] is True and j["duplicate"] is False and isinstance(j["assessment_id"], int)
    assert j["predicted_condition"] in ("Normal", "Alert", "Danger") and abs(sum(j["scores"].values()) - 1) < 1e-9
    assert j["recommendations"]["available"] is True and j["recommendations"]["items"]
    assert j["model_version"] == "v9.9.9" and j["demonstration_only"] is True
    assert client.get(f"/api/assessments/{j['assessment_id']}").json()["predicted_condition"] == j["predicted_condition"]


def test_a04_integers_and_floats_are_equivalent(client, readings):
    ints = {k: int(round(v)) for k, v in readings.items()}
    floats = {k: float(v) for k, v in ints.items()}
    a = client.post("/api/predict", json={"readings": ints}).json()["scores"]
    b = client.post("/api/predict", json={"readings": floats}).json()["scores"]
    assert a == b


def test_a04_reading_order_in_the_json_body_does_not_matter(client, readings):
    reordered = {k: readings[k] for k in reversed(list(readings))}
    assert client.post("/api/predict", json={"readings": readings}).json()["scores"] == \
           client.post("/api/predict", json={"readings": reordered}).json()["scores"]


# =============================== AREA 6: missing fields ===============================
@both
def test_a06_each_missing_feature_is_named_and_nothing_is_stored(client, readings, ep):
    for name in FEATURES:
        partial = {k: v for k, v in readings.items() if k != name}
        r = post(client, ep, partial)
        assert_clean_client_error(r)
        assert r.json()["error"]["details"]["missing_features"] == [name]
    assert stored(client) == 0


@both
def test_a06_empty_and_unknown_readings_rejected(client, readings, ep):
    assert_clean_client_error(post(client, ep, {}))
    r = post(client, ep, {**readings, "motor_temperature_kelvin": 300.0})
    assert_clean_client_error(r)
    assert r.json()["error"]["details"]["unknown_features"] == ["motor_temperature_kelvin"]
    assert stored(client) == 0


def test_a06_assessment_requires_motor_timestamp_and_readings(client, readings):
    for missing in ("motor_id", "measured_at", "readings"):
        body = make_assessment_body(readings)
        body.pop(missing)
        assert_clean_client_error(client.post("/api/assessments", json=body))
    assert stored(client) == 0


# =============================== AREA 6: wrong data types ===============================
WRONG_TYPES = [("text number", "12.5"), ("text", "hot"), ("bool true", True), ("bool false", False), ("null", None),
               ("list", [1.0]), ("object", {"v": 1}), ("empty string", "")]


@both
@pytest.mark.parametrize("label,value", WRONG_TYPES, ids=[w[0] for w in WRONG_TYPES])
def test_a06_wrong_reading_types_are_rejected_without_echoing_the_value(client, readings, ep, label, value):
    r = post(client, ep, {**readings, "de_h_ge": value})
    assert_clean_client_error(r)
    assert stored(client) == 0


@both
def test_a06_echo_check_secret_text_never_comes_back(client, readings, ep):
    r = post(client, ep, {**readings, "de_h_ge": "TOPSECRET-PAYLOAD"})
    assert r.status_code == 422 and "TOPSECRET-PAYLOAD" not in r.text


@pytest.mark.parametrize("raw", ['{"readings":', "[]", "42", "null", '"text"', "", "{}"], ids=["truncated", "array", "number", "null", "string", "empty", "empty-object"])
@both
def test_a06_malformed_json_bodies_are_422_not_500(client, ep, raw):
    assert_clean_client_error(post_raw(client, ep, raw))


@both
def test_a06_non_json_content_type_is_rejected(client, readings, ep):
    r = client.post(ENDPOINTS[ep][0], content=json.dumps({"readings": readings}), headers={"content-type": "text/plain"})
    assert_clean_client_error(r)


# =============================== AREA 6: NaN, infinity and absurd magnitudes ===============================
@both
@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_a06_nan_and_infinity_literals_are_rejected(client, readings, ep, token):
    body = json.dumps(ENDPOINTS[ep][1]({**readings, "de_h_ge": 0.0})).replace('"de_h_ge": 0.0', f'"de_h_ge": {token}')
    assert token in body
    assert_clean_client_error(post_raw(client, ep, body))
    assert stored(client) == 0


@both
def test_a06_overflowing_json_number_is_rejected(client, readings, ep):
    body = json.dumps(ENDPOINTS[ep][1]({**readings, "de_h_ge": 0.0})).replace('"de_h_ge": 0.0', '"de_h_ge": 1e999')
    assert_clean_client_error(post_raw(client, ep, body))


@pytest.fixture
def overflow_client(tmp_path):
    """A bundle whose positive weights make a 1e308 input overflow for certain (deterministic, unlike random weights)."""
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import FEATURES, make_settings
    from qa_support import build_bundle
    build_bundle(tmp_path / "ovf", layers=[(np.ones((len(FEATURES), 4)), np.zeros(4)), (np.ones((4, 3)), np.zeros(3))])
    with TestClient(create_app(make_settings(tmp_path / "ovf"))) as c:
        yield c


@both
def test_a06_reading_that_overflows_the_network_is_a_client_error_not_a_server_error(overflow_client, ep):
    """DEFECT D1: a finite reading (1e308) overflowed inside the network and surfaced as HTTP 500 prediction_failed."""
    ok = {n: 10.0 for n in FEATURES}
    assert post(overflow_client, ep, ok).status_code in (200, 201)             # the bundle itself works for normal readings
    body = json.dumps(ENDPOINTS[ep][1]({**ok, "de_h_ge": 0.0})).replace('"de_h_ge": 0.0', '"de_h_ge": 1e308')
    r = post_raw(overflow_client, ep, body)
    assert_clean_client_error(r)
    assert "too large" in r.json()["error"]["message"]
    assert overflow_client.get("/api/predictions").json()["total"] == 1       # only the normal reading was stored


@both
@pytest.mark.parametrize("literal", ["1e308", "-1e308", "1.7976931348623157e308", "-1.7976931348623157e308"])
def test_a06_float_limit_values_never_cause_a_server_error(client, readings, ep, literal):
    body = json.dumps(ENDPOINTS[ep][1]({**readings, "de_h_ge": 0.0})).replace('"de_h_ge": 0.0', f'"de_h_ge": {literal}')
    r = post_raw(client, ep, body)
    assert r.status_code in (200, 201, 422), r.text[:200]          # scored with a warning, or refused; never 5xx
    if r.status_code in (200, 201):
        assert abs(sum(r.json()["scores"].values()) - 1) < 1e-9


@both
def test_a06_huge_but_scoreable_reading_is_accepted_with_an_out_of_range_notice(client, readings, ep):
    """1e300 is a legal float the network can score. The API must not invent limits: it answers and flags the extrapolation."""
    r = post(client, ep, {**readings, "de_h_ge": 1e300})
    assert r.status_code in (200, 201)
    warned = r.json()["input_warnings"]
    assert [w["feature"] for w in warned] == ["de_h_ge"]


@both
def test_a06_integer_too_large_for_a_float_is_a_client_error(client, readings, ep):
    """DEFECT D2: a 400-digit integer made float() raise OverflowError -> HTTP 500."""
    body = json.dumps(ENDPOINTS[ep][1]({**readings, "de_h_ge": 0.0})).replace('"de_h_ge": 0.0', '"de_h_ge": ' + "9" * 400)
    assert_clean_client_error(post_raw(client, ep, body))
    assert stored(client) == 0


@both
def test_a06_large_negative_and_zero_readings_are_accepted(client, readings, ep):
    """Negative temperatures / zero load are legal numbers; range limits are NOT invented by the API."""
    r = post(client, ep, {**readings, "de_h_temp_c": -40.0, "load_percent": 0})
    assert r.status_code in (200, 201)


# =============================== AREA 6: timestamps ===============================
BAD_TIMESTAMPS = ["not-a-date", "2025-02-30T10:00:00", "2025-13-01T00:00:00", "2025-04-01T25:00:00", "", None, 12345.5, 1700000000, True, [], {}]


@pytest.mark.parametrize("ts", BAD_TIMESTAMPS, ids=[repr(t) for t in BAD_TIMESTAMPS])
def test_a06_assessment_rejects_invalid_timestamps(client, readings, ts):
    assert_clean_client_error(client.post("/api/assessments", json=make_assessment_body(readings, measured_at=ts)))
    assert stored(client) == 0


@pytest.mark.parametrize("ts", ["not-a-date", "2025-02-30T10:00:00", "2025-13-01T00:00:00", True, [], 12345.5, 1700000000],
                         ids=["text", "feb30", "month13", "bool", "list", "float-number", "int-number"])
def test_a06_single_prediction_rejects_invalid_or_numeric_timestamps(client, readings, ts):
    """DEFECT D10: a bare number was silently turned into a 1970 date on /api/predict (the assessment endpoint already refused it)."""
    assert_clean_client_error(client.post("/api/predict", json={"readings": readings, "measured_at": ts}))
    assert stored(client) == 0


EXTREME_TIMESTAMPS = ["0001-01-01T00:00:00", "1900-01-01T00:00:00", "1969-12-31T23:59:59", "2101-01-01T00:00:00", "2999-01-01T00:00:00",
                      "9999-12-31T23:59:59", "9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:00"]


@both
@pytest.mark.parametrize("ts", EXTREME_TIMESTAMPS)
def test_a06_implausible_or_overflowing_timestamps_are_rejected_like_in_csv(client, readings, ep, ts):
    """DEFECTS D3/D4: a timezone-aware date near year 1/9999 overflowed on conversion to UTC (HTTP 500), and the JSON endpoints accepted
    years the CSV path rejects (CSV allows 1970-2100 only)."""
    r = post(client, ep, readings, measured_at=ts)
    assert_clean_client_error(r)
    assert stored(client) == 0


@both
@pytest.mark.parametrize("ts", ["1970-01-01T00:00:00", "2025-04-01T07:20:00", "2025-04-01T07:20:00Z", "2025-04-01T07:20:00+05:30", "2100-12-31T23:59:59"])
def test_a06_ordinary_timestamps_are_still_accepted(client, readings, ep, ts):
    assert post(client, ep, readings, measured_at=ts).status_code in (200, 201)


# =============================== AREA 6/15: oversized JSON ===============================
@both
def test_a15_absurd_number_of_reading_keys_is_refused_with_a_small_response(client, readings, ep):
    """DEFECT D6: 100,000 unknown keys produced an ~890 KB error response that echoed every key."""
    r = post(client, ep, {f"k{i}": 1.0 for i in range(100_000)})
    assert_clean_client_error(r)
    assert len(r.content) < 20_000, f"error response is {len(r.content):,} bytes"


# =============================== AREA 7: IDs and unknown motors ===============================
BAD_IDS = ["trailing-newline\n", "has space", "../etc/passwd", "a/b", "x" * 65, "motor;drop table", "<script>", "line\nbreak", "motør", "", "  "]


@pytest.mark.parametrize("bad", BAD_IDS, ids=[repr(b)[:20] for b in BAD_IDS])
def test_a07_invalid_motor_ids_are_rejected(client, readings, bad):
    assert_clean_client_error(client.post("/api/assessments", json=make_assessment_body(readings, motor_id=bad)))
    assert stored(client) == 0


def test_a07_motor_id_boundaries_are_accepted(client, readings):
    for ok in ("M", "x" * 64, "CIPR-01", "a.b_c-9"):
        assert client.post("/api/assessments", json=make_assessment_body(readings, motor_id=ok)).status_code == 201


def test_a07_unknown_motor_is_recorded_not_rejected_and_does_not_change_the_prediction(client, readings):
    """The motor ID is a label, not a model input. A brand-new motor is accepted and gets exactly the same score for the same readings."""
    a = client.post("/api/assessments", json=make_assessment_body(readings, motor_id="KNOWN-1")).json()
    b = client.post("/api/assessments", json=make_assessment_body(readings, motor_id="NEVER-SEEN-BEFORE")).json()
    assert a["scores"] == b["scores"] and a["predicted_condition"] == b["predicted_condition"]
    ids = {m["motor_id"] for m in client.get("/api/motors").json()["items"]}
    assert {"KNOWN-1", "NEVER-SEEN-BEFORE"} <= ids


def test_a07_unknown_ids_in_lookups_are_404_or_empty_never_500(client):
    assert client.get("/api/assessments/999999").status_code == 404
    assert client.get("/api/predictions/999999").status_code == 404
    r = client.get("/api/predictions", params={"motor_id": "NO-SUCH-MOTOR"})
    assert r.status_code == 200 and r.json()["total"] == 0 and r.json()["items"] == []
    assert client.get("/api/predictions", params={"batch_id": "00000000-0000-0000-0000-000000000000"}).json()["total"] == 0
    for bad in ("abc", "-1", "1.5", "9" * 40):
        assert client.get(f"/api/predictions/{bad}").status_code in (404, 422), bad


# =============================== AREA 13: status codes and messages ===============================
def test_a13_error_envelope_and_status_codes_for_common_mistakes(client, readings):
    cases = [
        (client.get("/api/does-not-exist"), 404, "http_error"),
        (client.delete("/api/predictions/1"), 405, "http_error"),
        (client.put("/api/predict", json={}), 405, "http_error"),
        (client.get("/api/predictions/abc"), 422, "invalid_request"),
        (client.get("/api/predictions", params={"limit": 0}), 422, "invalid_request"),
        (client.get("/api/predictions", params={"limit": 501}), 422, "invalid_request"),
        (client.get("/api/predictions", params={"offset": -1}), 422, "invalid_request"),
        (client.get("/api/predictions", params={"date_from": "2025-13-45"}), 422, "invalid_request"),
        (client.get("/api/predictions", params={"date_from": "2025-05-02", "date_to": "2025-05-01"}), 422, "invalid_query"),
        (client.post("/api/predict", json={"readings": {}}), 422, "invalid_sensor_readings"),
        (client.get("/api/assessments/424242"), 404, "not_found"),
    ]
    for r, status, code in cases:
        assert r.status_code == status and r.json()["error"]["code"] == code, (r.request.method, r.request.url, r.text[:200])
        assert r.json()["error"]["message"]


def test_a13_messages_tell_the_user_what_to_fix(client, readings):
    r = client.post("/api/predict", json={"readings": {k: v for k, v in readings.items() if k != "load_percent"}})
    assert "load_percent" in json.dumps(r.json()) and "No prediction was made" in r.json()["error"]["message"]
    r = client.post("/api/assessments", json=make_assessment_body(readings), headers={"Idempotency-Key": "short"})
    assert r.status_code == 422 and "Idempotency-Key" in r.json()["error"]["message"]
