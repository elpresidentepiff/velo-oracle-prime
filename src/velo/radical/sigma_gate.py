"""Sigma gate inference helpers for Radical Velo shadow mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from .regime_router import safe_float


SIGMA_FEATURES = [
    "model_probability",
    "sp_decimal",
    "implied_probability",
    "edge",
    "field_size",
    "class_num",
    "candidate_stake",
    "router_v1_shadow_pass",
    "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist",
]


def build_sigma_feature_row(verdict: dict[str, Any], class_num: int) -> dict[str, float]:
    top = verdict.get("top") or {}
    vp = safe_float(top.get("velo_prime_prob") or top.get("model_probability"), 0.0)
    sp = safe_float(top.get("sp_dec") or top.get("sp_decimal"), 0.0)
    implied = (1.0 / sp) if sp > 0 else 0.0
    field_size = safe_float(verdict.get("scored") or verdict.get("field_size"), 0.0)
    execution_allowed = bool(
        top.get("execution_allowed")
        or top.get("candidate_execution_allowed")
        or top.get("legacy_execution_allowed")
    )
    return {
        "model_probability": vp,
        "sp_decimal": sp,
        "implied_probability": implied,
        "edge": vp - implied,
        "field_size": field_size,
        "class_num": float(class_num),
        "candidate_stake": 1.0 if execution_allowed else 0.0,
        "router_v1_shadow_pass": 1.0 if execution_allowed else 0.0,
        "router_v2_class4_shadow_pass": 1.0 if class_num == 4 and execution_allowed else 0.0,
        "router_v6_gold_seam_watchlist": 1.0
        if top.get("candidate_execution_lane") == "V6_GOLD_SEAM"
        else 0.0,
    }


class SigmaGate:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.loaded = False
        self.error: str | None = None
        self.features = SIGMA_FEATURES
        self.model: Any | None = None
        try:
            payload = joblib.load(model_path)
            self.model = payload.get("model") if isinstance(payload, dict) else payload
            self.features = payload.get("features", SIGMA_FEATURES) if isinstance(payload, dict) else SIGMA_FEATURES
            self.loaded = self.model is not None
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            self.error = str(exc)

    def predict(self, row: dict[str, float]) -> float | None:
        if not self.loaded or self.model is None:
            return None
        frame = pd.DataFrame([{feature: row.get(feature, 0.0) for feature in self.features}])
        try:
            return float(self.model.predict_proba(frame)[:, 1][0])
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            self.error = str(exc)
            return None

