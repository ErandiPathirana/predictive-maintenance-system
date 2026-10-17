"""Every request and response shape of the API."""

from datetime import date, datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

ID_PATTERN = r"^[A-Za-z0-9._\-]{1,64}$"
INTERPRETATION_NOTE = (
    "Predicted condition class from a statistical model. It is NOT a confirmed machine failure, "
    "and the scores are model outputs, not calibrated probabilities."
)


# ---------- inputs ----------
class SinglePredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str | None = Field(default=None, pattern=ID_PATTERN, description="Your own record reference (letters, digits, . _ -).")
    motor_id: str | None = Field(default=None, pattern=ID_PATTERN, description="Motor reference (letters, digits, . _ -).")
    measured_at: datetime | None = Field(default=None, description="When the reading was taken (ISO 8601). Stored for history only; not a model input.")
    readings: dict[str, Union[StrictInt, StrictFloat]] = Field(
        description="One numeric value per model input, keyed by feature name (see GET /api/features). Text and booleans are rejected.")


# ---------- results ----------
class InputWarning(BaseModel):
    feature: str
    value: float
    observed_train_min: float | None
    observed_train_max: float | None
    message: str


class PredictionResult(BaseModel):
    prediction_id: int | None = None
    record_id: str | None
    motor_id: str | None
    measured_at: datetime | None
    predicted_condition: str = Field(description="Predicted condition class. Not a confirmed failure.")
    predicted_class_id: int
    scores: dict[str, float] = Field(description="Model output score per class (sum to 1). Not calibrated probabilities.")
    scores_are_calibrated_probabilities: bool = False
    model_version: str
    provisional_label_provenance: bool
    demonstration_only: bool
    input_warnings: list[InputWarning] = []
    interpretation_note: str = INTERPRETATION_NOTE


class BatchPredictionResponse(BaseModel):
    batch_id: str
    filename: str
    record_count: int
    class_counts: dict[str, int]
    model_version: str
    provisional_label_provenance: bool
    demonstration_only: bool
    interpretation_note: str = INTERPRETATION_NOTE
    results: list[PredictionResult]


class ValidationIssue(BaseModel):
    row: int | None = Field(default=None, description="Line number in the file (header = line 1).")
    column: str | None = None
    problem: str


class CsvValidationReport(BaseModel):
    valid: bool
    record_count: int
    columns_found: list[str]
    ignored_columns: list[str]
    issues_total: int
    issues: list[ValidationIssue]
    note: str = "Dry run: nothing was predicted or stored."


# ---------- history ----------
class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    batch_id: str | None
    source: str
    record_id: str | None
    motor_id: str | None
    measured_at: datetime | None
    created_at: datetime
    predicted_condition: str
    predicted_class_id: int
    scores: dict[str, float]
    model_version: str
    provisional_label_provenance: bool
    demonstration_only: bool


class PredictionPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[HistoryItem]


class BatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    record_count: int
    created_at: datetime
    model_version: str


class BatchList(BaseModel):
    items: list[BatchSummary]


# ---------- system ----------
class HealthResponse(BaseModel):
    status: str = Field(description="'ok' or 'degraded' (model or database unavailable).")
    app_name: str
    app_version: str
    environment: str
    model_ready: bool
    database: str


class ClassInfo(BaseModel):
    id: int
    name: str


class FeatureInfo(BaseModel):
    name: str
    unit: str | None = None
    description: str | None = None
    observed_train_min: float | None = None
    observed_train_max: float | None = None


class FeatureListResponse(BaseModel):
    features: list[FeatureInfo]
    note: str = "observed_train_min/max describe the training data only. They are NOT validity limits or alarm thresholds."


class BundleInfo(BaseModel):
    model_name: str
    bundle_version: str
    task: str | None
    classes: list[ClassInfo]
    feature_count: int
    features: list[str]
    created_utc: str | None
    label_provenance_documented: bool
    provisional_label_provenance: bool
    demonstration_only: bool
    deployable_for_decisions: bool
    scores_are_calibrated_probabilities: bool = False
    future_failure_prediction_supported: bool
    smoke_test_bundle: bool
    reported_test_metrics: dict[str, Any] | None = None
    notes: list[str]


class ModelInfoResponse(BaseModel):
    model_ready: bool
    reason: str | None = None
    bundle: BundleInfo | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
