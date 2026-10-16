"""Check the exported artifacts on YOUR computer before running the full app.

Run from the project root (PowerShell):
    python ml/scripts/validate_artifacts.py

It loads the files exactly like the backend does, then runs ONE smoke-test
prediction to prove the model accepts the schema. The smoke-test numbers are
placeholders (middle of each range, or 0) and the output is NOT a result.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.schemas import PredictionRequest  # noqa: E402
from app.services.model_loader import ModelRegistry  # noqa: E402
from app.services.prediction import predict_failure  # noqa: E402


def main() -> int:
    registry = ModelRegistry(get_settings())
    registry.load()
    if not registry.is_ready:
        print("FAIL:", registry.not_ready_reason)
        return 1

    print(f"Loaded model: {registry.metadata.model_name} ({registry.metadata.model_version})")
    print(f"Features ({len(registry.schema.features)}): {', '.join(registry.schema.names)}")

    readings = {}
    for f in registry.schema.features:
        readings[f.name] = (f.min + f.max) / 2 if f.min is not None and f.max is not None else 0.0
    try:
        result = predict_failure(registry, PredictionRequest(readings=readings))
    except Exception as exc:  # noqa: BLE001
        print("FAIL during smoke test:", exc)
        return 1
    print("Smoke test OK (placeholder input, not a real result). Probability:", round(result.failure_probability, 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
