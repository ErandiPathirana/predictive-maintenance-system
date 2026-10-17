import json

import numpy as np
import pytest

from app.services.artifacts import ModelArtifactError, ModelRegistry, load_bundle
from conftest import CLASSES, FEATURES, make_bundle, make_settings, sign_manifest


def edit_json(d, name, fn):
    p = d / name
    doc = json.loads(p.read_text()); fn(doc); p.write_text(json.dumps(doc)); sign_manifest(d)


def test_valid_bundle_loads(bundle_dir):
    b = load_bundle(bundle_dir)
    assert b.feature_names == FEATURES and b.class_names == CLASSES and b.provisional is True and b.version == "v9.9.9"


def test_missing_folder(tmp_path):
    with pytest.raises(ModelArtifactError, match="not found"):
        load_bundle(tmp_path / "nope")


def test_missing_required_file_is_named(bundle_dir):
    (bundle_dir / "weights.npz").unlink()
    with pytest.raises(ModelArtifactError, match="weights.npz"):
        load_bundle(bundle_dir)


def test_missing_manifest(bundle_dir):
    (bundle_dir / "MANIFEST.json").unlink()
    with pytest.raises(ModelArtifactError, match="MANIFEST"):
        load_bundle(bundle_dir)


def test_tampered_file_fails_checksum(bundle_dir):
    p = bundle_dir / "training_metadata.json"
    p.write_text(p.read_text() + " ")
    with pytest.raises(ModelArtifactError, match="Checksum mismatch"):
        load_bundle(bundle_dir)


def test_manifest_with_path_traversal_is_rejected(bundle_dir):
    m = json.loads((bundle_dir / "MANIFEST.json").read_text()); m["files"]["../evil.txt"] = "0" * 64
    (bundle_dir / "MANIFEST.json").write_text(json.dumps(m))
    with pytest.raises(ModelArtifactError, match="unsafe"):
        load_bundle(bundle_dir)


def test_required_file_must_be_covered_by_manifest(bundle_dir):
    m = json.loads((bundle_dir / "MANIFEST.json").read_text()); del m["files"]["parity_probe.json"]
    (bundle_dir / "MANIFEST.json").write_text(json.dumps(m))
    with pytest.raises(ModelArtifactError, match="not covered"):
        load_bundle(bundle_dir)


def test_missing_metadata_key_is_named(bundle_dir):
    edit_json(bundle_dir, "training_metadata.json", lambda d: d.pop("provisional_label_provenance"))
    with pytest.raises(ModelArtifactError, match="provisional_label_provenance"):
        load_bundle(bundle_dir)


def test_wrongly_typed_provenance_flag(bundle_dir):
    edit_json(bundle_dir, "training_metadata.json", lambda d: d.update(provisional_label_provenance="yes"))
    with pytest.raises(ModelArtifactError, match="wrongly typed"):
        load_bundle(bundle_dir)


def test_smoke_test_bundle_refused_unless_allowed(tmp_path):
    make_bundle(tmp_path / "b", fast_debug=True)
    with pytest.raises(ModelArtifactError, match="smoke-test"):
        load_bundle(tmp_path / "b")
    assert load_bundle(tmp_path / "b", allow_smoke_test=True).fast_debug is True


def test_feature_order_mismatch_between_files(bundle_dir):
    def swap(d): d["features"][0], d["features"][1] = d["features"][1], d["features"][0]
    edit_json(bundle_dir, "feature_schema.json", swap)
    with pytest.raises(ModelArtifactError, match="same order"):
        load_bundle(bundle_dir)


def test_class_ids_must_be_contiguous(bundle_dir):
    edit_json(bundle_dir, "class_mapping.json", lambda d: d["classes"][2].update(id=5))
    with pytest.raises(ModelArtifactError, match="0..n-1"):
        load_bundle(bundle_dir)


def test_weight_shape_mismatch(bundle_dir):
    z = dict(np.load(bundle_dir / "weights.npz")); z["W0"] = z["W0"][:5]
    np.savez(bundle_dir / "weights.npz", **z); sign_manifest(bundle_dir)
    with pytest.raises(ModelArtifactError, match="shape"):
        load_bundle(bundle_dir)


def test_nan_weights_rejected(bundle_dir):
    z = dict(np.load(bundle_dir / "weights.npz")); z["b0"][0] = np.nan
    np.savez(bundle_dir / "weights.npz", **z); sign_manifest(bundle_dir)
    with pytest.raises(ModelArtifactError, match="NaN"):
        load_bundle(bundle_dir)


def test_pickled_weights_are_refused(bundle_dir):
    np.savez(bundle_dir / "weights.npz", W0=np.array([{"x": 1}], dtype=object), b0=np.zeros(1)); sign_manifest(bundle_dir)
    with pytest.raises(ModelArtifactError, match="safely"):
        load_bundle(bundle_dir)


def test_unsupported_activation(bundle_dir):
    edit_json(bundle_dir, "model_architecture.json", lambda d: d["layers"][0].update(activation="tanh"))
    with pytest.raises(ModelArtifactError, match="unsupported activations"):
        load_bundle(bundle_dir)


def test_unsupported_preprocessing_type(bundle_dir):
    edit_json(bundle_dir, "preprocessing.json", lambda d: d.update(type="MinMaxScaler"))
    with pytest.raises(ModelArtifactError, match="Unsupported preprocessing"):
        load_bundle(bundle_dir)


def test_zero_scale_rejected(bundle_dir):
    edit_json(bundle_dir, "preprocessing.json", lambda d: d["scale"].__setitem__(0, 0.0))
    with pytest.raises(ModelArtifactError, match="scale"):
        load_bundle(bundle_dir)


def test_parity_probe_mismatch_detected(bundle_dir):
    def corrupt(d): d["probes"][0]["expected_probabilities"]["Normal"] += 0.1
    edit_json(bundle_dir, "parity_probe.json", corrupt)
    with pytest.raises(ModelArtifactError, match="Parity probe"):
        load_bundle(bundle_dir)


def test_registry_reports_reason_without_server_paths(tmp_path):
    reg = ModelRegistry(make_settings(tmp_path / "missing"))
    reg.load()
    assert not reg.is_ready and "missing" in reg.reason
    assert "tmp" not in reg.public_reason and "missing" not in reg.public_reason
