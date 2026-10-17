"""All database reads and writes live here, so the routes stay thin."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Prediction, UploadBatch


@dataclass
class PredictionFilters:
    motor_id: str | None = None
    record_id: str | None = None
    batch_id: str | None = None
    predicted_condition: str | None = None
    date_from: date | None = None        # prediction time (UTC date), inclusive
    date_to: date | None = None
    measured_from: date | None = None    # measurement time, inclusive
    measured_to: date | None = None


def _conditions(f: PredictionFilters) -> list:
    c = []
    if f.motor_id: c.append(Prediction.motor_id == f.motor_id)
    if f.record_id: c.append(Prediction.record_id == f.record_id)
    if f.batch_id: c.append(Prediction.batch_id == f.batch_id)
    if f.predicted_condition: c.append(Prediction.predicted_condition == f.predicted_condition)
    if f.date_from: c.append(Prediction.created_at >= datetime.combine(f.date_from, time.min))
    if f.date_to: c.append(Prediction.created_at < datetime.combine(f.date_to + timedelta(days=1), time.min))
    if f.measured_from: c.append(Prediction.measured_at >= datetime.combine(f.measured_from, time.min))
    if f.measured_to: c.append(Prediction.measured_at < datetime.combine(f.measured_to + timedelta(days=1), time.min))
    return c


def create_batch(session: Session, filename: str, count: int, model_version: str) -> UploadBatch:
    batch = UploadBatch(id=str(uuid.uuid4()), filename=filename, record_count=count, model_version=model_version)
    session.add(batch)
    return batch


def create_predictions(session: Session, *, source: str, batch_id: str | None, bundle, demonstration: bool, scores: np.ndarray,
                       X: np.ndarray, record_ids, motor_ids, measured_at, store_inputs: bool) -> list[Prediction]:
    rows = []
    for i in range(len(scores)):
        k = int(scores[i].argmax())
        rows.append(Prediction(
            batch_id=batch_id, source=source, record_id=record_ids[i], motor_id=motor_ids[i], measured_at=measured_at[i],
            predicted_condition=bundle.class_names[k], predicted_class_id=k,
            scores={c: float(s) for c, s in zip(bundle.class_names, scores[i])}, model_version=bundle.version,
            provisional_label_provenance=bundle.provisional, demonstration_only=demonstration,
            input_readings={n: float(v) for n, v in zip(bundle.feature_names, X[i])} if store_inputs else None))
    session.add_all(rows)
    session.flush()          # assigns primary keys
    return rows


def query_page(session: Session, f: PredictionFilters, limit: int, offset: int) -> tuple[int, list[Prediction]]:
    cond = _conditions(f)
    total = session.scalar(select(func.count()).select_from(Prediction).where(*cond)) or 0
    rows = session.scalars(select(Prediction).where(*cond).order_by(Prediction.id.desc()).limit(limit).offset(offset)).all()
    return total, list(rows)


def query_for_export(session: Session, f: PredictionFilters, limit: int) -> tuple[int, list[Prediction]]:
    cond = _conditions(f)
    total = session.scalar(select(func.count()).select_from(Prediction).where(*cond)) or 0
    rows = session.scalars(select(Prediction).where(*cond).order_by(Prediction.id.asc()).limit(limit)).all()
    return total, list(rows)


def get_prediction(session: Session, prediction_id: int) -> Prediction | None:
    return session.get(Prediction, prediction_id)


def list_batches(session: Session, limit: int = 100) -> list[UploadBatch]:
    return list(session.scalars(select(UploadBatch).order_by(UploadBatch.created_at.desc()).limit(limit)).all())
