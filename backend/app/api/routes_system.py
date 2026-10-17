from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import api_key_guard, get_db, get_registry, get_settings_dep, require_bundle
from app.core.config import Settings
from app.schemas import (BundleInfo, ClassInfo, ErrorResponse, FeatureInfo, FeatureListResponse, HealthResponse, ModelInfoResponse)
from app.services.artifacts import LoadedBundle, ModelRegistry
from app.services.csv_io import OPTIONAL_COLUMNS, IDENTIFIER_COLUMNS
from app.services.predictions import is_demonstration

router = APIRouter(prefix="/api")
guarded = APIRouter(prefix="/api", dependencies=[Depends(api_key_guard)])


@router.get("/health", response_model=HealthResponse, tags=["System"], summary="Is the API running?")
def health(settings: Settings = Depends(get_settings_dep), registry: ModelRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001 - never leak driver errors
        db_status = "unavailable"
    ok = registry.is_ready and db_status == "ok"
    return HealthResponse(status="ok" if ok else "degraded", app_name=settings.app_name, app_version=settings.app_version,
                          environment=settings.environment, model_ready=registry.is_ready, database=db_status)


def _bundle_info(b: LoadedBundle, settings: Settings) -> BundleInfo:
    m = b.metadata
    ann = (m.get("test_metrics") or {}).get("ANN") or {}
    reported = {k: ann[k] for k in ("n", "accuracy", "balanced_accuracy", "macro_f1") if k in ann} or None
    demo = is_demonstration(b, settings)
    notes = ["Predicted condition class only. It is NOT a confirmed machine failure.",
             "Scores are model outputs, not calibrated probabilities (calibration was not evaluated)."]
    if b.provisional:
        notes.append("Label provenance is NOT documented: results describe agreement with an unverified label.")
    if b.fast_debug:
        notes.append("This is a smoke-test bundle. Its results are invalid.")
    if demo:
        notes.append("DEMONSTRATION: do not use for operational decisions.")
    if reported:
        notes.append("reported_test_metrics come from the training notebook (held-out motors); see the model card.")
    return BundleInfo(
        model_name=b.model_name, bundle_version=b.version, task=m.get("task"),
        classes=[ClassInfo(id=i, name=n) for i, n in enumerate(b.class_names)], feature_count=b.n_features, features=b.feature_names,
        created_utc=m.get("created_utc"), label_provenance_documented=not b.provisional, provisional_label_provenance=b.provisional,
        demonstration_only=demo, deployable_for_decisions=bool(m.get("deployable_for_decisions", False)),
        future_failure_prediction_supported=bool(m.get("option_b_future_failure_prediction_supported", False)),
        smoke_test_bundle=b.fast_debug, reported_test_metrics=reported, notes=notes)


@guarded.get("/model-info", response_model=ModelInfoResponse, tags=["System"], summary="Describe the loaded model bundle")
def model_info(registry: ModelRegistry = Depends(get_registry), settings: Settings = Depends(get_settings_dep)):
    if not registry.is_ready:
        return ModelInfoResponse(model_ready=False, reason=registry.public_reason)
    return ModelInfoResponse(model_ready=True, bundle=_bundle_info(registry.bundle, settings))


@guarded.get("/features", response_model=FeatureListResponse, responses={503: {"model": ErrorResponse}}, tags=["System"],
             summary="List the model inputs, in the order the model expects")
def features(bundle: LoadedBundle = Depends(require_bundle)):
    return FeatureListResponse(features=[FeatureInfo(**{k: f.get(k) for k in FeatureInfo.model_fields}) for f in bundle.feature_info])


@guarded.get("/template.csv", tags=["System"], summary="Download an empty CSV template with the correct columns",
             responses={200: {"content": {"text/csv": {}}}, 503: {"model": ErrorResponse}})
def template_csv(bundle: LoadedBundle = Depends(require_bundle)):
    header = [*IDENTIFIER_COLUMNS, *OPTIONAL_COLUMNS, *bundle.feature_names]
    return Response(",".join(header) + "\r\n", media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="motor_upload_template.csv"'})
