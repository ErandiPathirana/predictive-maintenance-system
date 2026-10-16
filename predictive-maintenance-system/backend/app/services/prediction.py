"""Runs the model and converts its output into an API response."""

import numpy as np

from app.errors import ModelNotReadyError, PredictionError
from app.schemas import PredictionRequest, PredictionResponse
from app.services.data_validation import validate_readings
from app.services.model_loader import ModelRegistry
from app.services.preprocessing import build_feature_frame


def predict_failure(registry: ModelRegistry, request: PredictionRequest) -> PredictionResponse:
    if not registry.is_ready:
        raise ModelNotReadyError(registry.not_ready_reason or "Model is not ready.")

    model, schema, metadata = registry.model, registry.schema, registry.metadata
    validate_readings(request.readings, schema)
    frame = build_feature_frame(request.readings, schema)

    try:
        classes = list(model.classes_) if hasattr(model, "classes_") else [0, 1]
        if metadata.positive_class not in classes:
            raise PredictionError(
                f"positive_class {metadata.positive_class!r} is not one of the model's classes {classes}."
            )
        positive_index = classes.index(metadata.positive_class)
        probability = float(model.predict_proba(frame)[0][positive_index])

        if metadata.decision_threshold is not None:
            predicted_failure = probability >= metadata.decision_threshold
        else:
            predicted_failure = bool(model.predict(frame)[0] == metadata.positive_class)
    except PredictionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PredictionError(f"The model could not score this input: {type(exc).__name__}.") from exc

    if not np.isfinite(probability):
        raise PredictionError("The model returned an invalid probability.")

    return PredictionResponse(
        machine_id=request.machine_id,
        failure_probability=min(max(probability, 0.0), 1.0),
        predicted_failure=predicted_failure,
        decision_threshold=metadata.decision_threshold,
        model_name=metadata.model_name,
        model_version=metadata.model_version,
    )
