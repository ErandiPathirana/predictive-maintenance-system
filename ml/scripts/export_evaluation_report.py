"""Export the saved research evaluation report that the website's "Model evaluation" page shows.

It copies numbers that the Colab notebook ALREADY computed on the held-out test motors
(training_metadata.json). It computes nothing new and invents nothing.

Usage (from the project root):
  python ml/scripts/export_evaluation_report.py ml/artifacts/pm_condition_ann_v1.0.0 --data-origin real
Output: frontend/public/evaluation_report.json  (change with --out)

--data-origin says where the training data came from. The bundle does not record this, so YOU must say it:
  real       measured plant data
  synthetic  generated data (demonstration only)
  unknown    default - the page will say the origin was not recorded
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "pm.evaluation_report.v1"
ROOT = Path(__file__).resolve().parents[2]


def build(bundle: Path, data_origin: str, allow_smoke: bool) -> dict:
    meta_path = bundle / "training_metadata.json"
    if not meta_path.is_file():
        sys.exit(f"ERROR: {meta_path} not found. Pass the bundle folder made by the Colab notebook.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("fast_debug_run") and not allow_smoke:
        sys.exit("ERROR: this bundle came from a FAST_DEBUG smoke test; its numbers are meaningless. Use --allow-smoke only to test the page.")
    tm = meta.get("test_metrics") or {}
    ann = tm.get("ANN")
    if not ann or "confusion_matrix" not in ann or "per_class" not in ann:
        sys.exit("ERROR: training_metadata.json has no test_metrics.ANN with confusion_matrix and per_class.")
    classes = meta.get("classes")
    if not classes:
        sys.exit("ERROR: training_metadata.json has no 'classes'.")

    def metrics(m: dict) -> dict:
        keep = ("n", "accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "macro_precision", "macro_recall", "mcc",
                "roc_auc_ovr_macro", "pr_auc_macro")
        return {k: m.get(k) for k in keep} | {"per_class": m["per_class"], "confusion_matrix": m["confusion_matrix"]}

    ds = meta.get("dataset", {})
    return {
        "schema": SCHEMA,
        "source": "training_metadata.json of the model bundle (computed once by the Colab notebook on held-out test motors)",
        "bundle_version": meta.get("bundle_version"),
        "created_utc": meta.get("created_utc"),
        "test_evaluated_at_utc": meta.get("test_evaluated_at_utc"),
        "task": meta.get("task"),
        "classes": classes,
        "data_origin": data_origin,
        "smoke_test": bool(meta.get("fast_debug_run")),
        "provisional_label_provenance": bool(meta.get("provisional_label_provenance", True)),
        "label_provenance": meta.get("label_provenance"),
        "dataset": {"file_name": ds.get("file_name"), "records": ds.get("records"), "motors": ds.get("motors"), "time_range": ds.get("time_range")},
        "split": meta.get("split", {}).get("summary"),
        "split_strategy": meta.get("split", {}).get("strategy"),
        "model": metrics(ann),
        "baselines": {name: metrics(m) for name, m in tm.items() if name != "ANN" and "per_class" in m and "confusion_matrix" in m},
        "bootstrap_ci_by_motor": meta.get("test_bootstrap_ci_by_motor"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--data-origin", choices=["real", "synthetic", "unknown"], default="unknown")
    ap.add_argument("--out", type=Path, default=ROOT / "frontend" / "public" / "evaluation_report.json")
    ap.add_argument("--allow-smoke", action="store_true")
    a = ap.parse_args()
    report = build(a.bundle, a.data_origin, a.allow_smoke)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {a.out}  (bundle {report['bundle_version']}, data origin: {a.data_origin})")


if __name__ == "__main__":
    main()
