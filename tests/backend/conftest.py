"""Shared fixtures.

The bundle built here follows the Colab notebook's artifact contract but contains RANDOM weights.
It exists only to test the software. Its predictions mean nothing.
"""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

FEATURES = ["de_h_velocity_mm_s", "de_h_ge", "de_h_temp_c", "de_v_velocity_mm_s", "de_v_ge", "de_v_temp_c",
            "nde_h_velocity_mm_s", "nde_h_ge", "nde_h_temp_c", "nde_v_velocity_mm_s", "nde_v_ge", "nde_v_temp_c",
            "rotational_speed_rpm", "load_percent"]
CLASSES = ["Normal", "Alert", "Danger"]
TS_FORMAT = "%m/%d/%Y %H:%M"


def reference_forward(mean, scale, layers, X):
    """Independent implementation used to compute the expected probe values."""
    z = (np.asarray(X, float) - mean) / scale
    for i, (W, b) in enumerate(layers):
        z = z @ W + b
        if i < len(layers) - 1:
            z = np.maximum(z, 0)
        else:
            e = np.exp(z - z.max(axis=1, keepdims=True)); z = e / e.sum(axis=1, keepdims=True)
    return z


def sign_manifest(d: Path, bundle_name="pm_condition_ann_vTEST") -> None:
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir()) if p.is_file() and p.name != "MANIFEST.json"}
    (d / "MANIFEST.json").write_text(json.dumps({"bundle": bundle_name, "files": files}, indent=2))


def make_bundle(d: Path, *, version="v9.9.9", provisional=True, fast_debug=False, seed=0, units=8):
    rng = np.random.default_rng(seed)
    d.mkdir(parents=True, exist_ok=True)
    mean, scale = rng.uniform(1, 50, len(FEATURES)), rng.uniform(0.5, 5, len(FEATURES))
    layers = [(rng.normal(size=(len(FEATURES), units)), rng.normal(size=units)), (rng.normal(size=(units, len(CLASSES))), rng.normal(size=len(CLASSES)))]
    np.savez(d / "weights.npz", **{f"{k}{i}": a for i, (W, b) in enumerate(layers) for k, a in (("W", W), ("b", b))})
    (d / "preprocessing.json").write_text(json.dumps({"type": "StandardScaler", "feature_names": FEATURES, "mean": mean.tolist(), "scale": scale.tolist()}))
    (d / "feature_schema.json").write_text(json.dumps({"order_is_contract": True, "features": [
        {"name": f, "unit": "u", "description": f"desc {f}", "observed_train_min": float(mean[i] - 3 * scale[i]), "observed_train_max": float(mean[i] + 3 * scale[i])}
        for i, f in enumerate(FEATURES)]}))
    (d / "class_mapping.json").write_text(json.dumps({"classes": [{"id": i, "name": n} for i, n in enumerate(CLASSES)]}))
    (d / "model_architecture.json").write_text(json.dumps({"layers": [{"type": "dense", "units": units, "activation": "relu"},
                                                                        {"type": "dense", "units": len(CLASSES), "activation": "softmax"}]}))
    (d / "training_metadata.json").write_text(json.dumps({
        "bundle_version": version, "created_utc": "2026-01-01T00:00:00+00:00", "task": "test task", "provisional_label_provenance": provisional,
        "deployable_for_decisions": False, "option_b_future_failure_prediction_supported": False, "fast_debug_run": fast_debug,
        "dataset": {"file_name": "test.csv", "timestamp_format_assumed": TS_FORMAT},
        "test_metrics": {"ANN": {"n": 100, "accuracy": 0.5, "balanced_accuracy": 0.4, "macro_f1": 0.3, "other": 1}}}))
    probes = []
    for name, vec in {"mean": mean, "plus": mean + scale, "minus": mean - scale}.items():
        p = reference_forward(mean, scale, layers, vec.reshape(1, -1))[0]
        probes.append({"name": name, "readings": dict(zip(FEATURES, map(float, vec))), "expected_probabilities": dict(zip(CLASSES, map(float, p)))})
    (d / "parity_probe.json").write_text(json.dumps({"tolerance": 1e-5, "probes": probes}))
    sign_manifest(d)
    return {"mean": mean, "scale": scale, "layers": layers}


def make_settings(bundle_dir, **kw) -> Settings:
    base = dict(environment="test", model_bundle_dir=bundle_dir, database_url="sqlite:///:memory:", auto_create_tables=True,
                cors_origins="http://localhost:5173", _env_file=None)
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def bundle_dir(tmp_path):
    d = tmp_path / "bundle"
    make_bundle(d)
    return d


@pytest.fixture
def truth(tmp_path):
    return make_bundle(tmp_path / "truth_bundle")   # same seed -> same numbers as bundle_dir


@pytest.fixture
def client(bundle_dir):
    with TestClient(create_app(make_settings(bundle_dir))) as c:
        yield c


@pytest.fixture
def loaded(bundle_dir):
    from app.services.artifacts import load_bundle
    return load_bundle(bundle_dir, allow_smoke_test=False)




@pytest.fixture
def readings(loaded):
    return {n: float(m) for n, m in zip(loaded.feature_names, loaded.mean)}


def csv_text(loaded, rows=2, *, with_ts=True, extra_cols=(), drop_cols=(), mutate=None, ids=("REC{:03d}", "MOT{:02d}")):
    cols = ["record_id", "motor_id"] + (["measured_at"] if with_ts else []) + list(loaded.feature_names) + list(extra_cols)
    cols = [c for c in cols if c not in drop_cols]
    lines = [",".join(cols)]
    for r in range(rows):
        vals = {"record_id": ids[0].format(r + 1), "motor_id": ids[1].format(r % 2 + 1), "measured_at": f"2025-04-0{r % 9 + 1} 07:20:00"}
        vals.update({n: f"{m + 0.1 * r:.3f}" for n, m in zip(loaded.feature_names, loaded.mean)})
        vals.update({c: "x" for c in extra_cols})
        if mutate:
            mutate(r, vals)
        lines.append(",".join(vals[c] for c in cols))
    return "\r\n".join(lines) + "\r\n"


def upload(client, text, name="data.csv", ctype="text/csv", url="/api/predict/batch"):
    data = text if isinstance(text, bytes) else text.encode()
    return client.post(url, files={"file": (name, data, ctype)})
