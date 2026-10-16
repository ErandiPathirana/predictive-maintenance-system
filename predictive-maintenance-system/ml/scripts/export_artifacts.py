"""Export a trained model for the backend. Designed to run inside Google Colab.

Usage in a Colab cell (after you trained `pipeline` on a pandas DataFrame `X_train`):

    export_artifacts(
        pipeline=pipeline,
        feature_names=list(X_train.columns),
        out_dir="/content/artifacts",
        model_name="my-model-name",
        model_version="v1",
        decision_threshold=0.5,   # replace with the value YOU chose on VALIDATION data
    )

It writes three files: model.joblib, feature_schema.json, model_metadata.json.
Nothing here invents values: ranges and thresholds are only written if you supply them.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def export_artifacts(
    pipeline,
    feature_names,
    out_dir,
    model_name,
    model_version,
    positive_class=1,
    decision_threshold=None,
    feature_info=None,
    notes=None,
):
    """feature_info (optional): {"feature": {"unit": "...", "min": 0, "max": 100, "description": "..."}}
    Only add min/max if they come from your data or a domain expert. Leave them out otherwise."""
    import joblib

    feature_names = list(feature_names)
    feature_info = feature_info or {}

    if not hasattr(pipeline, "predict_proba"):
        raise ValueError("The model must support predict_proba(). Use a classifier that provides probabilities.")

    trained_names = getattr(pipeline, "feature_names_in_", None)
    if trained_names is None:
        raise ValueError(
            "The model has no feature_names_in_. Train it on a pandas DataFrame (not a NumPy array) "
            "so column names and order are recorded."
        )
    if list(trained_names) != feature_names:
        raise ValueError(f"feature_names do not match training columns.\nTrained on: {list(trained_names)}\nGiven:      {feature_names}")

    unknown = set(feature_info) - set(feature_names)
    if unknown:
        raise ValueError(f"feature_info has names not in feature_names: {sorted(unknown)}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    joblib.dump(pipeline, out / "model.joblib")

    features = []
    for name in feature_names:
        spec = {"name": name}
        spec.update({k: v for k, v in feature_info.get(name, {}).items() if k in {"unit", "min", "max", "description"}})
        features.append(spec)
    (out / "feature_schema.json").write_text(json.dumps({"features": features}, indent=2), encoding="utf-8")

    metadata = {
        "model_name": model_name,
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "positive_class": positive_class,
        "decision_threshold": decision_threshold,
        "notes": notes,
    }
    (out / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    try:
        import sklearn

        print("scikit-learn used for training:", sklearn.__version__, "(backend must use the same minor version)")
    except ImportError:
        pass
    print("Exported to:", out.resolve())
    for p in sorted(out.iterdir()):
        print(f"  {p.name}  ({p.stat().st_size / 1024:.1f} KB)")
