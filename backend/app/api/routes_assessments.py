"""Manual motor assessments (one set of readings), with recommendations, saved only after the database confirms."""
import logging
import re
from datetime import timezone

import numpy as np
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import api_key_guard, get_db, get_settings_dep, get_site_guidance, require_bundle
from app.core.config import Settings
from app.core.errors import BadQueryError, DatabaseUnavailableError, IdempotencyConflictError, NotFoundError
from app.db import repository as repo
from app.db.models import Prediction
from app.schemas import AssessmentRequest, AssessmentResponse, ErrorResponse, MotorList, MotorSummary
from app.services.artifacts import LoadedBundle
from app.services.assessments import recommendation_for, request_hash
from app.services.predictions import input_warnings, is_demonstration, score_matrix, validate_single_readings
from app.services.recommendations import recommend

router = APIRouter(prefix="/api", dependencies=[Depends(api_key_guard)])
log = logging.getLogger("app.assessments")
_KEY = re.compile(r"^[A-Za-z0-9._\-]{8,64}$")
_ERR = {422: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


def _stored_warnings(row: Prediction, bundle: LoadedBundle) -> list[dict]:
    """Out-of-training-range notices can be rebuilt only when the readings were stored with the record."""
    stored = row.input_readings
    if not stored or not set(bundle.feature_names) <= set(stored):
        return []
    return input_warnings(bundle, np.array([stored[n] for n in bundle.feature_names], dtype="float64"))


def _response(row: Prediction, *, duplicate: bool, bundle: LoadedBundle, site, readings: dict | None = None,
              warnings: list[dict] | None = None) -> AssessmentResponse:
    rec, regenerated = row.recommendations, False
    if rec is None:                                   # older record or CSV row: rebuild from the stored condition (flagged as regenerated)
        rec, regenerated = recommend(row.predicted_condition, (), site).to_dict(), True
    return AssessmentResponse(
        saved=True, duplicate=duplicate, assessment_id=row.id, created_at=row.created_at, motor_id=row.motor_id,
        equipment_description=row.equipment_description, recorded_by=row.recorded_by, measured_at=row.measured_at,
        predicted_condition=row.predicted_condition, predicted_class_id=row.predicted_class_id, scores=row.scores,
        model_version=row.model_version, provisional_label_provenance=row.provisional_label_provenance, demonstration_only=row.demonstration_only,
        input_warnings=warnings if warnings is not None else _stored_warnings(row, bundle),
        readings=readings if readings is not None else row.input_readings, readings_stored=row.input_readings is not None,
        recommendations=rec, recommendations_regenerated=regenerated)


@router.post("/assessments", response_model=AssessmentResponse, status_code=201, responses={**_ERR, 200: {"model": AssessmentResponse}}, tags=["Assessment"],
             summary="Assess ONE motor from manually entered readings, get recommendations, and save the result")
def create_assessment(body: AssessmentRequest, response: Response,
                      idempotency_key: str | None = Header(default=None, alias="Idempotency-Key",
                                                           description="8-64 characters. Send the same key when retrying the same form, so it is saved once."),
                      bundle: LoadedBundle = Depends(require_bundle), settings: Settings = Depends(get_settings_dep),
                      site=Depends(get_site_guidance), db: Session = Depends(get_db)):
    if idempotency_key is not None and not _KEY.match(idempotency_key):
        raise BadQueryError("Idempotency-Key must be 8 to 64 characters: letters, digits, '.', '_' or '-'.")
    fingerprint = request_hash(body.model_dump(mode="json"))

    def replay(existing: Prediction) -> AssessmentResponse:
        if existing.request_hash != fingerprint:
            raise IdempotencyConflictError("This Idempotency-Key was already used for different readings. Start a new assessment to get a new key.")
        response.status_code = 200
        return _response(existing, duplicate=True, bundle=bundle, site=site)

    if idempotency_key:
        found = repo.find_by_idempotency_key(db, idempotency_key)
        if found is not None:
            return replay(found)

    X = validate_single_readings(body.readings, bundle)          # raises before any prediction if anything is missing or non-finite
    scores = score_matrix(bundle, X)
    condition = bundle.class_names[int(scores[0].argmax())]      # class NAME comes from the model's own class mapping
    recs = recommendation_for(bundle, condition, X[0], site).to_dict()
    measured = body.measured_at.astimezone(timezone.utc).replace(tzinfo=None) if body.measured_at.tzinfo else body.measured_at
    try:
        row = repo.create_assessment(db, bundle=bundle, demonstration=is_demonstration(bundle, settings), scores=scores, X=X, motor_id=body.motor_id,
                                     measured_at=measured, equipment_description=body.equipment_description, recorded_by=body.recorded_by,
                                     recommendations=recs, idempotency_key=idempotency_key, request_hash=fingerprint, store_inputs=settings.store_input_readings)
        db.commit()
    except IntegrityError:
        db.rollback()
        found = repo.find_by_idempotency_key(db, idempotency_key) if idempotency_key else None
        if found is not None:                                    # two identical submissions raced: the first one won
            return replay(found)
        log.error("Assessment not saved: integrity error")
        raise DatabaseUnavailableError("The assessment could not be saved, so nothing was recorded. Please try again.")
    except SQLAlchemyError:
        db.rollback()
        log.error("Assessment not saved: database error")
        raise DatabaseUnavailableError("The assessment could not be saved, so nothing was recorded. Please try again.")
    log.info("Assessment %s saved: motor=%s condition=%s model=%s", row.id, row.motor_id, row.predicted_condition, row.model_version)   # no readings in logs
    return _response(row, duplicate=False, bundle=bundle, site=site, readings={n: float(v) for n, v in zip(bundle.feature_names, X[0])},
                     warnings=input_warnings(bundle, X[0]))


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse, responses={404: {"model": ErrorResponse}}, tags=["Assessment"],
            summary="One stored assessment with its recommendations")
def get_assessment(assessment_id: int, bundle: LoadedBundle = Depends(require_bundle), site=Depends(get_site_guidance), db: Session = Depends(get_db)):
    row = repo.get_prediction(db, assessment_id)
    if row is None:
        raise NotFoundError("No assessment with that ID.")
    return _response(row, duplicate=False, bundle=bundle, site=site)


@router.get("/motors", response_model=MotorList, tags=["Assessment"], summary="Motor IDs seen in stored predictions")
def list_motors(db: Session = Depends(get_db)):
    return MotorList(items=[MotorSummary(**m) for m in repo.motor_summaries(db)])
