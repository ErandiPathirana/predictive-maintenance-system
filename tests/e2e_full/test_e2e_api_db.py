"""Full-stack end-to-end tests at the HTTP + database level (layer: MODEL INTEGRATION on a TRAINED synthetic-data model).

The real backend is started as a separate process (python -m uvicorn app.main:app) with a real SQLite file. Every check on what was
"really saved" reads the database file with plain sqlite3, not through application code.
Samples are chosen by their SYNTHETIC TRUTH label. The model is never forced: whatever class it returns is what is checked.
"""
import csv
import io
import json
import shutil
import sqlite3
import threading
from pathlib import Path

import httpx
import numpy as np
import pytest

from conftest import sign_manifest   # tests/backend/conftest.py (plain module)
from plugin_e2e import unique
from harness import OUT, Server, db_count, db_rows, decode_row
from scn import scn

HOW = "Real backend process + real SQLite file + trained (synthetic-data) model bundle"
WHEN = "2025-04-01T07:20:00"
FEATURES = ["de_h_velocity_mm_s", "de_h_ge", "de_h_temp_c", "de_v_velocity_mm_s", "de_v_ge", "de_v_temp_c",
            "nde_h_velocity_mm_s", "nde_h_ge", "nde_h_temp_c", "nde_v_velocity_mm_s", "nde_v_ge", "nde_v_temp_c", "rotational_speed_rpm", "load_percent"]
EXPORT_BASE = ["prediction_id", "batch_id", "source", "record_id", "motor_id", "measured_at", "predicted_at_utc", "predicted_condition", "predicted_class_id"]
EXPORT_TAIL = ["model_version", "label_provenance_provisional", "demonstration_only", "equipment_description", "recorded_by_unverified",
               "recommendation_summary", "recommendation_ruleset", "note"]
EXPORT_COLS = EXPORT_BASE + ["model_score_Normal", "model_score_Alert", "model_score_Danger"] + EXPORT_TAIL


def post(api, motor, readings, key=None, when=WHEN, **extra):
    h = {"Idempotency-Key": key} if key else {}
    return api.post("/api/assessments", json={"motor_id": motor, "measured_at": when, "readings": readings, **extra}, headers=h)


def export(api, **params):
    r = api.get("/api/reports/predictions.csv", params=params)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    return r, rows, (r.text.splitlines()[0].split(",") if r.text else [])


def csv_text(rows, drop=(), rename=None, extra=None):
    cols = ["record_id", "motor_id", "measured_at", *FEATURES]
    cols = [c for c in cols if c not in drop]
    head = [(rename or {}).get(c, c) for c in cols] + list((extra or {}).keys())
    lines = [",".join(head)]
    for i, r in enumerate(rows, 1):
        full = {"record_id": f"R{i}", "motor_id": r.get("motor", "CSV-M"), "measured_at": f"2025-04-0{i} 07:20:00", **r["readings"]}
        lines.append(",".join([str(full[c]) for c in cols] + [str(v) for v in (extra or {}).values()]))
    return "\r\n".join(lines) + "\r\n"


def upload(api, text, url="/api/predict/batch", name="data.csv"):
    return api.post(url, files={"file": (name, text if isinstance(text, bytes) else text.encode(), "text/csv")})


