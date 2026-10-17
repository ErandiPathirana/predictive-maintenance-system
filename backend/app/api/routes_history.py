import csv
import io
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import api_key_guard, get_db, get_registry, get_settings_dep
from app.core.config import Settings
from app.core.errors import BadQueryError, NotFoundError
from app.db import repository as repo
from app.db.models import Prediction
from app.schemas import BatchList, BatchSummary, ErrorResponse, HistoryItem, INTERPRETATION_NOTE, PredictionPage
from app.services.artifacts import ModelRegistry

router = APIRouter(prefix="/api", dependencies=[Depends(api_key_guard)])
_ID = {"max_length": 64}


def history_filters(
    motor_id: str | None = Query(None, max_length=64, description="Exact motor ID"),
    record_id: str | None = Query(None, max_length=64),
    batch_id: str | None = Query(None, max_length=36, description="Upload batch ID returned by /api/predict/batch"),
    predicted_condition: str | None = Query(None, max_length=64, description="e.g. Alert"),
    date_from: date | None = Query(None, description="Predictions made on/after this UTC date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Predictions made on/before this UTC date (inclusive)"),
    measured_from: date | None = Query(None, description="Readings measured on/after this date"),
    measured_to: date | None = Query(None, description="Readings measured on/before this date (inclusive)"),
) -> repo.PredictionFilters:
    if date_from and date_to and date_from > date_to:
        raise BadQueryError("date_from must not be after date_to.")
    if measured_from and measured_to and measured_from > measured_to:
        raise BadQueryError("measured_from must not be after measured_to.")
    return repo.PredictionFilters(motor_id, record_id, batch_id, predicted_condition, date_from, date_to, measured_from, measured_to)


@router.get("/predictions", response_model=PredictionPage, responses={422: {"model": ErrorResponse}}, tags=["History"],
            summary="Prediction history (newest first), filter by motor, batch, class or date")
def list_predictions(f: repo.PredictionFilters = Depends(history_filters), limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db)):
    total, rows = repo.query_page(db, f, limit, offset)
    return PredictionPage(total=total, limit=limit, offset=offset, items=[HistoryItem.model_validate(r) for r in rows])


@router.get("/predictions/{prediction_id}", response_model=HistoryItem, responses={404: {"model": ErrorResponse}}, tags=["History"],
            summary="One stored prediction")
def get_one(prediction_id: int, db: Session = Depends(get_db)):
    row = repo.get_prediction(db, prediction_id)
    if row is None:
        raise NotFoundError("No prediction with that ID.")
    return HistoryItem.model_validate(row)


@router.get("/batches", response_model=BatchList, tags=["History"], summary="Recent CSV upload batches")
def batches(db: Session = Depends(get_db)):
    return BatchList(items=[BatchSummary.model_validate(b) for b in repo.list_batches(db)])


def _safe_cell(value):
    """Prevents spreadsheet formula injection: text starting with = + - @ is prefixed with an apostrophe."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def build_report_csv(rows: list[Prediction]) -> str:
    class_cols: list[str] = []
    for r in rows:
        for c in r.scores:
            if c not in class_cols:
                class_cols.append(c)
    header = ["prediction_id", "batch_id", "source", "record_id", "motor_id", "measured_at", "predicted_at_utc", "predicted_condition",
              "predicted_class_id", *[f"model_score_{c}" for c in class_cols], "model_version", "label_provenance_provisional",
              "demonstration_only", "equipment_description", "recorded_by_unverified", "recommendation_summary", "recommendation_ruleset", "note"]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(header)
    for r in rows:
        w.writerow([r.id, r.batch_id or "", r.source, _safe_cell(r.record_id or ""), _safe_cell(r.motor_id or ""),
                    r.measured_at.isoformat(sep=" ") if r.measured_at else "", r.created_at.isoformat(sep=" ", timespec="seconds"),
                    r.predicted_condition, r.predicted_class_id, *[f"{r.scores.get(c, ''):.6f}" if c in r.scores else "" for c in class_cols],
                    r.model_version, r.provisional_label_provenance, r.demonstration_only, _safe_cell(r.equipment_description or ""),
                    _safe_cell(r.recorded_by or ""), _safe_cell(r.recommendation_summary or ""), r.ruleset_version or "", INTERPRETATION_NOTE])
    return out.getvalue()


@router.get("/reports/predictions.csv", tags=["History"], summary="Export prediction results to CSV (same filters as the history)",
            responses={200: {"content": {"text/csv": {}}}, 422: {"model": ErrorResponse}})
def export_csv(f: repo.PredictionFilters = Depends(history_filters), db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    total, rows = repo.query_for_export(db, f, settings.max_export_rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Response(build_report_csv(rows), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="predictions_{stamp}.csv"',
        "X-Total-Matching": str(total), "X-Rows-Exported": str(len(rows)), "X-Export-Truncated": str(total > len(rows)).lower()})
