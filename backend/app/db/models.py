from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
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
