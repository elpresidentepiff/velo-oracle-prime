"""
Specialist model loader — Phase C/D
Loads trained specialist models from models/specialist/.
Returns None (gracefully) if a model file doesn't exist yet.
"""
from __future__ import annotations

import warnings
from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent.parent
MODELS_DIR = ROOT / "models" / "specialist"

_MODEL_NAMES = [
    "improvement_model",
    "market_deception_model",
    "release_window_model",
    "comment_intelligence_model",
    "draw_bias_model",
    "place_model",
    "longshot_model",
]


@lru_cache(maxsize=None)
def _load_model(name: str):
    path = MODELS_DIR / name / f"{name}.pkl"
    if not path.exists():
        warnings.warn(f"Specialist model '{name}' not found at {path} — skipping", stacklevel=3)
        return None
    return joblib.load(path)


def score_runner(runner_features: dict) -> dict:
    """
    Score a single runner dict through all available specialist models.
    Returns a dict of {score_name: float} for available models.
    Gracefully returns None for missing models (not yet trained).
    """
    import json
    scores = {}
    df = pd.DataFrame([runner_features])

    for name in _MODEL_NAMES:
        model = _load_model(name)
        if model is None:
            continue

        meta_path = MODELS_DIR / name / "metadata.json"
        if not meta_path.exists():
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        features = meta.get("features", [])
        available = [f for f in features if f in df.columns]
        missing   = [f for f in features if f not in df.columns]

        if len(missing) > len(features) * 0.5:
            warnings.warn(f"{name}: too many missing features ({missing}) — skipping")
            continue

        X = df[available].fillna(0)
        # Pad missing features with 0
        for m in missing:
            X[m] = 0.0
        X = X[features]  # ensure correct column order

        try:
            prob = float(model.predict_proba(X)[0, 1])
        except Exception as e:
            warnings.warn(f"{name}: predict failed — {e}")
            continue

        score_key = name.replace("_model", "_score").replace("place_score", "place_prob")
        scores[score_key] = round(prob, 4)

    return scores


def score_runners_batch(runners_df: pd.DataFrame) -> pd.DataFrame:
    """
    Score a DataFrame of runners through all available specialist models.
    Adds specialist score columns to the DataFrame.
    Returns the augmented DataFrame.
    """
    import json
    out = runners_df.copy()

    for name in _MODEL_NAMES:
        model = _load_model(name)
        if model is None:
            continue

        meta_path = MODELS_DIR / name / "metadata.json"
        if not meta_path.exists():
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        features = meta.get("features", [])
        available = [f for f in features if f in out.columns]
        missing   = [f for f in features if f not in out.columns]

        X = out[available].fillna(0).copy()
        for m in missing:
            X[m] = 0.0
        X = X[features]

        try:
            probs = model.predict_proba(X)[:, 1]
        except Exception as e:
            warnings.warn(f"{name}: batch predict failed — {e}")
            continue

        score_key = name.replace("_model", "_score").replace("place_score", "place_prob")
        out[score_key] = probs.round(4)

    return out
