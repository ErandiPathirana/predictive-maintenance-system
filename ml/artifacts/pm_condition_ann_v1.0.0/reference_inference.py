# reference_inference.py: NumPy-only inference for the motor-condition ANN bundle.
# Copy this file into the backend. It needs only numpy (no TensorFlow, no pickle).
import hashlib
import json
from pathlib import Path

import numpy as np


def verify_manifest(bundle_dir):
    d = Path(bundle_dir)
    manifest = json.loads((d / "MANIFEST.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if hashlib.sha256((d / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Bundle file is missing, changed or corrupted: " + name)
    return manifest


def load_bundle(bundle_dir, verify=True):
    d = Path(bundle_dir)
    if verify:
        verify_manifest(d)
    pre = json.loads((d / "preprocessing.json").read_text(encoding="utf-8"))
    arch = json.loads((d / "model_architecture.json").read_text(encoding="utf-8"))
    classes = json.loads((d / "class_mapping.json").read_text(encoding="utf-8"))["classes"]
    meta = json.loads((d / "training_metadata.json").read_text(encoding="utf-8"))
    with np.load(d / "weights.npz", allow_pickle=False) as z:
        layers = [(z["W%d" % i].copy(), z["b%d" % i].copy(), spec["activation"]) for i, spec in enumerate(arch["layers"])]
    return {"feature_names": pre["feature_names"], "mean": np.array(pre["mean"], dtype="float64"),
            "scale": np.array(pre["scale"], dtype="float64"), "layers": layers,
            "class_names": [c["name"] for c in sorted(classes, key=lambda c: c["id"])],
            "version": meta["bundle_version"], "provisional": meta["provisional_label_provenance"]}


def predict_proba_matrix(bundle, X):
    z = (np.asarray(X, dtype="float64") - bundle["mean"]) / bundle["scale"]
    for W, b, act in bundle["layers"]:
        z = z @ W + b
        if act == "relu":
            z = np.maximum(z, 0.0)
        elif act == "softmax":
            z = np.exp(z - z.max(axis=1, keepdims=True))
            z = z / z.sum(axis=1, keepdims=True)
        else:
            raise ValueError("Unsupported activation: " + act)
    return z


def predict(bundle, readings):
    names = bundle["feature_names"]
    missing = [n for n in names if n not in readings]
    unknown = [k for k in readings if k not in names]
    if missing or unknown:
        raise ValueError("missing=%s unknown=%s" % (missing, unknown))
    x = np.array([[float(readings[n]) for n in names]], dtype="float64")
    if not np.isfinite(x).all():
        raise ValueError("All readings must be finite numbers.")
    p = predict_proba_matrix(bundle, x)[0]
    k = int(p.argmax())
    return {"predicted_class": bundle["class_names"][k], "predicted_class_id": k,
            "probabilities": {c: float(v) for c, v in zip(bundle["class_names"], p)},
            "bundle_version": bundle["version"], "provisional_label_provenance": bundle["provisional"]}
