# Artifact contract: Colab notebook to backend

The backend **never trains** and never loads pickle. It reads one bundle folder (`MODEL_BUNDLE_DIR`) written by
`ml/notebooks/motor_condition_ann_training.ipynb`. At startup it verifies everything below and **refuses to start** if anything is wrong.

## Required files (all listed with SHA-256 in `MANIFEST.json`)
| File | Required content |
|---|---|
| `MANIFEST.json` | `{"bundle": name, "files": {file: sha256}}`. Every listed file must exist and match; names must be plain file names. |
| `preprocessing.json` | `type = "StandardScaler"`, `feature_names` (unique, ordered), `mean`, `scale` (finite, scale > 0, same length) |
| `feature_schema.json` | `features[]` with `name` (same order as above), optional `unit`, `description`, `observed_train_min/max` |
| `class_mapping.json` | `classes[]` with ids exactly `0..n-1` and unique names |
| `model_architecture.json` | `layers[]` of dense layers: `relu` ... then a final `softmax`; `units` must match the weights |
| `weights.npz` | `W0,b0,W1,b1,...` float arrays, finite, shapes chained from the feature count to the class count. Loaded with `allow_pickle=False`. |
| `training_metadata.json` | required: `bundle_version` (string), `provisional_label_provenance` (bool). Used if present: `fast_debug_run`, `deployable_for_decisions`, `option_b_future_failure_prediction_supported`, `task`, `created_utc`, `dataset.timestamp_format_assumed`, `test_metrics.ANN` |
| `parity_probe.json` | `probes[]` of `readings` + `expected_probabilities`, `tolerance` <= 1e-3. The backend recomputes them and must match. |

`model.keras`, `model_card.md`, `reproducibility_report.md` and `reference_inference.py` are shipped for humans and are **not executed or loaded** by the backend.

## Startup validation (what is checked)
Folder exists, required files exist, checksums match, JSON parses, feature lists agree across files, scaler values valid, class ids valid,
architecture supported, weight shapes chain correctly, no NaN/infinity, no pickled arrays, smoke-test (`fast_debug_run`) bundles refused
(unless `ALLOW_SMOKE_TEST_BUNDLE=true` outside production), and all parity probes reproduce the notebook's probabilities.

## Gaps in the contract (information the bundle does NOT contain)
The backend does not guess these. Each has a safe, documented behaviour. Fixing them means adding fields in the notebook's bundle writer.

| Missing information | Backend behaviour now | Suggested notebook change |
|---|---|---|
| Whether the data is real or synthetic (`data_origin`) | Results are flagged `demonstration_only` when `provisional_label_provenance` is true or the bundle is a smoke test; an operator can force it with `FORCE_DEMONSTRATION_BANNER` | Add `data_origin: "real" / "synthetic" / "unknown"` to `training_metadata.json` |
| Calibration evaluation | Scores always labelled **not calibrated** | Add `calibration: {evaluated: false}` (or evaluation results) |
| Raw-header aliases (`DE_H_mm/s` to `de_h_velocity_mm_s`) | Only clean column names are accepted; the raw two-row-header file is rejected with an explanation | Add `raw_name` per feature in `feature_schema.json` if raw uploads are ever required |
| Validity limits or alarm thresholds | None are used. `observed_train_min/max` produce non-blocking warnings only | Not needed; supplying invented limits would be wrong |
| Velocity type (RMS/peak), gE definition, rpm/load meaning | Shown only as written in the feature descriptions | Fill from the data owner (open questions spreadsheet) |
| Timestamp convention for uploads | ISO 8601 or `dataset.timestamp_format_assumed` | Confirm with the data owner |
| Model name | Taken from `MANIFEST.json` (`bundle`) | Optional |
| `__pycache__` inside the bundle folder | Ignored (harmless); delete it | Import the reference code with bytecode writing disabled |