# =================================================================== A, B, C  full chain per class
def chain(api, srv, samples, rec, cls):
    s = samples["samples"][cls][0]; motor = unique(f"CHAIN-{cls}")
    key = unique("key").replace("-", "") + "00000000"
    before = db_count(srv.db)
    r = post(api, motor, s["readings"], key=key, recorded_by="e2e tester", equipment_description="Pump 3 drive motor")
    assert r.status_code == 201, r.text
    j = r.json()
    # 1. model + preprocessing: backend answer equals an INDEPENDENT NumPy forward pass (fixture computed outside the backend)
    assert j["predicted_condition"] == s["reference_prediction"], f"backend {j['predicted_condition']} != independent reference {s['reference_prediction']}"
    for c, v in s["reference_scores"].items():
        assert abs(j["scores"][c] - v) < 1e-6, f"score {c}: {j['scores'][c]} vs reference {v}"
    rec.actual_(f"truth label (synthetic) = {cls}; model returned {j['predicted_condition']} (independent NumPy reference agrees); scores {({k: round(v, 4) for k, v in j['scores'].items()})}")
    # 2. recommendations belong to the returned class (rules checked in layer R; here only consistency)
    recs = j["recommendations"]
    from app.services.recommendations import recommend as _rules       # the rule table itself is the oracle for WHICH steps belong to a class
    expected = _rules(j["predicted_condition"], [w["feature"] for w in j["input_warnings"]], None).to_dict()
    assert recs["items"] == expected["items"] and recs["urgent"] == expected["urgent"], "returned steps differ from the rule table for this class"
    assert recs["condition"] == j["predicted_condition"] and recs["available"] and len(recs["items"]) >= 4
    assert (recs["urgent"] is True) == (j["predicted_condition"] == "Danger")
    # 3. database record, read with sqlite3
    rows = db_rows(srv.db, "id=?", (j["assessment_id"],)); assert len(rows) == 1
    d = decode_row(rows[0])
    assert db_count(srv.db) == before + 1
    assert d["predicted_condition"] == j["predicted_condition"] and d["predicted_class_id"] == j["predicted_class_id"]
    assert d["motor_id"] == motor and d["model_version"] == j["model_version"] and d["source"] == "single"
    assert all(abs(d["scores"][k] - j["scores"][k]) < 1e-12 for k in j["scores"])
    assert d["recommendations"] == recs, "recommendations stored in the database differ from those returned"
    assert d["recommendation_summary"] == recs["summary"] and d["ruleset_version"] == recs["ruleset_version"]
    assert d["measured_at"].startswith("2025-04-01 07:20") and d["idempotency_key"] == key
    assert d["input_readings"] is None, "raw sensor readings were stored although STORE_INPUT_READINGS is off"
    rec.evidence_(f"sqlite row id={d['id']}: condition={d['predicted_condition']}, recommendations JSON == API response, summary='{d['recommendation_summary'][:70]}…', readings NOT stored (privacy default)")
    # 4. retrieval: GET by id, history, export
    g = api.get(f"/api/assessments/{j['assessment_id']}").json()
    assert g["predicted_condition"] == j["predicted_condition"] and g["recommendations"] == recs and g["scores"] == j["scores"]
    h = api.get("/api/predictions", params={"motor_id": motor}).json()
    assert h["total"] == 1 and h["items"][0]["id"] == j["assessment_id"] and h["items"][0]["recommendation_summary"] == recs["summary"]
    r2, erows, _ = export(api, motor_id=motor)
    assert len(erows) == 1 and erows[0]["predicted_condition"] == j["predicted_condition"] and erows[0]["recommendation_summary"] == recs["summary"]
    assert abs(float(erows[0][f"model_score_{j['predicted_condition']}"]) - j["scores"][j["predicted_condition"]]) < 1e-5
    assert erows[0]["equipment_description"] == "Pump 3 drive motor" and erows[0]["recorded_by_unverified"] == "e2e tester"
    rec.evidence_("GET /assessments/{id}, GET /predictions?motor_id and the CSV export all show the same condition, scores and recommendation summary as the database")
    return j


@scn("E2E-A", "A", "Valid readings, Normal prediction: manual entry → model → recommendations → database → history → export",
     pre="Server running on a trained synthetic-data bundle; empty or any DB; held-out synthetic row whose TRUTH label is Normal",
     inp="14 readings of a held-out Normal-labelled synthetic motor, motor id, timestamp, Idempotency-Key",
     exp="201; condition equals independent NumPy reference; scores equal to 1e-6; routine-monitoring advice; 1 DB row identical to the response; retrievable by id, in history and in the export",
     sev="High (wrong or unsaved prediction)", fix="Compare backend vs reference scores, then check preprocessing.json order; inspect the sqlite row", layer="Model integration (trained synthetic model)")
def test_A_normal(api, srv, samples, rec):
    j = chain(api, srv, samples, rec, "Normal")
    assert j["predicted_condition"] == "Normal"
    assert not j["recommendations"]["urgent"]
    rec.actual_("Normal advice: " + j["recommendations"]["headline"])


@scn("E2E-B", "B", "Valid readings, Alert prediction: full chain", pre="As E2E-A, held-out row whose TRUTH label is Alert", inp="14 readings of a held-out Alert-labelled synthetic motor",
     exp="201; condition equals independent reference; inspection and maintenance-engineer escalation advice; DB row identical to response",
     sev="High", fix="As E2E-A", layer="Model integration (trained synthetic model)")
def test_B_alert(api, srv, samples, rec):
    j = chain(api, srv, samples, rec, "Alert")
    assert j["predicted_condition"] == "Alert"
    assert "maintenance engineer" in j["recommendations"]["items"][0]["action"].lower()
    rec.actual_("Alert advice: " + j["recommendations"]["headline"])


