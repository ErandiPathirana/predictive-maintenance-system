"""QA area 18: API documentation and request/response schema consistency.

Category: synthetic_bundle. The key idea: the OpenAPI document is generated from the code, and the REAL responses are validated against
the schemas that document promises. If a route returns something its documentation does not describe, a test here fails.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from conftest import csv_text, upload
from qa_support import make_assessment_body

DOCS = PROJECT_ROOT / "docs"


def validator(spec: dict, schema_name: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"#/components/schemas/{schema_name}", "components": spec["components"]})


def assert_matches(spec: dict, name: str, payload) -> None:
    errors = sorted(validator(spec, name).iter_errors(payload), key=lambda e: list(e.path))
    assert not errors, f"{name}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


@pytest.fixture
def spec(client) -> dict:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    return r.json()


def test_a18_swagger_redoc_and_openapi_are_served(client):
    assert client.get("/docs").status_code == 200 and "swagger" in client.get("/docs").text.lower()
    assert client.get("/redoc").status_code == 200
    j = client.get("/openapi.json").json()
    assert j["openapi"].startswith("3.") and j["info"]["title"] and j["info"]["version"]
    assert "NOT a confirmed machine failure" in j["info"]["description"] or "not a confirmed machine failure" in j["info"]["description"].lower()


def test_a18_every_operation_is_documented(spec):
    ids = set()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            where = f"{method.upper()} {path}"
            assert op.get("summary"), where
            assert op.get("tags"), where
            assert op["operationId"] not in ids, f"duplicate operationId {where}"
            ids.add(op["operationId"])
            ok = [c for c in op["responses"] if c.startswith("2")]
            assert ok, f"{where} documents no success response"
            if "422" not in op["responses"] and (op.get("parameters") or op.get("requestBody")):
                pytest.fail(f"{where} takes input but does not document 422")


def test_a18_documented_error_codes_match_what_the_api_really_returns(spec, client, readings):
    # endpoints that can answer 503/415/413 must say so
    for path in ("/api/predict", "/api/predict/batch", "/api/uploads/validate"):
        assert "503" in spec["paths"][path]["post"]["responses"], path
    for path in ("/api/predict/batch", "/api/uploads/validate"):
        for code in ("413", "415", "422"):
            assert code in spec["paths"][path]["post"]["responses"], (path, code)
    assert "409" in spec["paths"]["/api/assessments"]["post"]["responses"] and "200" in spec["paths"]["/api/assessments"]["post"]["responses"]
    assert "404" in spec["paths"]["/api/predictions/{prediction_id}"]["get"]["responses"]
    assert "404" in spec["paths"]["/api/assessments/{assessment_id}"]["get"]["responses"]


def test_a18_real_success_responses_validate_against_the_published_schemas(client, spec, readings, loaded):
    body = make_assessment_body(readings, equipment_description="E", recorded_by="AB")
    a = client.post("/api/assessments", json=body, headers={"Idempotency-Key": "schema-check-0001"})
    batch = upload(client, csv_text(loaded, rows=3))
    pid = batch.json()["results"][0]["prediction_id"]
    cases = [
        ("HealthResponse", client.get("/api/health")), ("ModelInfoResponse", client.get("/api/model-info")), ("FeatureListResponse", client.get("/api/features")),
        ("PredictionResult", client.post("/api/predict", json={"readings": readings, "record_id": "R1", "motor_id": "M1", "measured_at": "2025-04-01T07:20:00"})),
        ("AssessmentResponse", a), ("AssessmentResponse", client.post("/api/assessments", json=body, headers={"Idempotency-Key": "schema-check-0001"})),   # replay (200)
        ("AssessmentResponse", client.get(f"/api/assessments/{a.json()['assessment_id']}")), ("AssessmentResponse", client.get(f"/api/assessments/{pid}")),
        ("BatchPredictionResponse", batch), ("CsvValidationReport", upload(client, csv_text(loaded, rows=2), url="/api/uploads/validate")),
        ("CsvValidationReport", upload(client, csv_text(loaded, rows=2, mutate=lambda r, v: v.update(de_h_ge="x")), url="/api/uploads/validate")),
        ("PredictionPage", client.get("/api/predictions")), ("HistoryItem", client.get(f"/api/predictions/{pid}")), ("BatchList", client.get("/api/batches")),
        ("MotorList", client.get("/api/motors")),
    ]
    for name, r in cases:
        assert r.status_code in (200, 201), (name, r.text[:200])
        assert_matches(spec, name, r.json())


def test_a18_real_error_responses_validate_against_error_response(client, spec, readings):
    errors = [client.post("/api/predict", json={"readings": {}}), client.get("/api/predictions/99999"), client.get("/api/assessments/99999"),
              client.get("/api/nothing"), client.delete("/api/predict"), upload(client, b"x", name="x.txt"), upload(client, b"", name="x.csv"),
              client.get("/api/predictions", params={"limit": 0}), client.get("/api/predictions", params={"date_from": "2025-02-01", "date_to": "2025-01-01"})]
    for r in errors:
        assert r.status_code >= 400
        assert_matches(spec, "ErrorResponse", r.json())


def test_a18_503_and_401_use_the_documented_error_schema(tmp_path, spec, readings):
    from fastapi.testclient import TestClient
    from conftest import make_settings
    with TestClient(create_app(make_settings(tmp_path / "none", require_model_at_startup=False, api_key="k-1234567"))) as c:
        assert_matches(spec, "ErrorResponse", c.get("/api/model-info").json())                                     # 401
        r = c.post("/api/predict", json={"readings": readings}, headers={"X-API-Key": "k-1234567"})
        assert r.status_code == 503
        assert_matches(spec, "ErrorResponse", r.json())


def test_a18_request_schemas_describe_what_the_api_really_enforces(spec):
    comps = spec["components"]["schemas"]
    a = comps["AssessmentRequest"]
    assert set(a["required"]) == {"motor_id", "measured_at", "readings"} and a.get("additionalProperties") is False
    assert comps["SinglePredictionRequest"].get("additionalProperties") is False and comps["SinglePredictionRequest"]["required"] == ["readings"]
    assert a["properties"]["readings"].get("maxProperties") == 100
    assert a["properties"]["motor_id"]["pattern"] == "^[A-Za-z0-9._\\-]{1,64}$"
    assert a["properties"]["equipment_description"]["anyOf"][0]["maxLength"] == 120


def _without_http_phrases(spec: dict) -> dict:
    """Python's http.HTTPStatus wording changed in 3.13 (422 'Unprocessable Entity' -> 'Unprocessable Content', 413 'Request Entity Too Large' ->
    'Content Too Large'). FastAPI copies that wording into the OpenAPI document, so the descriptions of 4xx/5xx entries are not compared."""
    spec = json.loads(json.dumps(spec))
    for ops in spec["paths"].values():
        for op in ops.values():
            for code, resp in op["responses"].items():
                if code[0] in "45":
                    resp.pop("description", None)
    return spec


def test_a18_the_committed_docs_are_in_sync_with_the_code():
    """docs/openapi.json is generated by backend/scripts/generate_api_docs.py. If this fails, re-run that script."""
    live = create_app(Settings(environment="test", database_url="sqlite:///:memory:", auto_create_tables=True, require_model_at_startup=False, _env_file=None)).openapi()
    committed = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    assert _without_http_phrases(committed) == _without_http_phrases(live), "docs/openapi.json is stale: run `python scripts/generate_api_docs.py` from the backend folder"
    md = (DOCS / "api-schemas.md").read_text(encoding="utf-8")
    for name in live["components"]["schemas"]:
        if name not in ("HTTPValidationError", "ValidationError"):
            assert f"### {name}" in md, f"{name} missing from docs/api-schemas.md"


def test_a18_openapi_has_no_secret_or_path_information(spec):
    text = json.dumps(spec)
    for leak in (str(PROJECT_ROOT), "/home/", "C:\\\\Users", "hunter2", "predictions.db"):
        assert leak not in text


def test_a18_scores_are_never_documented_or_labelled_as_calibrated_probabilities(spec, client, readings):
    j = client.post("/api/predict", json={"readings": readings}).json()
    assert j["scores_are_calibrated_probabilities"] is False and "not calibrated" in json.dumps(spec["components"]["schemas"]["PredictionResult"]).lower()
