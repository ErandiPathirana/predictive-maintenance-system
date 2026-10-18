# Reproducibility report: pm_condition_ann_v1.0.0
Generated 2026-10-17T02:12:12+00:00. Run mode: full.

## How to reproduce
1. Same notebook version, same input file (verify SHA-256 below), same library versions.
2. Runtime -> Restart session, then Run all. All seeds are fixed (SEED = 42); TensorFlow deterministic ops are enabled.
3. Exact bit-for-bit equality is expected on the same hardware/libraries; small differences can appear on different CPUs/GPUs or library versions.

## Input data
- File: motor_predictive_maintenance_master.csv | SHA-256: `0270fc74bc9f428b97a0ab8c9cad22fa92a5916edeea98ea9fdf93a795891a8b` | bytes: 216691
- Raw shape (no header assumed): [1940, 18] -> 1938 data rows after removing the sub-heading row (removed only after an exact 15-cell match).
- The original file was only read, never modified.

## Environment
{
  "python": "3.13.16",
  "numpy": "2.1.3",
  "pandas": "2.2.3",
  "scikit-learn": "1.6.1",
  "tensorflow": "2.21.0",
  "keras": "3.13.2",
  "platform": "Linux-6.6.122+-x86_64-with-glibc2.39",
  "gpu": "none"
}

## Settings
- Split fractions (0.6, 0.2, 0.2) (by motors), min class records per split 10, 5000 candidate partitions, 4669 feasible.
- ANN search: 24 random configurations from {"hidden_layers": [1, 2, 3], "units": [16, 32, 64, 128], "dropout": [0.0, 0.1, 0.3], "l2": [0.0, 0.0001, 0.001], "lr": [0.001, 0.003], "batch_size": [32, 64], "class_weight": [null, "balanced"]}; early stopping patience 20, max epochs 300.
- Selected ANN: {"units": 64, "lr": 0.001, "l2": 0.0001, "hidden_layers": 3, "dropout": 0.1, "class_weight": "balanced", "batch_size": 64} | Logistic Regression: {"C": 10, "class_weight": "balanced"} | Random Forest: {"class_weight": "balanced_subsample", "max_depth": 5, "min_samples_leaf": 3, "n_estimators": 200}
- Selection metric: validation macro-F1 (ties: validation Danger recall). Bootstrap resamples: 2000.

## Motors per split (identifiers, treat as internal)
{
 "train": [
  "MSA07",
  "CIPS01",
  "SDP04",
  "SDP06",
  "CIPS08",
  "CIPS05",
  "SDP01",
  "MRP08",
  "CIPR05",
  "MSA08",
  "CIPS04",
  "SDP02",
  "MSA05",
  "MRP03",
  "CIPR04",
  "MSA03",
  "CIPR01",
  "SDP03",
  "MSA02",
  "MRP01",
  "CIPS02",
  "CIPS03",
  "MRP04",
  "CIPR03"
 ],
 "val": [
  "MSA04",
  "CIPR07",
  "MRP02",
  "MRP06",
  "MSA01",
  "MRP07",
  "CIPR06",
  "SDP08"
 ],
 "test": [
  "CIPS07",
  "CIPR02",
  "SDP05",
  "SDP07",
  "CIPS06",
  "CIPR08",
  "MSA06",
  "MRP05"
 ]
}

## Integrity checks that passed in this run
- Unique record IDs; exact sub-heading match; strict numeric and timestamp conversion; labels in the allowed set.
- No excluded column among inputs; no motor shared between splits; scaler fitted on 1164 training rows only.
- NumPy reference inference matches Keras: max |difference| = 2.45e-07.
- Test set evaluated once, at 2026-10-17T02:10:16.703355+00:00.
