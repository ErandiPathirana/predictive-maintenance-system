"""Layer R: RECOMMENDATION RULES in isolation (CONTROLLED TEST DOUBLES) and layer B: the REAL trained artifacts (BLOCKED until they exist).

Doubles are used here and ONLY here, and only to choose which class the model "returns" so that every recommendation rule can be exercised.
They say nothing about the model. The model-integration tests are in test_e2e_api_db.py.
"""
import csv
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from conftest import make_settings           # tests/backend/conftest.py (plain module)
from harness import OUT, Server, db_rows, decode_row
from scn import scn
from app.main import create_app
from app.services.recommendations import recommend

FEATURES = ["de_h_velocity_mm_s", "de_h_ge", "de_h_temp_c", "de_v_velocity_mm_s", "de_v_ge", "de_v_temp_c",
            "nde_h_velocity_mm_s", "nde_h_ge", "nde_h_temp_c", "nde_v_velocity_mm_s", "nde_v_ge", "nde_v_temp_c", "rotational_speed_rpm", "load_percent"]

FORBIDDEN = [(r"\b\d+\s*(minutes?|hours?|days?|weeks?)\b", "an invented time limit"), (r"\bwithin\s+(the\s+)?(next\s+)?\d", "an invented deadline"),
             (r"\breplace\b|\breplacement\b|\bspare part|\bnew bearing|\b(re)?lubricate\b|\b(add|apply|inject) grease\b|\brealign|\brebalanc", "a repair or part recommendation"),
             (r"\b(is|are|has been|will be)\s+(automatically\s+)?(shut ?down|stopped|isolated)\b", "an automatic shutdown claim"),
             (r"\b(exceeds?|above|below|over)\s+(the\s+)?(limit|threshold|alarm)\b|\b\d+(\.\d+)?\s*(mm/s|degc|°c)\b", "an invented threshold"),
             (r"\b(bearing|misalignment|imbalance|unbalance|looseness|cavitation)\s+(fault|failure|defect|damage)\b", "a fault diagnosis")]


def all_text(rs: dict) -> str:
    return json.dumps(rs, ensure_ascii=False)


@scn("E2E-R1", "A-C (rules)", "Recommendation rules for Normal, Alert and Danger, tested in isolation", pre="No model involved: the rule function is called with each class name",
     inp="recommend('Normal' | 'Alert' | 'Danger')", exp="Normal: routine monitoring and planned-maintenance items only. Alert: escalation to the maintenance engineer + qualified inspection. Danger: urgent, immediate engineer notification, stop/isolate ONLY via approved lockout/tagout, no shutdown order, no repair instructions for unqualified users; never an invented deadline, threshold, part or diagnosis",
     sev="Critical (safety wording)", fix="Edit services/recommendations.py, bump RULESET_VERSION, update docs/recommendation-rules.md", layer="Recommendation rules (no model)")
def test_R1_rules(rec):
    n, a, d = (recommend(c, (), None).to_dict() for c in ("Normal", "Alert", "Danger"))
    assert not n["urgent"] and not a["urgent"] and d["urgent"]
    assert {i["timing"] for i in n["items"]} <= {"Routine monitoring", "Planned maintenance review"} and n["return_to_service"] == []
    assert a["items"][0]["timing"] == "Prompt engineering assessment"
    assert "maintenance engineer" in a["items"][0]["action"].lower() and any("inspect" in i["action"].lower() for i in a["items"]) and a["return_to_service"]
    assert d["items"][0]["timing"] == "Immediate safety review" and "immediately" in d["items"][0]["action"].lower()
    dtxt = all_text(d).lower()
    assert "lockout/tagout" in dtxt and "approved" in dtxt and "does not issue shutdown commands" in dtxt and "qualified" in dtxt
    assert d["items"][1]["action"].lower().startswith("if the equipment may be unsafe") and "only through" in d["items"][1]["action"]
    for name, rs in (("Normal", n), ("Alert", a), ("Danger", d)):
        text = all_text(rs).lower()
        for pat, what in FORBIDDEN:
            m = re.search(pat, text)
            assert not m, f"{name} advice contains {what}: '{m.group(0)}'"
        assert rs["disclaimer"] and rs["threshold_note"] and "does not diagnose a fault" in text
        assert all(i["source"] == "general_guidance" and i["requires_confirmation"] for i in rs["items"])
    rec.actual_(f"Normal: {len(n['items'])} items, only routine/planned timing, not urgent; Alert: {len(a['items'])} items, first = '{a['items'][0]['action']}'; Danger: {len(d['items'])} items, urgent, first = '{d['items'][0]['action']}'; no invented deadline/threshold/part/diagnosis in any class")


@scn("E2E-R2", "A-C (rules)", "Recommendation rules: unknown class is never given invented advice", pre="No model involved", inp="recommend('Critical')",
     exp="available=false, no items, tells the user to ask the maintenance engineer", sev="High", fix="recommendations.recommend", layer="Recommendation rules (no model)")
def test_R2_unknown(rec):
    r = recommend("Critical", (), None).to_dict()
    assert r["available"] is False and r["items"] == [] and "engineer" in all_text(r).lower()
    rec.actual_("available=false, 0 items, headline: " + r["headline"])


@pytest.fixture(scope="module")
def doubled_app(tmp_path_factory):
    from plugin_e2e import OUT as _o  # noqa
    return None


def _double_scores(k):
    p = np.full((1, 3), 0.05); p[0, k] = 0.90; return p


