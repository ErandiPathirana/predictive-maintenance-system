"""Request and response shapes for report e-mails and maintenance follow-up."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

from app.schemas import MAX_READINGS, ID_PATTERN  # noqa: F401  (ID_PATTERN re-exported for tests)


def clean_text(v: str | None) -> str | None:
    """Trims. Line breaks and tabs are allowed in notes; other control characters are not."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if any((ord(c) < 32 and c not in "\n\r\t") or ord(c) == 127 for c in v):
        raise ValueError("Must not contain control characters.")
    return v


class EmailStatus(BaseModel):
    configured: bool = Field(description="False until the administrator sets SMTP_HOST and SMTP_FROM.")
    recipients_restricted: bool = Field(description="True when only recipients at approved domains are accepted.")
    link_in_report: bool = Field(description="True when the report contains a link to the assessment.")
    max_per_hour: int


class EmailReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(max_length=254, description="One e-mail address.")
    note: str | None = Field(default=None, max_length=500, description="Optional note from the sender.")
    readings: dict[str, StrictInt | StrictFloat] | None = Field(
        default=None, max_length=MAX_READINGS,
        description="Only needed when the server does not store readings. They are checked against the saved result and are NOT stored.")

    @field_validator("recipient")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("note")
    @classmethod
    def _note(cls, v):
        return clean_text(v)


class EmailReportResponse(BaseModel):
    sent: bool
    assessment_id: int
    reference: str
    recipient: str
    sent_at: datetime
    readings_included: bool
    message: str


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipient: str
    status: str
    error_summary: str | None = None
    created_at: datetime


class MaintenanceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_status: Literal["pending_inspection", "maintenance_in_progress", "repair_completed_verification_required", "verified_closed"]
    updated_by: str | None = Field(default=None, max_length=64, description="Free text. NOT a verified identity: there is no login.")
    responsible_engineer: str | None = Field(default=None, max_length=64)
    started_on: date | None = None
    completed_on: date | None = None
    fault_found: str | None = Field(default=None, max_length=1000)
    actions_performed: str | None = Field(default=None, max_length=1000)
    parts_notes: str | None = Field(default=None, max_length=500)
    comment: str | None = Field(default=None, max_length=1000)
    verification_outcome: Literal["verified", "not_verified"] | None = None
    reassessment_date: date | None = None

    @field_validator("updated_by", "responsible_engineer", "fault_found", "actions_performed", "parts_notes", "comment")
    @classmethod
    def _text(cls, v):
        return clean_text(v)


class ReassessmentLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: int = Field(ge=1, le=2**63 - 1)
    reassessment_date: date | None = None


class MaintenanceUpdateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    kind: str
    from_status: str | None
    to_status: str
    updated_by: str | None
    responsible_engineer: str | None
    started_on: date | None
    completed_on: date | None
    fault_found: str | None
    actions_performed: str | None
    parts_notes: str | None
    comment: str | None
    verification_outcome: str | None
    reassessment_date: date | None
    reassessment_assessment_id: int | None


class ReassessmentOut(BaseModel):
    assessment_id: int
    created_at: datetime
    measured_at: datetime | None
    predicted_condition: str
    scores: dict[str, float]
    readings: dict[str, float] | None = Field(default=None, description="Only when the server stores readings.")


class MaintenanceCaseOut(BaseModel):
    id: int
    reference: str
    assessment_id: int
    assessment_reference: str
    motor_id: str
    status: str
    status_label: str
    created_at: datetime
    updated_at: datetime
    allowed_next_statuses: list[str]
    updates: list[MaintenanceUpdateOut]
    reassessments: list[ReassessmentOut]


class MaintenanceDetail(BaseModel):
    assessment_id: int
    predicted_condition: str
    eligible: bool = Field(description="True when a follow-up case can be opened (Alert or Danger, with a motor ID, and none yet).")
    reason: str | None = Field(default=None, description="Why a case cannot be opened, when eligible is false and there is no case.")
    case: MaintenanceCaseOut | None = None
    emails: list[EmailLogOut] = []
    follows_assessment_id: int | None = Field(default=None, description="Set when this assessment is a reassessment linked to an earlier case.")
    follows_case_id: int | None = None
