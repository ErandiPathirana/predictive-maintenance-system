from datetime import timezone

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import api_key_guard, get_db, get_settings_dep, get_site_guidance, require_bundle
from app.core.config import Settings
from app.db import repository as repo
from app.schemas import (BatchPredictionResponse, CsvValidationReport, ErrorResponse, PredictionResult, SinglePredictionRequest, ValidationIssue)
from app.services.artifacts import LoadedBundle
from app.services.assessments import summaries_for
from app.services.csv_io import analyse_csv, parse_csv_or_raise, read_upload, safe_filename
from app.services.predictions import is_demonstration, result_dicts, score_matrix, validate_single_readings
from app.services.recommendations import RULESET_VERSION

router = APIRouter(prefix="/api", dependencies=[Depends(api_key_guard)])
_ERR = {422: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


@router.post("/uploads/validate", response_model=CsvValidationReport, responses=_ERR, tags=["Upload"],
             summary="Check a CSV file without predicting or storing anything")
async def validate_upload(file: UploadFile = File(..., description="A .csv file with the columns from GET /api/template.csv"),
                          bundle: LoadedBundle = Depends(require_bundle), settings: Settings = Depends(get_settings_dep)):
    raw = await read_upload(file, settings.max_upload_bytes)
    a = await run_in_threadpool(analyse_csv, raw, bundle, settings.max_batch_rows)
    return CsvValidationReport(valid=a.valid, record_count=a.record_count, columns_found=a.columns_found, ignored_columns=a.ignored_columns,
                               issues_total=a.issues_total, issues=[ValidationIssue(**i) for i in a.issues])


@router.post("/predict", response_model=PredictionResult, responses=_ERR, tags=["Prediction"],
             summary="Predict the condition class for ONE set of sensor readings")
def predict_one(body: SinglePredictionRequest, bundle: LoadedBundle = Depends(require_bundle),
                settings: Settings = Depends(get_settings_dep), site=Depends(get_site_guidance), db: Session = Depends(get_db)):
    X = validate_single_readings(body.readings, bundle)       # raises before any prediction if invalid
    scores = score_matrix(bundle, X)
    measured = body.measured_at.astimezone(timezone.utc).replace(tzinfo=None) if body.measured_at and body.measured_at.tzinfo else body.measured_at
    try:
        rows = repo.create_predictions(db, source="single", batch_id=None, bundle=bundle, demonstration=is_demonstration(bundle, settings),
                                       scores=scores, X=X, record_ids=[body.record_id], motor_ids=[body.motor_id], measured_at=[measured],
                                       store_inputs=settings.store_input_readings, recommendation_summaries=summaries_for(bundle, scores, X, site),
                                       ruleset_version=RULESET_VERSION)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return PredictionResult(**result_dicts(bundle, settings, scores, X, [body.record_id], [body.motor_id], [measured], [rows[0].id])[0])


def _process_batch(raw: bytes, filename: str, bundle: LoadedBundle, settings: Settings, db: Session, site=None) -> BatchPredictionResponse:
    a = parse_csv_or_raise(raw, bundle, settings.max_batch_rows)   # all-or-nothing: any problem stops everything
    scores = score_matrix(bundle, a.X)
    demo = is_demonstration(bundle, settings)
    try:
        batch = repo.create_batch(db, filename, len(a.record_ids), bundle.version)
        rows = repo.create_predictions(db, source="csv", batch_id=batch.id, bundle=bundle, demonstration=demo, scores=scores, X=a.X,
                                       record_ids=a.record_ids, motor_ids=a.motor_ids, measured_at=a.measured_at,
                                       store_inputs=settings.store_input_readings, recommendation_summaries=summaries_for(bundle, scores, a.X, site),
                                       ruleset_version=RULESET_VERSION)
        db.commit()
    except Exception:
        db.rollback()
        raise
    results = result_dicts(bundle, settings, scores, a.X, a.record_ids, a.motor_ids, a.measured_at, [r.id for r in rows])
    counts = {c: 0 for c in bundle.class_names}
    for r in results:
        counts[r["predicted_condition"]] += 1
    return BatchPredictionResponse(batch_id=batch.id, filename=filename, record_count=len(results), class_counts=counts,
                                   model_version=bundle.version, provisional_label_provenance=bundle.provisional,
                                   demonstration_only=demo, results=[PredictionResult(**r) for r in results])


@router.post("/predict/batch", response_model=BatchPredictionResponse, responses=_ERR, tags=["Prediction"],
             summary="Predict the condition class for every record in an uploaded CSV")
async def predict_batch(file: UploadFile = File(..., description="A .csv file with the columns from GET /api/template.csv"),
                        bundle: LoadedBundle = Depends(require_bundle), settings: Settings = Depends(get_settings_dep),
                        site=Depends(get_site_guidance), db: Session = Depends(get_db)):
    raw = await read_upload(file, settings.max_upload_bytes)
    return await run_in_threadpool(_process_batch, raw, safe_filename(file.filename), bundle, settings, db, site)
