from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timestamps are stored as naive UTC so SQLite and PostgreSQL behave the same."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(100))
    record_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    model_version: Mapped[str] = mapped_column(String(64))


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_motor_id", "motor_id"),
        Index("ix_predictions_created_at", "created_at"),
        Index("ix_predictions_measured_at", "measured_at"),
        Index("ix_predictions_batch_id", "batch_id"),
        Index("ix_predictions_motor_created", "motor_id", "created_at"),
        Index("ix_predictions_idempotency_key", "idempotency_key", unique=True),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(10))                       # "single" or "csv"
    record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    motor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    measured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    predicted_condition: Mapped[str] = mapped_column(String(64))
    predicted_class_id: Mapped[int] = mapped_column(Integer)
    scores: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(64))
    provisional_label_provenance: Mapped[bool] = mapped_column(Boolean)
    demonstration_only: Mapped[bool] = mapped_column(Boolean)
    input_readings: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # only if STORE_INPUT_READINGS=true
    # --- added in migration 0002 (manual assessments and recommendations) ---
    equipment_description: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)      # free text, NOT a verified identity
    recommendation_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ruleset_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    recommendations: Mapped[dict | None] = mapped_column(JSON, nullable=True)       # full recommendations as shown (manual assessments)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ---------- maintenance follow-up and e-mailed reports (migration 0003) ----------
# These tables only REFER to a prediction. They never change it, so the original assessment is always kept as first recorded.
class MaintenanceCase(Base):
    __tablename__ = "maintenance_cases"
    __table_args__ = (Index("ix_maintenance_cases_status", "status"), Index("ix_maintenance_cases_motor_id", "motor_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)    # the ORIGINAL assessment
    motor_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MaintenanceUpdate(Base):
    """Append-only log: every status change, note and reassessment link is its own row, so nothing is overwritten."""
    __tablename__ = "maintenance_updates"
    __table_args__ = (Index("ix_maintenance_updates_case_id", "case_id"), Index("ix_maintenance_updates_reassessment", "reassessment_assessment_id", unique=True))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("maintenance_cases.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    kind: Mapped[str] = mapped_column(String(16))                        # "opened", "update" or "reassessment"
    from_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    to_status: Mapped[str] = mapped_column(String(48))
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)           # free text, NOT a verified identity
    responsible_engineer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    fault_found: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    actions_performed: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    parts_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    verification_outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reassessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reassessment_assessment_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)


class ReportEmail(Base):
    """One attempt to e-mail an assessment report. 'sent' means the mail server ACCEPTED the message, not that it reached an inbox."""
    __tablename__ = "report_emails"
    __table_args__ = (Index("ix_report_emails_assessment_id", "assessment_id"), Index("ix_report_emails_created_at", "created_at"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"))
    recipient: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(10))                     # "sent" or "failed"
    error_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)   # short reason, never credentials
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
