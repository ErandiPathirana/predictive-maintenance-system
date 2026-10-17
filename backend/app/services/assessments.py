"""Glue between a prediction and its recommendations, shared by manual assessments and CSV batches."""
import hashlib
import json

import numpy as np

from app.services.artifacts import LoadedBundle
from app.services.predictions import input_warnings
from app.services.recommendations import RecommendationSet, SiteGuidance, recommend


def recommendation_for(bundle: LoadedBundle, condition: str, x_row: np.ndarray, site: SiteGuidance | None) -> RecommendationSet:
    flagged = [w["feature"] for w in input_warnings(bundle, x_row)]
    return recommend(condition, flagged, site)


def summaries_for(bundle: LoadedBundle, scores: np.ndarray, X: np.ndarray, site: SiteGuidance | None) -> list[str]:
    """One short recommendation summary per row. Rows with the same class and the same flagged inputs share one computation."""
    cache: dict[tuple, str] = {}
    out = []
    for i in range(len(scores)):
        cond = bundle.class_names[int(scores[i].argmax())]
        flagged = tuple(w["feature"] for w in input_warnings(bundle, X[i]))
        if (cond, flagged) not in cache:
            cache[(cond, flagged)] = recommend(cond, flagged, site).summary
        out.append(cache[(cond, flagged)])
    return out


def request_hash(payload: dict) -> str:
    """Fingerprint of a request, so a repeated Idempotency-Key with DIFFERENT data is detected."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
