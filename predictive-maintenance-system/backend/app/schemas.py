"""Pydantic models: the shape of every request and response."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------- Feature schema (exported from Colab as feature_schema.json) ----------
class FeatureSpec(BaseModel):
    """One model input feature."""

    name: str = Field(min_length=1)
    description: str = ""
    unit: str | None = None
    # Valid ranges come from YOUR dataset / domain expert. They are optional:
    # leave them out if you do not have an evidence-based range.
    min: float | None = None
    max: float | None = None


class FeatureSchema(BaseModel):
    features: list[FeatureSpec] = Field(min_length=1)

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.features]


# ---------- Model metadata (exported from Colab as model_metadata.json) ----------
class ModelMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="allow")

    model_name: str = "unnamed-model"
    model_version: str = "unversioned"
    trained_at: datetime | None = None
    positive_class: int | str = 1  # the class label that means "failure"
    # Chosen by YOU on validation data in Colab. If absent, the model's own predict() is used.
    decision_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None


# ---------- API requests / responses ----------
class PredictionRequest(BaseModel):
    machine_id: str | None = Field(default=None, max_length=64, description="Optional label for display only.")
    readings: dict[str, float] = Field(description="Sensor readings keyed by feature name.")


class PredictionResponse(BaseModel):
    machine_id: str | None
    failure_probability: float = Field(ge=0.0, le=1.0)
    predicted_failure: bool
    decision_threshold: float | None
    model_name: str
    model_version: str


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    environment: str
    model_ready: bool


class ModelInfoResponse(BaseModel):
    model_ready: bool
    reason: str | None = None
    metadata: dict[str, Any] | None = None
    feature_count: int | None = None


class FeatureListResponse(BaseModel):
    features: list[FeatureSpec]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
