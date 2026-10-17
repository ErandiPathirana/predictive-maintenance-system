"""Turns validated numeric inputs into structured prediction results."""

import math
from datetime import datetime

import numpy as np

from app.core.errors import InputValidationError, PredictionError
from app.services.artifacts import LoadedBundle
from app.services.inference import forward


def is_demonstration(bundle: LoadedBundle, settings) -> bool:
    """Flag results as a demonstration when labels are unverified or the bundle is a smoke test.
    (The bundle contract has no 'data is synthetic' field, so an operator can force it with FORCE_DEMONSTRATION_BANNER.)"""
    if settings.force_demonstration_banner is not None:
        return settings.force_demonstration_banner
    return bundle.provisional or bundle.fast_debug


def validate_single_readings(readings: dict[str, float], bundle: LoadedBundle) -> np.ndarray:
    expected, provided = set(bundle.feature_names), set(readings)
    missing, unknown = sorted(expected - provided), sorted(provided - expected)
    non_finite = sorted(n for n, v in readings.items() if not math.isfinite(float(v)))
    if missing or unknown or non_finite:
        details = {"missing_features": missing, "unknown_features": unknown, "non_finite_values": non_finite}
        raise InputValidationError("Some sensor readings are missing or invalid. No prediction was made.", {k: v for k, v in details.items() if v})
    return np.array([[float(readings[n]) for n in bundle.feature_names]], dtype="float64")


def input_warnings(bundle: LoadedBundle, x_row: np.ndarray) -> list[dict]:
    """Non-blocking notice when a value lies outside the range seen in TRAINING (extrapolation).
    This is not an engineering limit or alarm threshold."""
    out = []
    for name, v in zip(bundle.feature_names, x_row):
        lo, hi = bundle.observed_ranges.get(name, (None, None))
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            out.append({"feature": name, "value": float(v), "observed_train_min": lo, "observed_train_max": hi,
                        "message": "Outside the range seen during training: the model is extrapolating and may be unreliable."})
    return out


def score_matrix(bundle: LoadedBundle, X: np.ndarray) -> np.ndarray:
    scores = forward(bundle, X)
    if not np.isfinite(scores).all():
        raise PredictionError("The model produced an invalid score. No prediction was made.")
    return scores


def result_dicts(bundle: LoadedBundle, settings, scores: np.ndarray, X: np.ndarray, record_ids, motor_ids,
                 measured_at: list[datetime | None], prediction_ids: list[int | None]) -> list[dict]:
    demo = is_demonstration(bundle, settings)
    out = []
    for i in range(len(scores)):
        k = int(scores[i].argmax())
        out.append({
            "prediction_id": prediction_ids[i], "record_id": record_ids[i], "motor_id": motor_ids[i], "measured_at": measured_at[i],
            "predicted_condition": bundle.class_names[k], "predicted_class_id": k,
            "scores": {c: float(s) for c, s in zip(bundle.class_names, scores[i])},
            "scores_are_calibrated_probabilities": False, "model_version": bundle.version,
            "provisional_label_provenance": bundle.provisional, "demonstration_only": demo,
            "input_warnings": input_warnings(bundle, X[i]),
        })
    return out
