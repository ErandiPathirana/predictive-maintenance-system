"""NumPy-only forward pass. Mirrors the notebook's reference_inference.py exactly:
standardise with the training mean/scale, then dense layers with ReLU and a final softmax."""

import numpy as np


def forward(bundle, X: np.ndarray) -> np.ndarray:
    z = (np.asarray(X, dtype="float64") - bundle.mean) / bundle.scale
    for W, b, activation in bundle.layers:
        z = z @ W + b
        if activation == "relu":
            z = np.maximum(z, 0.0)
        else:  # softmax (numerically stable)
            z = np.exp(z - z.max(axis=1, keepdims=True))
            z = z / z.sum(axis=1, keepdims=True)
    return z
