"""API-level tests: the full request -> response path."""

VALID = {"machine_id": "M-1", "readings": {"sensor_a": 80.0, "sensor_b": 5.0}}


def test_health_without_model_still_works(client_without_model):
    body = client_without_model.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["model_ready"] is False


def test_model_info_explains_why_model_is_missing(client_without_model):
    body = client_without_model.get("/api/v1/model/info").json()
    assert body["model_ready"] is False
    assert "Missing model file" in body["reason"]
    assert "pytest-of" not in body["reason"]  # the temp folder path must not leak to users


def test_predict_without_model_returns_structured_503(client_without_model):
    r = client_without_model.post("/api/v1/predict", json=VALID)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "model_not_ready"


def test_health_and_model_info_with_model(client):
    assert client.get("/api/v1/health").json()["model_ready"] is True
    info = client.get("/api/v1/model/info").json()
    assert info["model_ready"] is True
    assert info["feature_count"] == 2
    assert info["metadata"]["model_name"] == "test-model"


def test_features_endpoint(client):
    names = [f["name"] for f in client.get("/api/v1/model/features").json()["features"]]
    assert names == ["sensor_a", "sensor_b"]


def test_predict_success_returns_valid_probability(client):
    r = client.post("/api/v1/predict", json=VALID)
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["failure_probability"] <= 1.0
    assert isinstance(body["predicted_failure"], bool)
    assert body["machine_id"] == "M-1"
    assert body["model_version"] == "0.0.test"


def test_predict_missing_feature_is_422_with_details(client):
    r = client.post("/api/v1/predict", json={"readings": {"sensor_a": 10}})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_sensor_readings"
    assert err["details"]["missing_features"] == ["sensor_b"]


def test_predict_unknown_feature_is_rejected(client):
    r = client.post("/api/v1/predict", json={"readings": {"sensor_a": 1, "sensor_b": 1, "typo": 3}})
    assert r.status_code == 422
    assert r.json()["error"]["details"]["unknown_features"] == ["typo"]


def test_predict_out_of_range_is_rejected(client):
    r = client.post("/api/v1/predict", json={"readings": {"sensor_a": 500, "sensor_b": 1}})
    assert r.status_code == 422
    assert r.json()["error"]["details"]["out_of_range"][0]["feature"] == "sensor_a"


def test_predict_wrong_type_uses_structured_format(client):
    r = client.post("/api/v1/predict", json={"readings": {"sensor_a": "hot", "sensor_b": 1}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_unknown_route_uses_structured_format(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert "error" in r.json()


def test_cors_allows_configured_origin(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_other_origin(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_openapi_docs_are_available(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
