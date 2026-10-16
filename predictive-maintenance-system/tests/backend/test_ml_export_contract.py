"""Contract test: files written by ml/scripts/export_artifacts.py (Colab side)
must be loadable and usable by the backend. Uses random test data only."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.config import Settings
from app.schemas import PredictionRequest
from app.services.model_loader import ModelRegistry
from app.services.prediction import predict_failure

SCRIPT = Path(__file__).resolve().parents[2] / "ml" / "scripts" / "export_artifacts.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_artifacts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.export_artifacts


def _train(columns):
    rng = np.random.default_rng(1)
    x = pd.DataFrame(rng.normal(size=(100, len(columns))), columns=columns)
    y = (x.iloc[:, 0] > 0).astype(int)
    return make_pipeline(StandardScaler(), LogisticRegression()).fit(x, y)


def test_exported_files_load_and_predict(tmp_path):
    export = _load_exporter()
    export(_train(["f1", "f2"]), ["f1", "f2"], tmp_path, "contract-test", "v0", decision_threshold=0.4)

    registry = ModelRegistry(Settings(model_dir=tmp_path))
    registry.load()
    assert registry.is_ready, registry.not_ready_reason
    result = predict_failure(registry, PredictionRequest(readings={"f1": 0.1, "f2": -0.2}))
    assert 0 <= result.failure_probability <= 1
    assert result.decision_threshold == 0.4


def test_export_rejects_column_order_mismatch(tmp_path):
    export = _load_exporter()
    with pytest.raises(ValueError, match="do not match"):
        export(_train(["f1", "f2"]), ["f2", "f1"], tmp_path, "m", "v0")


def test_export_rejects_model_trained_on_numpy_array(tmp_path):
    export = _load_exporter()
    arr_model = make_pipeline(StandardScaler(), LogisticRegression()).fit(np.random.rand(50, 2), np.random.randint(0, 2, 50))
    with pytest.raises(ValueError, match="DataFrame"):
        export(arr_model, ["f1", "f2"], tmp_path, "m", "v0")