@scn("E2E-R3", "A-C (rules)", "Rules → API → database: recommendations stored equal the rules' output for each class (model replaced by a TEST DOUBLE)",
     pre="In-process API with a real SQLite file; the scoring function is replaced by a controlled double that returns a chosen class (mock_ml)",
     inp="valid readings; double returns Normal, then Alert, then Danger", exp="response and database both carry exactly recommend(class); stored summary/ruleset match",
     sev="High", fix="Check routes_assessments / repository.create_assessment", layer="Recommendation rules (TEST DOUBLE model)")
@pytest.mark.mock_ml
def test_R3_doubles_to_db(monkeypatch, tmp_path, samples, rec):
    import app.api.routes_assessments as ra
    db = tmp_path / "r3.db"
    settings = make_settings(OUT / "bundle", database_url=f"sqlite:///{db.as_posix()}")
    readings = samples["samples"]["Normal"][0]["readings"]; seen = []
    with TestClient(create_app(settings)) as c:
        for k, cls in enumerate(("Normal", "Alert", "Danger")):
            monkeypatch.setattr(ra, "score_matrix", lambda bundle, X, k=k: _double_scores(k))
            r = c.post("/api/assessments", json={"motor_id": f"R3-{cls}", "measured_at": "2025-04-01T07:20:00", "readings": readings})
            assert r.status_code == 201, r.text
            j = r.json(); assert j["predicted_condition"] == cls
            want = recommend(cls, [w["feature"] for w in j["input_warnings"]], None).to_dict()
            assert j["recommendations"] == want
            d = decode_row(db_rows(db, "id=?", (j["assessment_id"],))[0])
            assert d["recommendations"] == want and d["predicted_condition"] == cls and d["recommendation_summary"] == want["summary"]
            seen.append(cls)
    rec.actual_(f"double returned {seen}; for each, API response == recommend(class) == database JSON")


# ======================================================================= layer B: REAL trained artifacts
def real_bundle():
    cands = [Path(os.environ["PM_REAL_BUNDLE_DIR"])] if os.environ.get("PM_REAL_BUNDLE_DIR") else []
    root = OUT.parents[2] / "ml" / "artifacts"
    if root.is_dir():
        cands += sorted(p for p in root.iterdir() if p.is_dir())
    for c in cands:
        if (c / "MANIFEST.json").is_file():
            return c
    return None


@scn("E2E-B1", "A-C (real)", "REAL trained model: bundle loads, parity probes pass, health and model-info are ready", pre="Colab export copied to ml/artifacts/<bundle> (or PM_REAL_BUNDLE_DIR set)",
     inp="start backend on the real bundle", exp="server starts (manifest hashes, feature order, parity probes verified); /api/health model_ready=true", sev="High", fix="Export the bundle from the Colab notebook (section 19) into ml/artifacts",
     layer="Real artifacts")
def test_B1_real_bundle(tmp_path, rec):
    b = real_bundle()
    if b is None:
        pytest.skip("BLOCKED: no trained model bundle in ml/artifacts and PM_REAL_BUNDLE_DIR is not set. The real model has not been tested.")
    with Server(b, tmp_path / "real.db", port=8160) as s:
        assert not s.exited(), s.log_tail()
        h = httpx.get(s.url + "/api/health").json(); assert h["model_ready"] is True
        info = httpx.get(s.url + "/api/model-info").json()["bundle"]
        rec.actual_(f"bundle {b.name} loaded: version {info['bundle_version']}, {info['feature_count']} features, classes {[c['name'] for c in info['classes']]}")


@scn("E2E-B2", "A-C (real)", "REAL model on REAL labelled rows: which classes does it actually produce, and does every saved record match?", pre="Real bundle AND a CSV of real rows with the 14 inputs plus condition_label (PM_REAL_SAMPLES_CSV). The data stays on your machine",
     inp="up to 3 rows per true class, sent as manual assessments", exp="201 each; DB row equals response; recommendations match the predicted class. Agreement with the label is REPORTED, not asserted (this is not an accuracy test)",
     sev="High", fix="Provide the real rows (never commit them to GitHub)", layer="Real artifacts")
def test_B2_real_rows(tmp_path, rec):
    b = real_bundle(); csvp = os.environ.get("PM_REAL_SAMPLES_CSV")
    if b is None or not csvp or not Path(csvp).is_file():
        pytest.skip("BLOCKED: needs the real bundle (ml/artifacts) and PM_REAL_SAMPLES_CSV pointing to real rows with a condition_label column.")
    rows = list(csv.DictReader(open(csvp, encoding="utf-8-sig"))); by = {}
    for r in rows: by.setdefault(r["condition_label"], []).append(r)
    db = tmp_path / "real_rows.db"; out = {}
    with Server(b, db, port=8161) as s:
        c = httpx.Client(base_url=s.url, timeout=20)
        for label, rs in by.items():
            for i, r in enumerate(rs[:3]):
                body = {"motor_id": f"REAL-{label}-{i}", "measured_at": "2025-04-01T07:20:00", "readings": {f: float(r[f]) for f in FEATURES}}
                resp = c.post("/api/assessments", json=body); assert resp.status_code == 201, resp.text
                j = resp.json(); d = decode_row(db_rows(db, "id=?", (j["assessment_id"],))[0])
                assert d["predicted_condition"] == j["predicted_condition"] and d["recommendations"] == j["recommendations"]
                out.setdefault(label, []).append(j["predicted_condition"])
    produced = sorted({p for v in out.values() for p in v})
    rec.actual_(f"label → predicted: {out}. Classes produced: {produced}. " + ("All three classes were produced: full real-model scenarios A-C can be run." if len(produced) == 3 else "NOT all three classes were produced: keep real-model integration tests and recommendation-rule tests separate (as done here)."))
