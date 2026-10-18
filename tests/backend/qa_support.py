"""Helpers for the backend QA suite (files named test_qa_*.py).

TEST CATEGORIES (every QA test belongs to exactly one, and says so in its module docstring or marker):

  real_artifacts     Uses the TRAINED model bundle from ml/artifacts (or $PM_TEST_BUNDLE_DIR).
                     If no bundle exists these tests are SKIPPED with the word BLOCKED in the reason. A skip is NOT a pass.
  synthetic_bundle   Uses the real loading + inference code on a bundle with made-up weights built in the test.
                     Proves the software, says nothing about model quality. (Most QA tests.)
  mock_ml            The model is replaced by a stub (monkeypatch). Used ONLY to test backend behaviour independent of inference.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from app.core.config import PROJECT_ROOT
from conftest import CLASSES, FEATURES, TS_FORMAT, reference_forward, sign_manifest

ARTIFACTS_ROOT = PROJECT_ROOT / "ml" / "artifacts"


def find_real_bundle() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("PM_TEST_BUNDLE_DIR"):
        candidates.append(Path(os.environ["PM_TEST_BUNDLE_DIR"]))
    if ARTIFACTS_ROOT.is_dir():
        candidates += sorted(p for p in ARTIFACTS_ROOT.iterdir() if p.is_dir())
    for c in candidates:
        if (c / "MANIFEST.json").is_file():
            return c
    return None


def build_bundle(d: Path, *, layers, class_doc=None, mean=None, scale=None, version="vQA.1", provisional=False, name="pm_condition_ann_vQA"):
    """Write a complete, correctly signed bundle with the given (W, b) layers. Hidden layers use ReLU, the last uses softmax."""
    d.mkdir(parents=True, exist_ok=True)
    mean = np.full(len(FEATURES), 10.0) if mean is None else mean
    scale = np.full(len(FEATURES), 2.0) if scale is None else scale
    np.savez(d / "weights.npz", **{f"{k}{i}": a for i, (W, b) in enumerate(layers) for k, a in (("W", W), ("b", b))})
    (d / "preprocessing.json").write_text(json.dumps({"type": "StandardScaler", "feature_names": FEATURES, "mean": mean.tolist(), "scale": scale.tolist()}))
    (d / "feature_schema.json").write_text(json.dumps({"order_is_contract": True, "features": [
        {"name": f, "unit": "u", "description": f, "observed_train_min": float(mean[i] - 3 * scale[i]), "observed_train_max": float(mean[i] + 3 * scale[i])}
        for i, f in enumerate(FEATURES)]}))
    (d / "class_mapping.json").write_text(json.dumps(class_doc or {"classes": [{"id": i, "name": n} for i, n in enumerate(CLASSES)]}))
    acts = ["relu"] * (len(layers) - 1) + ["softmax"]
    (d / "model_architecture.json").write_text(json.dumps({"layers": [{"type": "dense", "units": int(W.shape[1]), "activation": a} for (W, _), a in zip(layers, acts)]}))
    (d / "training_metadata.json").write_text(json.dumps({
        "bundle_version": version, "created_utc": "2026-01-01T00:00:00+00:00", "task": "QA test task", "provisional_label_provenance": provisional,
        "deployable_for_decisions": False, "option_b_future_failure_prediction_supported": False, "fast_debug_run": False,
        "dataset": {"file_name": "qa.csv", "timestamp_format_assumed": TS_FORMAT}}))
    names = [c["name"] for c in sorted((class_doc or {"classes": [{"id": i, "name": n} for i, n in enumerate(CLASSES)]})["classes"], key=lambda c: c["id"])]
    probes = []
    for pname, vec in {"mean": mean, "plus": mean + scale, "minus": mean - scale}.items():
        p = reference_forward(mean, scale, layers, vec.reshape(1, -1))[0]
        probes.append({"name": pname, "readings": dict(zip(FEATURES, map(float, vec))), "expected_probabilities": dict(zip(names, map(float, p)))})
    (d / "parity_probe.json").write_text(json.dumps({"tolerance": 1e-5, "probes": probes}))
    sign_manifest(d, name)


def forced_layers(k: int, n_classes: int = 3, strength: float = 25.0):
    """A network that ignores its input and always scores class index k highest (softmax ~ one-hot at k)."""
    bias = np.zeros(n_classes)
    bias[k] = strength
    return [(np.zeros((len(FEATURES), 4)), np.zeros(4)), (np.zeros((4, n_classes)), bias)]


def build_forced_bundle(d: Path, k: int, **kw):
    build_bundle(d, layers=forced_layers(k), **kw)


def make_assessment_body(readings: dict, **over) -> dict:
    body = {"motor_id": "QA-M1", "measured_at": "2025-04-01T07:20:00", "readings": readings}
    body.update(over)
    return body


def need_real_bundle():
    path = find_real_bundle()
    if path is None:
        pytest.skip("BLOCKED: no trained model bundle found in ml/artifacts (copy the Colab export there, or set PM_TEST_BUNDLE_DIR).")
    return path


from contextlib import contextmanager


@contextmanager
def served(tmp_path, k: int, *, class_doc=None, name="forced", **settings_kw):
    """Run the real app on a bundle whose network always picks output index k. No mocks: real loader, real inference, real database."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import make_settings
    d = tmp_path / name
    build_forced_bundle(d, k, class_doc=class_doc)
    with TestClient(create_app(make_settings(d, **settings_kw))) as c:
        yield c
