"""Every request and response shape of the API."""

from datetime import date, datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

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


def _no_control_chars(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in v):
        raise ValueError("Must not contain control characters or line breaks.")
    return v


class AssessmentRequest(BaseModel):
    """A manual motor assessment. The same strict checks and preprocessing as CSV rows are applied to `readings`."""
    model_config = ConfigDict(extra="forbid")
    motor_id: str = Field(pattern=ID_PATTERN, description="Motor reference (letters, digits, . _ -). New IDs are allowed if they match this pattern.")
    measured_at: datetime = Field(description="When the reading was taken (ISO 8601). Required for assessments.")
    equipment_description: str | None = Field(default=None, max_length=120, description="Optional name or description of the equipment.")
    recorded_by: str | None = Field(default=None, max_length=64, description="Optional free-text name or initials. NOT verified: the API has no user login.")
    readings: dict[str, Union[StrictInt, StrictFloat]] = Field(
        description="One numeric value per model input, keyed by feature name (see GET /api/features). Text, booleans, NaN and infinity are rejected.")

    @field_validator("equipment_description", "recorded_by")
    @classmethod
    def _clean_text(cls, v):
        return _no_control_chars(v)

    @field_validator("measured_at", mode="before")
    @classmethod
    def _timestamp_must_be_text(cls, v):
        # Pydantic would otherwise read a bare number as a Unix timestamp; a typo such as 12345.5 must not become a date.
        if not isinstance(v, str):
            raise ValueError("measured_at must be a date-time text such as 2025-04-01T07:20:00")
        return v


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
    equipment_description: str | None = None
    recorded_by: str | None = Field(default=None, description="Free text typed by the user. NOT a verified identity.")
    recommendation_summary: str | None = None
    ruleset_version: str | None = None
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


# ---------- assessments and recommendations ----------
class RecommendationItem(BaseModel):
    priority: int
    action: str
    reason: str
    responsible_role: str
    timing: str = Field(description="Immediate safety review, Prompt engineering assessment, Planned maintenance review or Routine monitoring. No exact deadlines.")
    safety_note: str | None = None
    source: str = Field(description="'general_guidance' or 'site_approved'")
    source_detail: str
    requires_confirmation: bool


class RecommendationBlock(BaseModel):
    condition: str
    available: bool = Field(description="False when the model returned a class the rules do not cover. Nothing is invented then.")
    ruleset_version: str
    headline: str
    items: list[RecommendationItem]
    summary: str
    disclaimer: str
    threshold_note: str
    site_guidance_version: str | None = None
    urgent: bool
    return_to_service: list[str] = Field(description="Questions to settle before return to service. Not pass/fail criteria.")
    return_to_service_note: str | None = None


class AssessmentResponse(BaseModel):
    saved: bool = Field(description="True only after the database confirmed the save.")
    duplicate: bool = Field(description="True when this is a replay of an earlier submission with the same Idempotency-Key. Nothing new was saved.")
    assessment_id: int
    created_at: datetime
    motor_id: str | None
    equipment_description: str | None
    recorded_by: str | None
    recorded_by_verified: bool = False
    measured_at: datetime | None
    predicted_condition: str
    predicted_class_id: int
    scores: dict[str, float]
    scores_are_calibrated_probabilities: bool = False
    model_version: str
    provisional_label_provenance: bool
    demonstration_only: bool
    input_warnings: list[InputWarning] = []
    readings: dict[str, float] | None = Field(default=None, description="The validated readings. Returned on creation, and later only if the server stores readings.")
    readings_stored: bool
    recommendations: RecommendationBlock
    recommendations_regenerated: bool = Field(default=False, description="True when an older record had no stored recommendations and they were rebuilt from the stored condition.")
    interpretation_note: str = INTERPRETATION_NOTE


class MotorSummary(BaseModel):
    motor_id: str
    record_count: int
    last_measured_at: datetime | None


class MotorList(BaseModel):
    items: list[MotorSummary]
    note: str = "Motors seen in stored predictions. Other IDs are accepted if they match the allowed pattern."
