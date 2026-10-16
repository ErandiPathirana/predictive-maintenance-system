"""Checks sensor readings BEFORE they reach the model.

Rules (all driven by feature_schema.json, nothing hard-coded):
  1. Every feature the model needs must be present.
  2. No unknown features are allowed (catches typos).
  3. Values must be finite numbers (no NaN / infinity).
  4. If the schema gives a min and/or max, the value must be inside it.

All problems are collected and reported together, so the user can fix them in one go.
"""

import math

from app.errors import InputValidationError
from app.schemas import FeatureSchema


def validate_readings(readings: dict[str, float], schema: FeatureSchema) -> None:
    expected = set(schema.names)
    provided = set(readings)

    missing = sorted(expected - provided)
    unknown = sorted(provided - expected)
    not_finite = sorted(name for name, v in readings.items() if not math.isfinite(v))
    out_of_range: list[dict] = []

    for spec in schema.features:
        value = readings.get(spec.name)
        if value is None or not math.isfinite(value):
            continue
        too_low = spec.min is not None and value < spec.min
        too_high = spec.max is not None and value > spec.max
        if too_low or too_high:
            out_of_range.append({"feature": spec.name, "value": value, "min": spec.min, "max": spec.max})

    if missing or unknown or not_finite or out_of_range:
        details = {
            "missing_features": missing,
            "unknown_features": unknown,
            "non_finite_values": not_finite,
            "out_of_range": out_of_range,
        }
        # Keep the response compact: drop empty groups.
        details = {k: v for k, v in details.items() if v}
        raise InputValidationError("Some sensor readings are missing or invalid.", details)
