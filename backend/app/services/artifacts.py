"""Loads and VALIDATES the artifact bundle exported by the Colab notebook.

Nothing is guessed: every file, key and shape the notebook promises is checked, and a clear
ModelArtifactError names whatever is missing or inconsistent. Only JSON and NumPy arrays are read
(np.load with allow_pickle=False), so loading a bundle cannot execute code.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.services.inference import forward

logger = logging.getLogger(__name__)

REQUIRED_FILES = (
    "preprocessing.json", "feature_schema.json", "class_mapping.json", "model_architecture.json",
    "weights.npz", "training_metadata.json", "parity_probe.json",
)
REQUIRED_METADATA_KEYS = ("bundle_version", "provisional_label_provenance")
SUPPORTED_ACTIVATIONS = ("relu", "softmax")


class ModelArtifactError(Exception):
    """Raised when the bundle is missing, tampered with, or does not match the contract."""


@dataclass(frozen=True)
class LoadedBundle:
    model_name: str
    version: str
    feature_names: list[str]
    feature_info: list[dict[str, Any]]
    mean: np.ndarray
    scale: np.ndarray
    layers: list[tuple[np.ndarray, np.ndarray, str]]
    class_names: list[str]
    metadata: dict[str, Any]
    provisional: bool
    fast_debug: bool
    observed_ranges: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)

    @property
    def n_features(self) -> int:
        return len(self.feature_names)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelArtifactError(f"{path.name} is missing or is not valid JSON ({type(exc).__name__}).") from exc


def _verify_manifest(d: Path) -> dict[str, Any]:
    if not (d / "MANIFEST.json").is_file():
        raise ModelArtifactError("MANIFEST.json is missing, so the bundle's integrity cannot be verified.")
    manifest = _read_json(d / "MANIFEST.json")
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, dict) or not files:
        raise ModelArtifactError("MANIFEST.json has no 'files' section.")
    for name, expected in files.items():
        if not isinstance(name, str) or name in ("", ".", "..") or Path(name).name != name:
            raise ModelArtifactError(f"MANIFEST.json lists an unsafe file name: {name!r}.")
        path = d / name
        if not path.is_file():
            raise ModelArtifactError(f"File listed in MANIFEST.json is missing: {name}.")
        if _sha256(path) != expected:
            raise ModelArtifactError(f"Checksum mismatch for {name}: the file was changed or corrupted after export.")
    uncovered = [n for n in REQUIRED_FILES if n not in files]
    if uncovered:
        raise ModelArtifactError(f"Required file(s) not covered by MANIFEST.json: {', '.join(uncovered)}.")
    return manifest


def _finite(a: np.ndarray) -> bool:
    return bool(np.isfinite(a).all())


def load_bundle(bundle_dir: Path, *, allow_smoke_test: bool = False) -> LoadedBundle:
    d = Path(bundle_dir)
    if not d.is_dir():
        raise ModelArtifactError(f"Model bundle folder not found: {d}. Export it from the Colab notebook and set MODEL_BUNDLE_DIR.")
    missing = [n for n in REQUIRED_FILES if not (d / n).is_file()]
    if missing:
        raise ModelArtifactError(f"Bundle is missing required file(s): {', '.join(missing)}.")
    manifest = _verify_manifest(d)

    pre = _read_json(d / "preprocessing.json")
    schema = _read_json(d / "feature_schema.json")
    classes_doc = _read_json(d / "class_mapping.json")
    arch = _read_json(d / "model_architecture.json")
    meta = _read_json(d / "training_metadata.json")
    parity = _read_json(d / "parity_probe.json")

    absent = [k for k in REQUIRED_METADATA_KEYS if k not in meta]
    if absent:
        raise ModelArtifactError(f"training_metadata.json lacks required key(s): {', '.join(absent)}.")
    if not isinstance(meta["provisional_label_provenance"], bool) or not isinstance(meta["bundle_version"], str):
        raise ModelArtifactError("training_metadata.json has wrongly typed 'bundle_version' or 'provisional_label_provenance'.")
    fast_debug = bool(meta.get("fast_debug_run", False))
    if fast_debug and not allow_smoke_test:
        raise ModelArtifactError("This bundle came from a FAST_DEBUG smoke-test run and is refused. "
                                 "Re-run the notebook without FAST_DEBUG (or set ALLOW_SMOKE_TEST_BUNDLE=true for local debugging only).")

    # ---- features and scaler ----
    names = pre.get("feature_names")
    if not isinstance(names, list) or not names or len(set(names)) != len(names) or not all(isinstance(n, str) and n for n in names):
        raise ModelArtifactError("preprocessing.json: 'feature_names' must be a non-empty list of unique strings.")
    schema_features = schema.get("features") if isinstance(schema, dict) else None
    if not isinstance(schema_features, list) or [f.get("name") for f in schema_features] != names:
        raise ModelArtifactError("feature_schema.json does not list exactly the same features, in the same order, as preprocessing.json.")
    try:
        mean = np.asarray(pre["mean"], dtype="float64"); scale = np.asarray(pre["scale"], dtype="float64")
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelArtifactError("preprocessing.json: 'mean' and 'scale' must be numeric lists.") from exc
    if mean.shape != (len(names),) or scale.shape != (len(names),):
        raise ModelArtifactError("preprocessing.json: mean/scale length differs from the number of features.")
    if not _finite(mean) or not _finite(scale) or (scale <= 0).any():
        raise ModelArtifactError("preprocessing.json: mean must be finite and scale must be finite and > 0.")
    if pre.get("type") != "StandardScaler":
        raise ModelArtifactError(f"Unsupported preprocessing type: {pre.get('type')!r} (only StandardScaler is implemented).")

    # ---- classes ----
    cls = classes_doc.get("classes") if isinstance(classes_doc, dict) else None
    if not isinstance(cls, list) or len(cls) < 2:
        raise ModelArtifactError("class_mapping.json: at least two classes are required.")
    ordered = sorted(cls, key=lambda c: c.get("id", -1))
    if [c.get("id") for c in ordered] != list(range(len(ordered))):
        raise ModelArtifactError("class_mapping.json: class ids must be 0..n-1 without gaps or duplicates.")
    class_names = [c.get("name") for c in ordered]
    if not all(isinstance(n, str) and n for n in class_names) or len(set(class_names)) != len(class_names):
        raise ModelArtifactError("class_mapping.json: class names must be unique non-empty strings.")

    # ---- network ----
    specs = arch.get("layers") if isinstance(arch, dict) else None
    if not isinstance(specs, list) or not specs:
        raise ModelArtifactError("model_architecture.json: no layers.")
    acts = [s.get("activation") for s in specs]
    if any(a not in SUPPORTED_ACTIVATIONS for a in acts) or acts[-1] != "softmax" or "softmax" in acts[:-1]:
        raise ModelArtifactError(f"model_architecture.json: unsupported activations {acts} (need relu... then a final softmax).")
    layers, prev = [], len(names)
    try:
        with np.load(d / "weights.npz", allow_pickle=False) as z:
            for i, spec in enumerate(specs):
                W, b = np.array(z[f"W{i}"], dtype="float64"), np.array(z[f"b{i}"], dtype="float64")
                if W.ndim != 2 or W.shape[0] != prev or b.shape != (W.shape[1],) or W.shape[1] != spec.get("units"):
                    raise ModelArtifactError(f"weights.npz: layer {i} shape {W.shape} does not fit the architecture (expected {prev} inputs).")
                if not _finite(W) or not _finite(b):
                    raise ModelArtifactError(f"weights.npz: layer {i} contains NaN or infinity.")
                layers.append((W, b, spec["activation"])); prev = W.shape[1]
    except ModelArtifactError:
        raise
    except Exception as exc:  # corrupt file, missing array, or an unsafe (pickled) array
        raise ModelArtifactError(f"weights.npz could not be loaded safely ({type(exc).__name__}).") from exc
    if prev != len(class_names):
        raise ModelArtifactError(f"The network outputs {prev} scores but class_mapping.json has {len(class_names)} classes.")

    observed = {f["name"]: (f.get("observed_train_min"), f.get("observed_train_max")) for f in schema_features}
    bundle = LoadedBundle(
        model_name=str(manifest.get("bundle", d.name)), version=meta["bundle_version"], feature_names=list(names),
        feature_info=schema_features, mean=mean, scale=scale, layers=layers, class_names=list(class_names),
        metadata=meta, provisional=meta["provisional_label_provenance"], fast_debug=fast_debug, observed_ranges=observed)

    # ---- parity probes: proves this backend computes what the notebook computed ----
    probes = parity.get("probes") if isinstance(parity, dict) else None
    if not isinstance(probes, list) or not probes:
        raise ModelArtifactError("parity_probe.json contains no probes.")
    tol = float(parity.get("tolerance", 1e-5))
    if not 0 < tol <= 1e-3:
        raise ModelArtifactError("parity_probe.json: tolerance must be in (0, 1e-3].")
    for p in probes:
        try:
            x = np.array([[float(p["readings"][n]) for n in names]])
            expected = np.array([float(p["expected_probabilities"][c]) for c in class_names])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelArtifactError(f"parity_probe.json: probe {p.get('name')!r} does not match the feature/class lists.") from exc
        diff = float(np.abs(forward(bundle, x)[0] - expected).max())
        if diff > tol:
            raise ModelArtifactError(f"Parity probe {p.get('name')!r} differs from the notebook by {diff:.2e} (> {tol:.0e}). "
                                     "The bundle and the backend inference code are inconsistent.")
    logger.info("Model bundle %s (%s) loaded and verified: %d features, %d classes, %d parity probes passed.",
                bundle.model_name, bundle.version, len(names), len(class_names), len(probes))
    return bundle


class ModelRegistry:
    """Holds the loaded bundle (or the reason there is none). Loads once, never trains."""

    def __init__(self, settings):
        self._settings = settings
        self.bundle: LoadedBundle | None = None
        self.reason: str | None = "Model has not been loaded yet."

    @property
    def is_ready(self) -> bool:
        return self.bundle is not None

    @property
    def public_reason(self) -> str:
        """Safe to show to users: no server paths or file contents."""
        return "The prediction model is not available on the server." if not self.is_ready else ""

    def load(self) -> None:
        try:
            self.bundle = load_bundle(self._settings.model_bundle_dir, allow_smoke_test=self._settings.allow_smoke_test_bundle)
            self.reason = None
        except ModelArtifactError as exc:
            self.bundle, self.reason = None, str(exc)
            logger.error("Model bundle rejected: %s", exc)
