"""Shared test fixtures.

IMPORTANT: the model built here is trained on RANDOM numbers. It exists only to
test that the code (loading, validation, prediction, errors) works. Its output
means nothing and must never be reported as a research result.
"""

import json

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.config import Settings
from app.main import create_app

FEATURES = [
    {"name": "sensor_a", "unit": "unit_a", "min": 0, "max": 100},
    {"name": "sensor_b", "unit": "unit_b"},  # no range given
]


def _settings(model_dir) -> Settings:
    return Settings(model_dir=model_dir, cors_origins="http://localhost:5173")


@pytest.fixture
def client_without_model(tmp_path):
    """App started with an empty artifacts folder."""
    with TestClient(create_app(_settings(tmp_path))) as client:
        yield client


@pytest.fixture
def model_dir(tmp_path):
    """A folder containing a tiny, meaningless-but-valid set of artifacts."""
    rng = np.random.default_rng(0)
    x = pd.DataFrame(rng.uniform(0, 100, size=(200, 2)), columns=[f["name"] for f in FEATURES])
    y = (x["sensor_a"] + rng.normal(0, 10, 200) > 50).astype(int)
    model = make_pipeline(StandardScaler(), LogisticRegression()).fit(x, y)

    joblib.dump(model, tmp_path / "model.joblib")
    (tmp_path / "feature_schema.json").write_text(json.dumps({"features": FEATURES}))
    (tmp_path / "model_metadata.json").write_text(
        json.dumps({"model_name": "test-model", "model_version": "0.0.test", "positive_class": 1, "decision_threshold": 0.5})
    )
    return tmp_path


@pytest.fixture
def client(model_dir):
    with TestClient(create_app(_settings(model_dir))) as client:
        yield client
