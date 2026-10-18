"""Builds a TRAINED model bundle from SYNTHETIC data, using only NumPy, for end-to-end software testing.

WHAT THIS IS
  * A real training run: standardisation fitted on training motors only, a small ANN (14 -> 16 -> 3, ReLU + softmax)
    trained with Adam, validation-based early stopping, a motor-grouped split, then export in the project's bundle format
    (weights.npz, preprocessing.json, feature_schema.json, class_mapping.json, parity_probe.json, signed MANIFEST.json).
  * The weights are LEARNED. Nothing is forced to a class. Which class a reading gets is decided by the trained network.

WHAT THIS IS NOT
  * It is not your research model and it says nothing about accuracy on real motors. The data are invented
    (class-dependent Gaussian sensor values with deliberate overlap). The bundle is marked
    provisional_label_provenance=true and deployable_for_decisions=false, and its metadata says data_origin=synthetic.

Usage:  python tests/e2e_full/synthetic_model.py [output_dir]     (default: tests/e2e_full/out/bundle)
Also writes samples.json next to the bundle: held-out rows chosen by their SYNTHETIC TRUTH label (never by the model's answer),
together with what an independent NumPy forward pass says the model predicts for each.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "tests" / "backend")]

from conftest import CLASSES, FEATURES, reference_forward, sign_manifest  # noqa: E402
from qa_support import build_bundle  # noqa: E402

SEED = 20260101
UNITS = {"velocity": "mm/s", "_ge": "gE", "temp": "degC", "rotational": "rpm", "load": "%"}

# class-dependent means (Normal, Alert, Danger) and spread for each kind of input. Overlap between classes is deliberate.
KIND = {
    "velocity": ([2.5, 5.5, 9.5], 1.5),
    "_ge": ([0.30, 0.65, 1.20], 0.30),
    "temp": ([55.0, 66.0, 78.0], 7.0),
    "rotational": ([1480.0, 1478.0, 1470.0], 15.0),
    "load": ([60.0, 65.0, 70.0], 18.0),
}


def kind_of(name):
    return next(k for k in KIND if k in name)


def make_data(n_motors=90, per_motor=40, seed=SEED):
    rng = np.random.default_rng(seed)
    rows, y, motor = [], [], []
    for m in range(n_motors):
        base = rng.choice(3, p=[0.55, 0.30, 0.15])          # a motor tends to stay near one condition
        offset = {k: rng.normal(0, 0.35 * KIND[k][1]) for k in KIND}   # motor-specific bias (mounting, environment)
        for _ in range(per_motor):
            c = base if rng.random() < 0.8 else rng.choice(3)
            rows.append([rng.normal(KIND[kind_of(f)][0][c] + offset[kind_of(f)], KIND[kind_of(f)][1]) for f in FEATURES])
            y.append(c); motor.append(m)
    X = np.clip(np.array(rows), 0.01, None)
    return X, np.array(y), np.array(motor)


def train(Xtr, ytr, Xva, yva, units=16, epochs=400, patience=30, lr=0.01, seed=SEED):
    rng = np.random.default_rng(seed)
    W1 = rng.normal(0, np.sqrt(2 / Xtr.shape[1]), (Xtr.shape[1], units)); b1 = np.zeros(units)
    W2 = rng.normal(0, np.sqrt(2 / units), (units, 3)); b2 = np.zeros(3)
    params = [W1, b1, W2, b2]; m = [np.zeros_like(p) for p in params]; v = [np.zeros_like(p) for p in params]
    # mild class weighting so the minority classes are learned
    cw = len(ytr) / (3 * np.bincount(ytr, minlength=3)); best = (1e9, None, 0); t = 0

    def fwd(X, p):
        h = np.maximum(X @ p[0] + p[1], 0); z = h @ p[2] + p[3]
        e = np.exp(z - z.max(1, keepdims=True)); return h, e / e.sum(1, keepdims=True)

    for ep in range(epochs):
        order = rng.permutation(len(Xtr))
        for i in range(0, len(order), 64):
            idx = order[i:i + 64]; xb, yb = Xtr[idx], ytr[idx]
            h, p = fwd(xb, params); g = p.copy(); g[np.arange(len(yb)), yb] -= 1; g *= cw[yb][:, None] / len(yb)
            dW2 = h.T @ g; db2 = g.sum(0); dh = g @ params[2].T; dh[h <= 0] = 0; dW1 = xb.T @ dh; db1 = dh.sum(0)
            t += 1
            for k, gr in enumerate([dW1 + 1e-4 * params[0], db1, dW2 + 1e-4 * params[2], db2]):
                m[k] = 0.9 * m[k] + 0.1 * gr; v[k] = 0.999 * v[k] + 0.001 * gr ** 2
                params[k] -= lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(v[k] / (1 - 0.999 ** t)) + 1e-8)
        _, pv = fwd(Xva, params); loss = -np.log(pv[np.arange(len(yva)), yva] + 1e-12).mean()
        if loss < best[0] - 1e-5: best = (loss, [p.copy() for p in params], ep)
        elif ep - best[2] >= patience: break
    return best[1], best[0], best[2] + 1


def macro_f1(y, pred):
    f = []
    for c in range(3):
        tp = ((pred == c) & (y == c)).sum(); fp = ((pred == c) & (y != c)).sum(); fn = ((pred != c) & (y == c)).sum()
        f.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f))


def main(out: Path):
    X, y, g = make_data()
    motors = np.unique(g); rng = np.random.default_rng(SEED); rng.shuffle(motors)
    n = len(motors); tr_m, va_m, te_m = motors[: int(.6 * n)], motors[int(.6 * n): int(.8 * n)], motors[int(.8 * n):]
    sel = lambda ms: np.isin(g, ms)
    Xtr, ytr, Xva, yva, Xte, yte = X[sel(tr_m)], y[sel(tr_m)], X[sel(va_m)], y[sel(va_m)], X[sel(te_m)], y[sel(te_m)]
    mean, scale = Xtr.mean(0), Xtr.std(0)
    (W1, b1, W2, b2), vloss, epochs = train((Xtr - mean) / scale, ytr, (Xva - mean) / scale, yva)
    layers = [(W1, b1), (W2, b2)]
    pte = reference_forward(mean, scale, layers, Xte); pred = pte.argmax(1)
    test = {"n": int(len(yte)), "accuracy": float((pred == yte).mean()), "macro_f1": macro_f1(yte, pred),
            "confusion_matrix(rows=truth,cols=pred)": [[int(((yte == a) & (pred == b)).sum()) for b in range(3)] for a in range(3)]}
    out.mkdir(parents=True, exist_ok=True)
    build_bundle(out, layers=layers, mean=mean, scale=scale, version="vSYNTH.1", provisional=True, name="pm_condition_ann_vSYNTH")
    # replace placeholder feature ranges/units with ranges actually observed in the TRAINING rows, then record honest metadata
    fs = json.loads((out / "feature_schema.json").read_text())
    for i, f in enumerate(fs["features"]):
        f["observed_train_min"] = float(Xtr[:, i].min()); f["observed_train_max"] = float(Xtr[:, i].max())
        f["unit"] = next(u for k, u in UNITS.items() if k in f["name"])
    (out / "feature_schema.json").write_text(json.dumps(fs, indent=2))
    meta = json.loads((out / "training_metadata.json").read_text())
    meta.update({"task": "SYNTHETIC-DATA end-to-end test model (not the research model)", "data_origin": "synthetic", "demonstration_only": True,
                 "created_utc": "2026-10-18T00:00:00+00:00", "training": {"seed": SEED, "epochs_run": epochs, "validation_loss": float(vloss), "split": "by motor 60/20/20",
                 "records": {"train": int(len(ytr)), "val": int(len(yva)), "test": int(len(yte))}},
                 "test_metrics": {"ANN": {"n": test["n"], "accuracy": test["accuracy"], "balanced_accuracy": test["accuracy"], "macro_f1": test["macro_f1"]}}})
    (out / "training_metadata.json").write_text(json.dumps(meta, indent=2))
    sign_manifest(out, "pm_condition_ann_vSYNTH")

    # Held-out sample rows chosen by SYNTHETIC TRUTH label (not by the model's answer); the model's answer is recorded alongside.
    samples = {}
    Xr = np.round(Xte, 3)                                   # the values a person would type; the reference answer is computed on exactly these
    pr = reference_forward(mean, scale, layers, Xr)
    for c, name in enumerate(CLASSES):
        idx = np.where(yte == c)[0][:4]
        samples[name] = [{"truth": name, "readings": {f: float(Xr[i, j]) for j, f in enumerate(FEATURES)},
                          "reference_prediction": CLASSES[int(pr[i].argmax())],
                          "reference_scores": {CLASSES[k]: float(pr[i][k]) for k in range(3)}} for i in idx]
    (out.parent / "samples.json").write_text(json.dumps({"test_metrics": test, "samples": samples}, indent=2))
    print(f"bundle: {out}\nheld-out test accuracy {test['accuracy']:.3f}, macro-F1 {test['macro_f1']:.3f}, confusion {test['confusion_matrix(rows=truth,cols=pred)']}")
    for name, rows in samples.items():
        print(name, "-> model says", [r["reference_prediction"] for r in rows])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "bundle")