@scn("E2E-C", "C", "Valid readings, Danger prediction: full chain", pre="As E2E-A, held-out row whose TRUTH label is Danger", inp="14 readings of a held-out Danger-labelled synthetic motor",
     exp="201; condition equals independent reference; urgent=true; stop/isolate only via approved lockout/tagout procedure; no shutdown command; DB row identical to response",
     sev="Critical (safety wording)", fix="As E2E-A; check recommendations.py", layer="Model integration (trained synthetic model)")
def test_C_danger(api, srv, samples, rec):
    j = chain(api, srv, samples, rec, "Danger")
    assert j["predicted_condition"] == "Danger" and j["recommendations"]["urgent"] is True
    text = json.dumps(j["recommendations"]).lower()
    assert "approved" in text and "lockout/tagout" in text and "does not issue shutdown commands" in text and "does not diagnose a fault" in text
    rec.actual_("Danger advice: " + j["recommendations"]["headline"])


# =================================================================== D  missing readings
@scn("E2E-D", "D", "Missing required sensor readings", pre="Server running", inp="valid body with each of the 14 readings removed in turn; empty readings; a null reading; missing motor id; missing timestamp",
     exp="422 (never 500); error names the missing feature; nothing is saved", sev="High if a prediction is made from incomplete data", fix="Check validate_single_readings", layer="Model integration")
def test_D_missing(api, srv, samples, rec):
    good = samples["samples"]["Normal"][1]["readings"]; before = db_count(srv.db); n = 0
    for f in FEATURES:
        body = {k: v for k, v in good.items() if k != f}
        r = post(api, "MISS-1", body); n += 1
        assert r.status_code == 422, (f, r.status_code, r.text[:200])
        e = r.json()["error"]; assert f in json.dumps(e["details"]), f"{f} not named in {e}"
    r = post(api, "MISS-1", {}); assert r.status_code == 422
    r = post(api, "MISS-1", {**good, "de_h_ge": None}); assert r.status_code == 422
    r = api.post("/api/assessments", json={"measured_at": WHEN, "readings": good}); assert r.status_code == 422
    r = api.post("/api/assessments", json={"motor_id": "MISS-1", "readings": good}); assert r.status_code == 422
    assert db_count(srv.db) == before, "a rejected request created a database row"
    rec.actual_(f"{n} single-field omissions + 4 other cases: all 422 with a named field; database row count unchanged ({before})")


# =================================================================== E  invalid numbers and timestamps
@scn("E2E-E", "E", "Invalid numeric values and timestamps", pre="Server running",
     inp="readings: 'abc', '', true, [], {}, NaN, Infinity, -Infinity, 1e999, 400-digit integer; timestamps: 'not-a-date', '2025-13-45T00:00:00', '2025-02-30T10:00:00', '', null, 12345.5, year 0001, 9999-12-31T23:59:59-05:00",
     exp="422 for every one (never 500); nothing saved; an extreme but finite value is accepted only with an out-of-range warning", sev="High", fix="Check schemas.py validators", layer="Model integration")
def test_E_invalid(api, srv, samples, rec):
    good = samples["samples"]["Alert"][1]["readings"]; before = db_count(srv.db); checked = 0
    def raw(readings_json=None, ts='"2025-04-01T07:20:00"'):
        r = {**good}; body = json.dumps({"motor_id": "BAD-1", "measured_at": "@@", "readings": r}).replace('"@@"', ts)
        if readings_json:
            body = body.replace(f'"de_h_ge": {good["de_h_ge"]}', f'"de_h_ge": {readings_json}')
        return api.post("/api/assessments", content=body, headers={"Content-Type": "application/json"})
    for v in ['"abc"', '""', "true", "[]", "{}", "NaN", "Infinity", "-Infinity", "1e999", "9" * 400, '"1,5"', '"12abc"', "null"]:
        r = raw(readings_json=v); checked += 1
        assert r.status_code == 422, (v[:20], r.status_code, r.text[:200])
    for ts in ['"not-a-date"', '"2025-13-45T00:00:00"', '"2025-02-30T10:00:00"', '""', "null", "12345.5", '"0001-01-01T00:00:00"', '"9999-12-31T23:59:59-05:00"', '"01/32/2025"']:
        r = raw(ts=ts); checked += 1
        assert r.status_code == 422, (ts, r.status_code, r.text[:200])
    assert db_count(srv.db) == before
    ok = post(api, "BAD-OK", {**good, "de_h_temp_c": 250.0})
    assert ok.status_code == 201 and any(w["feature"] == "de_h_temp_c" for w in ok.json()["input_warnings"])
    rec.actual_(f"{checked} invalid values/timestamps → all 422, 0 rows added. 250 degC (finite, outside training range) → 201 with an input warning, as designed (no engineering limits exist)")


