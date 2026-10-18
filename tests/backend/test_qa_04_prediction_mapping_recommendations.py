"""QA areas 8, 9, 10: repeatable predictions, output -> class-name mapping, class -> corrective-action mapping.

Category: synthetic_bundle. The class tests use "forced" bundles (weights that ignore the input and always pick output index k) so the
EXPECTED class is known without any mocking: this isolates the backend's mapping logic from model quality.
"""

import numpy as np
import pytest

from conftest import CLASSES
from qa_support import make_assessment_body, served

R = {  # any valid readings: forced bundles ignore them
    "de_h_velocity_mm_s": 10.0, "de_h_ge": 10.0, "de_h_temp_c": 10.0, "de_v_velocity_mm_s": 10.0, "de_v_ge": 10.0, "de_v_temp_c": 10.0,
    "nde_h_velocity_mm_s": 10.0, "nde_h_ge": 10.0, "nde_h_temp_c": 10.0, "nde_v_velocity_mm_s": 10.0, "nde_v_ge": 10.0, "nde_v_temp_c": 10.0,
    "rotational_speed_rpm": 10.0, "load_percent": 10.0}
DANGER_FIRST = "Notify the responsible maintenance engineer immediately."


# =============================== AREA 8: consistency ===============================
def test_a08_same_input_gives_bit_identical_scores_every_time(client, readings):
    first = client.post("/api/predict", json={"readings": readings}).json()["scores"]
    for _ in range(25):
        assert client.post("/api/predict", json={"readings": readings}).json()["scores"] == first


def test_a08_same_input_via_every_route_gives_the_same_scores(client, readings, loaded):
    from conftest import csv_text, upload
    single = client.post("/api/predict", json={"readings": readings}).json()["scores"]
    assess = client.post("/api/assessments", json=make_assessment_body(readings)).json()["scores"]
    row = ",".join(["R1", "M1"] + [repr(float(readings[n])) for n in loaded.feature_names])
    batch = upload(client, "record_id,motor_id," + ",".join(loaded.feature_names) + "\r\n" + row + "\r\n").json()["results"][0]["scores"]
    for other in (assess, batch):
        assert max(abs(single[c] - other[c]) for c in single) < 1e-12


def test_a08_batch_results_do_not_depend_on_batch_size_or_row_order(client, loaded):
    from conftest import csv_text, upload
    rows = 9
    text = csv_text(loaded, rows=rows)
    head, *body = text.strip().splitlines()
    full = {r["record_id"]: r["scores"] for r in upload(client, "\r\n".join([head, *body]) + "\r\n").json()["results"]}
    rev = {r["record_id"]: r["scores"] for r in upload(client, "\r\n".join([head, *reversed(body)]) + "\r\n").json()["results"]}
    alone = {}
    for line in body:
        alone.update({r["record_id"]: r["scores"] for r in upload(client, head + "\r\n" + line + "\r\n").json()["results"]})
    for rid in full:
        for other in (rev, alone):
            assert max(abs(full[rid][c] - other[rid][c]) for c in full[rid]) < 1e-12, rid


