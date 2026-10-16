"""Unit tests for the individual service modules (no HTTP involved)."""

import json

import pytest

from app.config import Settings
from app.errors import InputValidationError
from app.schemas import FeatureSchema
from app.services.data_validation import validate_readings
from app.services.model_loader import ModelRegistry
from app.services.preprocessing import build_feature_frame

SCHEMA = FeatureSchema.model_validate(
    {"features": [{"name": "a", "min": 0, "max": 10}, {"name": "b"}]}
)


def test_valid_readings_pass():
    validate_readings({"a": 5, "b": -999}, SCHEMA)  # b has no range, so any finite value is fine


def test_all_problems_reported_together():
    with pytest.raises(InputValidationError) as info:
        validate_readings({"a": 50, "c": 1}, SCHEMA)
    d = info.value.details
    assert d["missing_features"] == ["b"]
    assert d["unknown_features"] == ["c"]
    assert d["out_of_range"][0]["feature"] == "a"


def test_nan_and_infinity_rejected():
    with pytest.raises(InputValidationError) as info:
        validate_readings({"a": float("nan"), "b": float("inf")}, SCHEMA)
    assert info.value.details["non_finite_values"] == ["a", "b"]


def test_boundary_values_are_allowed():
    validate_readings({"a": 0, "b": 0}, SCHEMA)
    validate_readings({"a": 10, "b": 0}, SCHEMA)


def test_frame_has_training_column_order():
    frame = build_feature_frame({"b": 2, "a": 1}, SCHEMA)  # dict order differs on purpose
    assert list(frame.columns) == ["a", "b"]
    assert frame.iloc[0].tolist() == [1.0, 2.0]


def test_registry_reports_missing_files(tmp_path):
    reg = ModelRegistry(Settings(model_dir=tmp_path))
    reg.load()
    assert reg.is_ready is False
    assert "model.joblib" in reg.not_ready_reason


def test_registry_survives_corrupt_model_file(model_dir):
    (model_dir / "model.joblib").write_bytes(b"not a real model")
    reg = ModelRegistry(Settings(model_dir=model_dir))
    reg.load()
    assert reg.is_ready is False
    assert "Could not load" in reg.not_ready_reason


def test_registry_survives_bad_schema(model_dir):
    (model_dir / "feature_schema.json").write_text(json.dumps({"features": []}))
    reg = ModelRegistry(Settings(model_dir=model_dir))
    reg.load()
    assert reg.is_ready is False


def test_registry_loads_good_artifacts(model_dir):
    reg = ModelRegistry(Settings(model_dir=model_dir))
    reg.load()
    assert reg.is_ready is True
    assert reg.not_ready_reason is None