# =================================================================== F  CSV problems
@scn("E2E-F", "F", "CSV with missing or incorrectly named columns", pre="Server running", inp="CSV missing de_h_ge; CSV with 'de_h_velocity' instead of de_h_velocity_mm_s; upper-case header; duplicate header; empty file; header only; no header",
     exp="validate: valid=false and the issue names the column; batch: 4xx, never 5xx; nothing saved", sev="High", fix="Check csv_io.parse_and_validate", layer="Model integration")
def test_F_csv_columns(api, srv, samples, rec):
    rows = [{"readings": s["readings"]} for s in samples["samples"]["Normal"][:2]]; before = (db_count(srv.db), db_count(srv.db, "upload_batches")); log = []
    cases = {
        "missing de_h_ge": (csv_text(rows, drop=("de_h_ge",)), "de_h_ge"),
        "unknown extra column 'comment'": (csv_text(rows, extra={"comment": "x"}), "comment"),
        "misnamed de_h_velocity": (csv_text(rows, rename={"de_h_velocity_mm_s": "de_h_velocity"}), "de_h_velocity_mm_s"),
        "upper-case header": (csv_text(rows, rename={"de_h_ge": "DE_H_GE"}), "de_h_ge"),
        "empty file": (b"", None), "header only": (csv_text([]), None),
        "no header": (",".join(str(v) for v in rows[0]["readings"].values()) + "\r\n", None),
    }
    for name, (txt, col) in cases.items():
        v = upload(api, txt, "/api/uploads/validate"); b = upload(api, txt)
        assert v.status_code < 500 and b.status_code < 500, (name, v.status_code, b.status_code)
        assert b.status_code in (400, 413, 415, 422), (name, "batch should reject", b.status_code, b.text[:200])
        if v.status_code == 200:
            assert v.json()["valid"] is False, name
            if col: assert any(col in str(i) for i in v.json()["issues"]), (name, v.json()["issues"])
        log.append(f"{name}: validate {v.status_code}, batch {b.status_code}")
    dup = csv_text(rows).replace("de_h_ge,", "de_h_ge,de_h_ge,", 1)
    assert upload(api, dup).status_code in (400, 422)
    assert (db_count(srv.db), db_count(srv.db, "upload_batches")) == before, "a rejected CSV left rows or an upload batch behind"
    rec.actual_("; ".join(log) + "; duplicate header → rejected; predictions and upload_batches tables unchanged")


@scn("E2E-CSV1", "F", "Valid CSV: batch prediction, database rows, history and export", pre="Server running; 6-row CSV: 2 held-out rows per class (chosen by truth label)",
     inp="CSV with 6 rows and the tolerated condition_label column", exp="200; per-row condition equals independent reference; 6 DB rows with one batch id; class_counts add up; history and export contain them",
     sev="High", fix="Check routes_predict.predict_batch", layer="Model integration (trained synthetic model)")
def test_CSV_valid(api, srv, samples, rec):
    sel = [(c, s) for c in ("Normal", "Alert", "Danger") for s in samples["samples"][c][:2]]
    rows = [{"readings": s["readings"], "motor": unique("CSVM")} for _, s in sel]
    txt = csv_text(rows, extra={"condition_label": "Normal"}); before = db_count(srv.db)
    v = upload(api, txt, "/api/uploads/validate").json(); assert v["valid"] is True and "condition_label" in v["ignored_columns"]
    r = upload(api, txt); assert r.status_code == 200, r.text
    j = r.json(); assert j["record_count"] == 6 and len(j["results"]) == 6
    for (c, s), res in zip(sel, j["results"]):
        assert res["predicted_condition"] == s["reference_prediction"], (c, res["predicted_condition"], s["reference_prediction"])
    assert sum(j["class_counts"].values()) == 6
    d = [decode_row(x) for x in db_rows(srv.db, "batch_id=?", (j["batch_id"],))]
    assert len(d) == 6 and db_count(srv.db) == before + 6 and all(x["source"] == "csv" for x in d)
    assert [x["predicted_condition"] for x in d] == [r_["predicted_condition"] for r_ in j["results"]]
    assert all(x["input_readings"] is None for x in d)
    _, erows, _ = export(api, batch_id=j["batch_id"]) if False else (None, [], None)
    allx = export(api, limit=1000)[1] if False else None
    r2, erows, _ = export(api)
    ids = {int(x["prediction_id"]): x for x in erows}
    assert all(x["id"] in ids and ids[x["id"]]["predicted_condition"] == x["predicted_condition"] for x in d)
    rec.actual_(f"6 rows → {j['class_counts']}; each condition equals the independent reference; 6 sqlite rows with batch_id; all 6 present in the export. Note: CSV rows store no recommendation JSON (regenerated on read, flagged)")


