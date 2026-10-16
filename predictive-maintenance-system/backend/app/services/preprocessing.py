"""Turns validated readings into the table the model expects.

Scaling, encoding and similar steps live INSIDE the exported scikit-learn
Pipeline, so they are guaranteed to match training. This module only has one
job: put the values in the SAME column order used during training.
"""

import pandas as pd

from app.schemas import FeatureSchema


def build_feature_frame(readings: dict[str, float], schema: FeatureSchema) -> pd.DataFrame:
    row = {name: float(readings[name]) for name in schema.names}
    return pd.DataFrame([row], columns=schema.names)
