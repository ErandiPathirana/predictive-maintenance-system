"""Loads the trained model and its companion files from disk.

Three files are exported from Google Colab (see ml/README.md):
  model.joblib          a scikit-learn Pipeline (preprocessing + classifier)
  feature_schema.json   the input feature names, units and optional valid ranges
  model_metadata.json   model name, version, positive class, decision threshold

If a file is missing the app still starts. It simply reports "model not ready",
so the frontend can show a clear message instead of crashing.

SECURITY NOTE: joblib/pickle files can run code when loaded. Only ever load
model files that you created yourself.
"""

import json
import logging
from pathlib import Path
from typing import Any

import joblib

from app.config import Settings
from app.schemas import FeatureSchema, ModelMetadata

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Holds the loaded model in memory (loaded once, at startup)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self.model: Any | None = None
        self.schema: FeatureSchema | None = None
        self.metadata: ModelMetadata | None = None
        self.not_ready_reason: str | None = "Model has not been loaded yet."

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.schema is not None and self.metadata is not None

    def load(self) -> None:
        """Try to load everything. Never raises: failures are stored as a reason."""
        s = self._settings
        missing = [p.name for p in (s.model_path, s.schema_path, s.metadata_path) if not p.exists()]
        if missing:
            self._fail(f"Missing model file(s): {', '.join(missing)}. Export them from Colab (see ml/README.md).")
            return
        try:
            schema = FeatureSchema.model_validate(_read_json(s.schema_path))
            metadata = ModelMetadata.model_validate(_read_json(s.metadata_path))
            model = joblib.load(s.model_path)
        except Exception as exc:  # noqa: BLE001 - we want to report any loading problem
            logger.exception("Failed to load model artifacts")
            self._fail(f"Could not load model files: {type(exc).__name__}: {exc}")
            return

        if not hasattr(model, "predict_proba"):
            self._fail("The loaded model has no predict_proba(). Export a classifier that supports probabilities.")
            return

        self.model, self.schema, self.metadata = model, schema, metadata
        self.not_ready_reason = None
        logger.info("Model loaded: %s (%s)", metadata.model_name, metadata.model_version)

    def _fail(self, reason: str) -> None:
        self.model = self.schema = self.metadata = None
        self.not_ready_reason = reason
        logger.warning("Model not ready: %s", reason)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