# =================================================================== G  model unavailable / incompatible
def _copy_bundle(src, name):
    d = OUT / f"bundle_{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); return d




def _start_expect_refusal(bundle, name, **kw):
    db = OUT / f"g_{name}.db"; db.unlink(missing_ok=True)
    s = Server(bundle, db, port=8110 + abs(hash(name)) % 80, **kw); s.start(timeout=20)
    refused = s.exited(); tail = s.log_tail(); code = s.proc.returncode; s.stop()
    return refused, code, tail


@scn("E2E-G1", "G", "Model artifact missing: server refuses to start (default) with a clear message", pre="MODEL_BUNDLE_DIR points to a folder that does not exist; REQUIRE_MODEL_AT_STARTUP=true",
     inp="start backend", exp="process exits non-zero; log says STARTUP ABORTED and names the problem; no stack-trace with paths of secrets", sev="High", fix="Check ModelRegistry.load / lifespan", layer="Model integration")
def test_G1_missing(bundle_dir, rec):
    refused, code, tail = _start_expect_refusal(OUT / "no_such_bundle", "missing")
    assert refused and code not in (0, None) and "STARTUP ABORTED" in tail
    rec.actual_(f"exit code {code}; log: {tail.strip().splitlines()[-1][:160]}")


@scn("E2E-G2", "G", "Model unavailable but server allowed to start: health says so, assessments refused (503), history still readable", pre="REQUIRE_MODEL_AT_STARTUP=false, no bundle",
     inp="GET /api/health, /api/model-info, POST /api/assessments, GET /api/predictions", exp="health model_ready=false/degraded; POST 503 with a plain message; no row saved; history 200",
     sev="High", fix="Check require_bundle dependency", layer="Model integration")
def test_G2_no_model(bundle_dir, samples, rec):
    db = OUT / "g2.db"; db.unlink(missing_ok=True)
    with Server(OUT / "no_such_bundle", db, port=8120, require_model=False) as s:
        assert not s.exited(), s.log_tail()
        c = httpx.Client(base_url=s.url, timeout=10)
        h = c.get("/api/health").json(); assert h["model_ready"] is False and h["status"] != "ok", h
        m = c.get("/api/model-info").json(); assert m["model_ready"] is False and m["reason"]
        r = post(c, "NOMODEL", samples["samples"]["Normal"][0]["readings"]); assert r.status_code == 503, r.text
        assert "model" in r.json()["error"]["message"].lower()
        assert db_count(db) == 0
        assert c.get("/api/predictions").status_code == 200
        rec.actual_(f"health={h['status']}/model_ready={h['model_ready']}; POST → 503 '{r.json()['error']['message'][:80]}'; 0 rows; history 200")


def _break(name, fn):
    d = _copy_bundle(OUT / "bundle", name); fn(d); return d


@scn("E2E-G3", "G", "Incompatible or corrupted artifacts are refused at startup", pre="Copies of the trained bundle damaged in 6 different ways",
     inp="(a) feature order in preprocessing.json swapped, manifest re-signed; (b) weights replaced by a network with the wrong input width, re-signed; (c) weights.npz altered, manifest NOT re-signed; (d) class_mapping with a 4th class, re-signed; (e) a required file deleted; (f) FAST_DEBUG smoke-test bundle",
     exp="every one: process exits non-zero with STARTUP ABORTED; never serves predictions from a damaged bundle", sev="Critical", fix="Check artifacts.load_bundle", layer="Model integration")
