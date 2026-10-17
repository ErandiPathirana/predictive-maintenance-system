"""Writes REAL backend responses to frontend/src/test/fixtures/*.json.

The frontend type-checks these files against its TypeScript interfaces, so a backend schema change that the
frontend does not follow fails `npm run typecheck`. The model used here has RANDOM weights (test bundle);
the fixtures contain no real data and no research results.
Run from backend/:  python scripts/export_api_fixtures.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from conftest import csv_text, make_bundle, make_settings  # noqa: E402
from app.services.artifacts import load_bundle  # noqa: E402

OUT = ROOT / "frontend" / "src" / "test" / "fixtures"


def save(name, resp):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(resp.json(), indent=2), encoding="utf-8")
    print(f"{name}: HTTP {resp.status_code}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        bdir = Path(tmp) / "bundle"
        make_bundle(bdir)
        loaded = load_bundle(bdir)
        with TestClient(create_app(make_settings(bdir))) as c:
            save("health", c.get("/api/health"))
            save("model_info", c.get("/api/model-info"))
            save("features", c.get("/api/features"))
            text = csv_text(loaded, rows=6)
            files = lambda t: {"file": ("fixture.csv", t.encode(), "text/csv")}
            save("validate_ok", c.post("/api/uploads/validate", files=files(text)))
            bad = csv_text(loaded, rows=3, mutate=lambda r, v: v.update(de_h_ge="abc") if r == 1 else None)
            save("validate_bad", c.post("/api/uploads/validate", files=files(bad)))
            save("error_invalid_csv", c.post("/api/predict/batch", files=files(bad)))
            save("batch_response", c.post("/api/predict/batch", files=files(text)))
            readings = {n: float(m) for n, m in zip(loaded.feature_names, loaded.mean)}
            save("predict_single", c.post("/api/predict", json={"record_id": "ONE", "motor_id": "MOT01", "readings": readings}))
            save("predictions_page", c.get("/api/predictions", params={"limit": 50}))
            save("batches", c.get("/api/batches"))
            save("error_not_found", c.get("/api/predictions/999"))
            save("error_invalid_request", c.post("/api/predict", json={"readings": {"de_h_ge": "x"}}))


if __name__ == "__main__":
    main()