def test_a08_restarting_the_service_does_not_change_results(bundle_dir, readings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import make_settings
    got = []
    for _ in range(3):
        with TestClient(create_app(make_settings(bundle_dir))) as c:
            got.append(c.post("/api/predict", json={"readings": readings}).json())
    assert got[0]["scores"] == got[1]["scores"] == got[2]["scores"] and len({g["model_version"] for g in got}) == 1


def test_a08_results_carry_the_model_version_that_produced_them(client, readings):
    pid = client.post("/api/predict", json={"readings": readings}).json()["prediction_id"]
    assert client.get(f"/api/predictions/{pid}").json()["model_version"] == "v9.9.9"


def test_a08_scores_match_an_independent_numpy_reference(client, readings, truth, loaded):
    from conftest import reference_forward
    x = np.array([[readings[n] for n in loaded.feature_names]])
    expected = reference_forward(truth["mean"], truth["scale"], truth["layers"], x)[0]
    got = client.post("/api/predict", json={"readings": readings}).json()["scores"]
    assert np.allclose([got[c] for c in CLASSES], expected, atol=1e-12)


# =============================== AREA 9: output -> class name ===============================
@pytest.mark.parametrize("k,name", list(enumerate(CLASSES)))
def test_a09_each_output_index_becomes_the_right_class_name_everywhere(tmp_path, k, name):
    with served(tmp_path, k) as c:
        single = c.post("/api/predict", json={"readings": R}).json()
        assert (single["predicted_condition"], single["predicted_class_id"]) == (name, k)
        assert single["scores"][name] > 0.999 and abs(sum(single["scores"].values()) - 1) < 1e-9
        assess = c.post("/api/assessments", json=make_assessment_body(R)).json()
        assert (assess["predicted_condition"], assess["predicted_class_id"]) == (name, k)
        from conftest import upload
        header = "record_id,motor_id," + ",".join(R) + "\r\n"
        batch = upload(c, header + "A1,M1," + ",".join(map(str, R.values())) + "\r\n").json()
        assert batch["class_counts"] == {n: int(n == name) for n in CLASSES}
        hist = c.get("/api/predictions").json()["items"]
        assert {h["predicted_condition"] for h in hist} == {name} and {h["predicted_class_id"] for h in hist} == {k}
        assert c.get("/api/predictions", params={"predicted_condition": name}).json()["total"] == 3
        assert "predicted_condition" in c.get("/api/reports/predictions.csv").text.splitlines()[0]
        assert f",{name},{k}," in c.get("/api/reports/predictions.csv").text


def test_a09_mapping_comes_from_class_mapping_json_not_from_a_hard_coded_order(tmp_path):
    """If the notebook ever exported 0=Danger, 1=Normal, 2=Alert the backend must follow the bundle, not assume Normal/Alert/Danger."""
    doc = {"classes": [{"id": 0, "name": "Danger"}, {"id": 1, "name": "Normal"}, {"id": 2, "name": "Alert"}]}
    for k, expected in enumerate(["Danger", "Normal", "Alert"]):
        with served(tmp_path, k, class_doc=doc, name=f"m{k}") as c:
            r = c.post("/api/assessments", json=make_assessment_body(R)).json()
            assert r["predicted_condition"] == expected and r["recommendations"]["condition"] == expected
            assert r["recommendations"]["urgent"] is (expected == "Danger")
            assert list(r["scores"]) == ["Danger", "Normal", "Alert"]


def test_a09_class_mapping_listed_out_of_order_is_sorted_by_id(tmp_path):
    doc = {"classes": [{"id": 2, "name": "Danger"}, {"id": 0, "name": "Normal"}, {"id": 1, "name": "Alert"}]}
    with served(tmp_path, 2, class_doc=doc) as c:
        assert c.post("/api/predict", json={"readings": R}).json()["predicted_condition"] == "Danger"
        assert [x["name"] for x in c.get("/api/model-info").json()["bundle"]["classes"]] == CLASSES


def test_a09_exact_ties_resolve_to_the_lowest_class_id_deterministically(tmp_path):
    """OBSERVATION (not a defect): equal scores pick output 0. With float weights an exact tie is practically impossible,
    but it is recorded here so the behaviour is deliberate. Whether 'Normal' is the right default for a tie is a policy question."""
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import FEATURES, make_settings
    from qa_support import build_bundle
    build_bundle(tmp_path / "tie", layers=[(np.zeros((len(FEATURES), 4)), np.zeros(4)), (np.zeros((4, 3)), np.zeros(3))])
    with TestClient(create_app(make_settings(tmp_path / "tie"))) as c:
        outs = {c.post("/api/predict", json={"readings": R}).json()["predicted_condition"] for _ in range(5)}
        assert outs == {"Normal"}


def test_a09_unknown_class_names_are_reported_not_silently_remapped(tmp_path):
    doc = {"classes": [{"id": 0, "name": "Healthy"}, {"id": 1, "name": "Warning"}, {"id": 2, "name": "Critical"}]}
    with served(tmp_path, 2, class_doc=doc) as c:
        r = c.post("/api/assessments", json=make_assessment_body(R)).json()
        assert r["predicted_condition"] == "Critical" and r["recommendations"]["available"] is False and r["recommendations"]["items"] == []


# =============================== AREA 10: class -> corrective action ===============================
@pytest.mark.parametrize("k,name", list(enumerate(CLASSES)))
def test_a10_each_class_gets_its_own_recommendation_set(tmp_path, k, name):
    with served(tmp_path, k) as c:
        j = c.post("/api/assessments", json=make_assessment_body(R)).json()
        rec = j["recommendations"]
        assert rec["condition"] == name and rec["available"] is True and rec["ruleset_version"]
        assert [i["priority"] for i in rec["items"]] == list(range(1, len(rec["items"]) + 1))
        assert all(i["action"] and i["responsible_role"] and i["timing"] and i["source"] == "general_guidance" and i["requires_confirmation"] for i in rec["items"])
        assert "not a safety-rated control system" in rec["disclaimer"]
        assert name in rec["headline"]
        # what was returned is exactly what is stored and re-served later
        again = c.get(f"/api/assessments/{j['assessment_id']}").json()
        assert again["recommendations"] == rec and again["recommendations_regenerated"] is False


def test_a10_urgency_and_ordering_differ_by_class_as_designed(tmp_path):
    out = {}
    for k, name in enumerate(CLASSES):
        with served(tmp_path, k, name=f"c{k}") as c:
            out[name] = c.post("/api/assessments", json=make_assessment_body(R)).json()["recommendations"]
    assert [out[n]["urgent"] for n in CLASSES] == [False, False, True]
    assert out["Danger"]["items"][0]["action"] == DANGER_FIRST and out["Danger"]["items"][0]["timing"] == "Immediate safety review"
    assert out["Alert"]["items"][0]["action"] == "Notify the responsible maintenance engineer."
    assert out["Normal"]["items"][0]["timing"] == "Routine monitoring" and out["Normal"]["return_to_service"] == []
    assert out["Alert"]["return_to_service"] and out["Danger"]["return_to_service"]
    assert out["Normal"]["items"][0]["action"] != out["Danger"]["items"][0]["action"]


def test_a10_the_api_never_commands_a_shutdown_or_claims_a_diagnosis(tmp_path):
    for k in range(3):
        with served(tmp_path, k, name=f"s{k}") as c:
            text = str(c.post("/api/assessments", json=make_assessment_body(R)).json()["recommendations"]["items"]).lower()
            for banned in ("shut down the motor", "replace the bearing", "bearing failure", "will fail", "confirmed failure", "repair immediately"):
                assert banned not in text, banned


def test_a10_out_of_range_inputs_add_a_data_check_without_changing_the_class_or_putting_it_before_the_danger_notice(tmp_path):
    far = {**R, "de_h_ge": 10_000.0}
    for k, name in enumerate(CLASSES):
        with served(tmp_path, k, name=f"w{k}") as c:
            j = c.post("/api/assessments", json=make_assessment_body(far)).json()
            assert j["predicted_condition"] == name and [w["feature"] for w in j["input_warnings"]] == ["de_h_ge"]
            actions = [i["action"] for i in j["recommendations"]["items"]]
            assert any("de_h_ge" in i["reason"] + i["action"] for i in j["recommendations"]["items"])
            if name == "Danger":
                assert actions[0] == DANGER_FIRST


def test_a10_csv_batch_rows_store_a_class_matched_summary(tmp_path):
    from conftest import upload
    for k, name in enumerate(CLASSES):
        with served(tmp_path, k, name=f"b{k}") as c:
            upload(c, "record_id,motor_id," + ",".join(R) + "\r\n" + "A1,M1," + ",".join(map(str, R.values())) + "\r\n")
            item = c.get("/api/predictions").json()["items"][0]
            assert item["recommendation_summary"].startswith(f"{name}:") and item["ruleset_version"]


# =============================== TRAINED MODEL (BLOCKED when ml/artifacts has no bundle) ===============================
@pytest.fixture
def real_client():
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import make_settings
    from qa_support import need_real_bundle
    with TestClient(create_app(make_settings(need_real_bundle()))) as c:
        yield c


def _real_readings(c) -> dict:
    """Mid-point of the range observed in training for every input (taken from the bundle's own feature schema)."""
    feats = c.get("/api/features").json()["features"]
    return {f["name"]: (f["observed_train_min"] + f["observed_train_max"]) / 2 for f in feats}


@pytest.mark.real_artifacts
def test_a08_real_model_is_repeatable_and_batch_equals_single(real_client):
    from conftest import upload
    r = _real_readings(real_client)
    first = real_client.post("/api/predict", json={"readings": r}).json()
    assert all(real_client.post("/api/predict", json={"readings": r}).json()["scores"] == first["scores"] for _ in range(5))
    names = list(r)
    csv = "record_id,motor_id," + ",".join(names) + "\r\n" + "A1,M1," + ",".join(repr(r[n]) for n in names) + "\r\n"
    b = upload(real_client, csv).json()["results"][0]
    assert max(abs(b["scores"][c] - first["scores"][c]) for c in first["scores"]) < 1e-12


@pytest.mark.real_artifacts
def test_a09_a10_real_model_class_names_and_recommendations_agree(real_client):
    r = _real_readings(real_client)
    j = real_client.post("/api/assessments", json=make_assessment_body(r)).json()
    assert j["predicted_condition"] in CLASSES and j["scores"][j["predicted_condition"]] == max(j["scores"].values())
    assert j["recommendations"]["condition"] == j["predicted_condition"] and j["recommendations"]["available"] is True
    assert abs(sum(j["scores"].values()) - 1) < 1e-6