def test_G3_incompatible(bundle_dir, rec):
    from conftest import sign_manifest
    def a(d):
        p = json.loads((d / "preprocessing.json").read_text()); n = p["feature_names"]; n[0], n[1] = n[1], n[0]
        (d / "preprocessing.json").write_text(json.dumps(p)); sign_manifest(d)
    def b(d):
        w = np.load(d / "weights.npz"); arr = {k: w[k] for k in w.files}; arr["W0"] = arr["W0"][:10]; np.savez(d / "weights.npz", **arr); sign_manifest(d)
    def c(d):
        w = np.load(d / "weights.npz"); arr = {k: w[k] for k in w.files}; arr["b1"] = arr["b1"] + 0.5; np.savez(d / "weights.npz", **arr)
    def dd(d):
        cm = json.loads((d / "class_mapping.json").read_text()); cm["classes"].append({"id": 3, "name": "Critical"}); (d / "class_mapping.json").write_text(json.dumps(cm)); sign_manifest(d)
    def e(d): (d / "preprocessing.json").unlink()
    def f(d):
        m = json.loads((d / "training_metadata.json").read_text()); m["fast_debug_run"] = True; (d / "training_metadata.json").write_text(json.dumps(m)); sign_manifest(d)
    out = []
    for name, fn in {"a_feature_order": a, "b_weight_shape": b, "c_tampered_weights": c, "d_extra_class": dd, "e_missing_file": e, "f_smoke_test": f}.items():
        d = _break(name, fn); refused, code, tail = _start_expect_refusal(d, name)
        assert refused and "STARTUP ABORTED" in tail, f"{name}: server did not refuse the damaged bundle.\n{tail}"
        out.append(f"{name}: refused ({tail.strip().splitlines()[-1][-110:]})")
    rec.actual_("; ".join(out))


# =================================================================== H  database / backend failure
@scn("E2E-H1", "H", "Database failure while the backend is running", pre="Backend running with a real SQLite file; one assessment saved; then the predictions table is dropped underneath the server",
     inp="POST /api/assessments, GET /api/predictions, GET /api/health after the table disappears", exp="503 database_unavailable with a plain message; response never claims saved=true; no SQL text or file path in the response; server keeps running",
     sev="High (false 'saved' claim)", fix="Check DatabaseUnavailableError handlers", layer="Model integration")
def test_H1_db_failure(bundle_dir, samples, rec):
    db = OUT / "h1.db"; db.unlink(missing_ok=True)
    with Server(bundle_dir, db, port=8130) as s:
        c = httpx.Client(base_url=s.url, timeout=10); rd = samples["samples"]["Normal"][2]["readings"]
        assert post(c, "H1", rd).status_code == 201
        con = sqlite3.connect(str(db)); con.execute("DROP TABLE predictions"); con.commit(); con.close()
        r = post(c, "H1", rd); body = r.text
        assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable", body
        assert '"saved": true' not in body and "predictions" not in body.lower().replace("no predictions", "") and "sqlite" not in body.lower() and str(db) not in body
        assert c.get("/api/predictions").status_code == 503
        assert c.get("/api/health").status_code in (200, 503) and s.proc.poll() is None
        rec.actual_(f"after DROP TABLE: POST → {r.status_code} {r.json()['error']['code']} '{r.json()['error']['message'][:90]}'; GET /predictions → 503; server still running; no SQL/path in body")


@scn("E2E-H2", "H", "Database unreachable at startup", pre="DATABASE_URL points to a folder that does not exist", inp="start backend", exp="process exits non-zero with a clear message; no password/URL echoed",
     sev="Medium", fix="Check lifespan / session creation", layer="Model integration")
def test_H2_db_startup(bundle_dir, rec):
    s = Server(bundle_dir, Path("/no_such_dir_e2e/x.db") if Path("/").anchor == "/" else Path("Z:/no_such_dir_e2e/x.db"), port=8131)
    s.start(timeout=20); refused = s.exited(); tail = s.log_tail(); s.stop()
    assert refused, "server started with an unreachable database"
    assert "STARTUP ABORTED" in tail or "unable to open database" in tail.lower() or "OperationalError" in tail
    rec.actual_("refused to start: " + tail.strip().splitlines()[-1][:160])


# =================================================================== I  repeated submission
@scn("E2E-I", "I", "Repeated submission (double click, retry, replay)", pre="Server running", inp="same Idempotency-Key + same readings twice; same key + different readings; 8 concurrent identical requests; no key twice; same CSV uploaded twice",
     exp="same key+payload → one row, second answer 200 duplicate=true with the same id; same key, different payload → 409; 8 concurrent → exactly 1 row; KNOWN GAP: same CSV twice stores twice",
     sev="Medium", fix="Add idempotency to /predict/batch (risk R1)", layer="Model integration")
