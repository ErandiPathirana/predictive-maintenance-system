"""HTTP endpoints. Kept thin: they call the service modules to do the real work."""

from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.errors import ModelNotReadyError
from app.schemas import (
    ErrorResponse,
    FeatureListResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
)
from app.services.model_loader import ModelRegistry
from app.services.prediction import predict_failure

router = APIRouter(prefix="/api/v1")


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


@router.get("/health", response_model=HealthResponse, tags=["System"], summary="Is the API running?")
def health(settings: Settings = Depends(get_settings), registry: ModelRegistry = Depends(get_registry)):
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        model_ready=registry.is_ready,
    )


@router.get("/model/info", response_model=ModelInfoResponse, tags=["Model"], summary="Describe the loaded model")
def model_info(registry: ModelRegistry = Depends(get_registry)):
    if not registry.is_ready:
        return ModelInfoResponse(model_ready=False, reason=registry.not_ready_reason)
    return ModelInfoResponse(
        model_ready=True,
        metadata=registry.metadata.model_dump(mode="json"),
        feature_count=len(registry.schema.features),
    )


@router.get(
    "/model/features",
    response_model=FeatureListResponse,
    responses={503: {"model": ErrorResponse}},
    tags=["Model"],
    summary="List the sensor features the model needs",
)
def model_features(registry: ModelRegistry = Depends(get_registry)):
    if not registry.is_ready:
        raise ModelNotReadyError(registry.not_ready_reason or "Model is not ready.")
    return FeatureListResponse(features=registry.schema.features)


@router.post(
    "/predict",
    response_model=PredictionResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Prediction"],
    summary="Predict failure risk from sensor readings",
)
def predict(body: PredictionRequest, registry: ModelRegistry = Depends(get_registry)):
    return predict_failure(registry, body)
