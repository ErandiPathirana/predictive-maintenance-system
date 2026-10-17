"""Check an exported artifact bundle on YOUR computer before starting the app.

Run from the project root (PowerShell):
    python ml/scripts/validate_artifacts.py                      # uses MODEL_BUNDLE_DIR from .env
    python ml/scripts/validate_artifacts.py ml/artifacts/pm_condition_ann_v1.0.0

It uses exactly the loader the backend uses: checksums, file contract, shapes, class mapping and the
notebook's parity probes. Nothing is predicted from your data.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.artifacts import ModelArtifactError, load_bundle  # noqa: E402


def main() -> int:
    s = get_settings()
    folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else s.model_bundle_dir
    try:
        b = load_bundle(folder, allow_smoke_test=s.allow_smoke_test_bundle)
    except ModelArtifactError as exc:
        print("FAIL:", exc)
        return 1
    print(f"OK: {b.model_name} ({b.version})")
    print(f"  inputs ({b.n_features}): {', '.join(b.feature_names)}")
    print(f"  classes: {', '.join(b.class_names)}")
    print(f"  label provenance documented: {not b.provisional}")
    if b.provisional:
        print("  NOTE: provisional bundle, so results are flagged 'demonstration only' by the API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