def test_I_repeat(api, srv, samples, rec):
    rd = samples["samples"]["Alert"][2]["readings"]; m = unique("REP"); key = "rep-" + m.replace("-", "")[:20]
    a = post(api, m, rd, key=key); b = post(api, m, rd, key=key)
    assert a.status_code == 201 and b.status_code == 200 and b.json()["duplicate"] is True and a.json()["assessment_id"] == b.json()["assessment_id"]
    assert len(db_rows(srv.db, "motor_id=?", (m,))) == 1
    c = post(api, m, samples["samples"]["Danger"][2]["readings"], key=key); assert c.status_code == 409 and len(db_rows(srv.db, "motor_id=?", (m,))) == 1
    m2 = unique("RACE"); k2 = "race-" + m2.replace("-", "")[:20]; res = []
    def go():
        with httpx.Client(base_url=srv.url, timeout=20) as cl: res.append(post(cl, m2, rd, key=k2).status_code)
    ts = [threading.Thread(target=go) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(set(res)) <= [200, 201] and len(db_rows(srv.db, "motor_id=?", (m2,))) == 1, (res,)
    m3 = unique("NOKEY"); post(api, m3, rd); post(api, m3, rd); nokey = len(db_rows(srv.db, "motor_id=?", (m3,)))
    rec.actual_(f"same key twice: 201 then 200 duplicate=true, 1 row; same key different data: 409; 8 concurrent: {len(res)} replies {sorted(set(res))}, 1 row; WITHOUT a key two identical submissions → {nokey} rows (by design; the web form always sends a key)")
    assert nokey == 2


@scn("E2E-I2", "I", "Same CSV file uploaded twice (known gap R1)", pre="Server running", inp="identical CSV uploaded twice", exp="ideally recognised as a repeat; today it is stored twice",
     sev="Medium (known, documented as risk R1)", fix="Add a file-hash idempotency key to /api/predict/batch", layer="Model integration")
@pytest.mark.xfail(strict=True, reason="Known gap R1: /api/predict/batch has no duplicate protection")
def test_I2_csv_twice(api, srv, samples, rec):
    rows = [{"readings": samples["samples"]["Normal"][3]["readings"], "motor": unique("TWICE")}]; txt = csv_text(rows); before = db_count(srv.db)
    upload(api, txt); upload(api, txt)
    assert db_count(srv.db) == before + 1, "the same file created two sets of rows"


# =================================================================== J  unknown motor
@scn("E2E-J", "J", "History query for an unknown motor ID (and other unknown ids)", pre="Server running", inp="GET /api/predictions?motor_id=NOSUCH; GET /api/predictions/999999; GET /api/assessments/999999; export for NOSUCH; /api/motors",
     exp="history: 200 with total 0; unknown record ids: 404 with a plain message; export: 200 with header only; never 500", sev="Medium", fix="Check history routes", layer="Model integration")
def test_J_unknown(api, srv, rec):
    h = api.get("/api/predictions", params={"motor_id": "NOSUCH-MOTOR"}); assert h.status_code == 200 and h.json()["total"] == 0 and h.json()["items"] == []
    for u in ("/api/predictions/999999", "/api/assessments/999999"):
        r = api.get(u); assert r.status_code == 404 and r.json()["error"]["code"] == "not_found" and "No" in r.json()["error"]["message"]
    r, rows, header = export(api, motor_id="NOSUCH-MOTOR"); assert r.status_code == 200 and rows == [] and r.headers["x-rows-exported"] == "0"
    assert "NOSUCH-MOTOR" not in [m["motor_id"] for m in api.get("/api/motors").json()["items"]]
    c = api.get("/api/predictions", params={"predicted_condition": "Banana"}); assert c.status_code == 200 and c.json()["total"] == 0
    rec.actual_("motor_id=NOSUCH → 200 total 0; ids 999999 → 404 not_found; export → 200, 0 rows; unknown condition 'Banana' → 200, 0 rows (no error, no 500)")


# =================================================================== K  persistence across a restart
@scn("E2E-K", "K", "A saved prediction is retrieved from history, also after the server is restarted", pre="Own server and DB file", inp="save one assessment per class, stop the server, start it again on the same DB",
     exp="after restart GET by id, history and export return identical condition, scores, recommendations", sev="High", fix="Check DB commit / URL", layer="Model integration")
def test_K_restart(bundle_dir, samples, rec):
    db = OUT / "k.db"; db.unlink(missing_ok=True); saved = {}
    with Server(bundle_dir, db, port=8140) as s:
        c = httpx.Client(base_url=s.url, timeout=10)
        for cls in ("Normal", "Alert", "Danger"):
            j = post(c, f"K-{cls}", samples["samples"][cls][3]["readings"]).json(); saved[cls] = j
    with Server(bundle_dir, db, port=8141) as s2:
        c = httpx.Client(base_url=s2.url, timeout=10)
        for cls, j in saved.items():
            g = c.get(f"/api/assessments/{j['assessment_id']}").json()
            assert (g["predicted_condition"], g["scores"], g["recommendations"], g["motor_id"]) == (j["predicted_condition"], j["scores"], j["recommendations"], j["motor_id"])
            hi = c.get("/api/predictions", params={"motor_id": f"K-{cls}"}).json(); assert hi["total"] == 1 and hi["items"][0]["predicted_condition"] == j["predicted_condition"]
        _, erows, _ = export(c); assert {r["motor_id"] for r in erows} == {"K-Normal", "K-Alert", "K-Danger"}
    rec.actual_("3 records (" + ", ".join(f"{k}→{v['predicted_condition']}" for k, v in saved.items()) + ") identical after restart through GET by id, history and export")


# =================================================================== L  export content
@scn("E2E-L", "L", "Result export contains the expected records and columns", pre="Records of several motors and classes stored", inp="export all / by motor / by condition / by date; motor id starting with '='",
     exp="exact header; one line per DB row with matching values; filters respected; X-Total-Matching equals lines; no raw sensor readings; spreadsheet-formula protection; empty export keeps the same header",
     sev="Medium", fix="Check routes_history.build_report_csv", layer="Model integration")
def test_L_export(bundle_dir, samples, rec):
    db = OUT / "l.db"; db.unlink(missing_ok=True)
    with Server(bundle_dir, db, port=8150) as s:
        c = httpx.Client(base_url=s.url, timeout=10); made = {}
        for cls in ("Normal", "Alert", "Danger"):
            for i in range(2): made[(cls, i)] = post(c, f"L-{cls}", samples["samples"][cls][i]["readings"], when=f"2025-04-0{i + 1}T07:20:00").json()
        assert post(c, "=1+1", samples["samples"]["Normal"][0]["readings"]).status_code == 422, "motor ids with formula characters must be refused"
        post(c, "L-Normal", samples["samples"]["Normal"][0]["readings"], when="2025-05-01T07:20:00", equipment_description="=1+1")
        r, rows, header = export(c)
        assert header == EXPORT_COLS, f"header differs:\n got {header}\nwant {EXPORT_COLS}"
        assert len(rows) == 7 == int(r.headers["x-total-matching"]) == db_count(db) and r.headers["x-export-truncated"] == "false"
        by_id = {int(x["prediction_id"]): x for x in rows}
        for d in (decode_row(x) for x in db_rows(db)):
            e = by_id[d["id"]]
            assert (e["predicted_condition"], e["model_version"], e["recommendation_summary"]) == (d["predicted_condition"], d["model_version"], d["recommendation_summary"])
            assert all(abs(float(e[f"model_score_{k}"]) - v) < 1e-5 for k, v in d["scores"].items())
        assert not any(f in header for f in FEATURES), "raw sensor columns present in export"
        assert any(x["equipment_description"] == "'=1+1" for x in rows), "formula-like free text not neutralised"
        _, d_rows, _ = export(c, predicted_condition="Danger"); assert {x["predicted_condition"] for x in d_rows} == {"Danger"} and len(d_rows) == 2
        _, m_rows, _ = export(c, motor_id="L-Alert"); assert len(m_rows) == 2 and {x["motor_id"] for x in m_rows} == {"L-Alert"}
        _, t_rows, _ = export(c, measured_from="2025-04-02", measured_to="2025-04-02"); assert len(t_rows) == 3 and all(x["measured_at"].startswith("2025-04-02") for x in t_rows)
        _, e_rows, e_header = export(c, motor_id="NOSUCH")
        assert e_rows == [] and e_header == EXPORT_COLS, f"EMPTY export header differs from the normal one: {e_header}"
        rec.actual_(f"header has the {len(header)} expected columns; 7 rows == 7 DB rows == X-Total-Matching; condition filter 2 rows; motor filter 2; date filter 3; formula-like description neutralised and formula-like motor id refused (422); empty export keeps the full header")
