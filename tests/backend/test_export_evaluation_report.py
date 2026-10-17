"""The evaluation-report exporter copies saved notebook numbers and refuses anything it cannot vouch for."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml" / "scripts"))
import export_evaluation_report as exp  # noqa: E402

PER = {c: {"precision": 0.5, "recall": 0.5, "f1": 0.5, "support": 4} for c in ("Normal", "Alert", "Danger")}
CM = [[2, 1, 1], [1, 2, 1], [1, 1, 2]]


def write(tmp_path, **over):
    meta = {"bundle_version": "v1", "classes": ["Normal", "Alert", "Danger"], "provisional_label_provenance": True,
            "dataset": {"file_name": "d.csv", "records": 12, "motors": 3},
            "split": {"strategy": "motor-grouped", "summary": {"test": {"motors": 1, "records": 4}}},
            "test_metrics": {"ANN": {"n": 12, "accuracy": 0.5, "per_class": PER, "confusion_matrix": CM},
                             "RF": {"n": 12, "accuracy": 0.6, "per_class": PER, "confusion_matrix": CM}}} | over
    (tmp_path / "training_metadata.json").write_text(json.dumps(meta))
    return tmp_path


def test_copies_numbers_and_records_origin(tmp_path):
    r = exp.build(write(tmp_path), "real", False)
    assert r["schema"] == "pm.evaluation_report.v1" and r["data_origin"] == "real"
    assert r["model"]["confusion_matrix"] == CM and r["model"]["accuracy"] == 0.5
    assert list(r["baselines"]) == ["RF"]


def test_refuses_smoke_bundle(tmp_path):
    with pytest.raises(SystemExit):
        exp.build(write(tmp_path, fast_debug_run=True), "real", False)
    assert exp.build(write(tmp_path, fast_debug_run=True), "synthetic", True)["smoke_test"] is True


def test_refuses_missing_metrics(tmp_path):
    with pytest.raises(SystemExit):
        exp.build(write(tmp_path, test_metrics={}), "real", False)
    with pytest.raises(SystemExit):
        exp.build(tmp_path / "nope", "real", False)
