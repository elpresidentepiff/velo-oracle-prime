"""
SQPE v17 Service — Clean Loader
Loads and executes the canonical SQPE v17 model.
Replaces the quarantined model_manager for production scoring.
"""

import logging
import math
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "sqpe_v17" / "sqpe_v17.pkl"
V16_MODEL_PATH = ROOT / "models" / "sqpe_v16" / "sqpe_v16.pkl"
NO_RPR_SHADOW_MODEL_PATH = ROOT / "models" / "sqpe_v17_no_rpr_staging" / "sqpe_v17_no_rpr.pkl"

# Exact order from model.feature_names_in_
EXPECTED_FEATURES = [
    "sp_dec",
    "log_sp",
    "implied_prob",
    "dist_f",
    "going_code",
    "is_aw",
    "class_num",
    "wgt_lbs",
    "or_num",
    "rpr_num",
    "ts_num",
    "or_vs_field",
    "rpr_vs_field",
    "field_size",
    "draw_num",
    "draw_pct",
    "age_num",
    "sp_rank",
    "is_fav",
    "runs_since_win",
    "runs_since_place",
    "runs_since_mkt_support",
    "curr_or_minus_last_win_or",
    "curr_or_minus_best_or",
    "mark_compression_score",
    "release_window_score",
    "course_fit_score",
    "going_fit_score",
    "distance_fit_score",
    "quiet_run_score",
    "trainer_timing_score",
    "jockey_switch_intent",
    "odds_resilience_score",
    "odds_contraction_score",
    "decoy_support_flag",
    "setup_run_flag",
    "cash_run_flag",
]

_model = None
_model_feature_names = None
_no_rpr_shadow_model = None
_no_rpr_shadow_feature_names = None


def _load_model():
    global _model, _model_feature_names
    if _model is not None:
        return _model

    path = MODEL_PATH
    if not path.exists():
        path = V16_MODEL_PATH

    if not path.exists():
        logger.error(f"SQPE model not found at {MODEL_PATH} or {V16_MODEL_PATH}")
        return None

    _model = joblib.load(path)
    _model_feature_names = _extract_model_feature_names(_model)
    logger.info(f"SQPE model loaded from {path}")
    return _model


def _extract_model_feature_names(model) -> list[str]:
    """Return the real feature contract for live and challenger SQPE models."""
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        return [str(name) for name in names]

    classifiers = getattr(model, "calibrated_classifiers_", None) or []
    for clf in classifiers:
        estimator = getattr(clf, "estimator", None) or getattr(clf, "base_estimator", None)
        names = getattr(estimator, "feature_names_in_", None)
        if names is not None:
            return [str(name) for name in names]

    return list(EXPECTED_FEATURES)


def _feature_names_for_model(model=None) -> list[str]:
    """Expose the loaded model's feature order for tests and shadow lanes."""
    global _model_feature_names
    if model is not None:
        return _extract_model_feature_names(model)
    if _model_feature_names is None:
        loaded = _load_model()
        if loaded is None:
            return list(EXPECTED_FEATURES)
    return list(_model_feature_names or EXPECTED_FEATURES)


def _load_no_rpr_shadow_model():
    """Load the no-RPR challenger for report-only shadow scoring."""
    global _no_rpr_shadow_model, _no_rpr_shadow_feature_names
    if _no_rpr_shadow_model is not None:
        return _no_rpr_shadow_model
    if not NO_RPR_SHADOW_MODEL_PATH.exists():
        return None
    try:
        _no_rpr_shadow_model = joblib.load(NO_RPR_SHADOW_MODEL_PATH)
        _no_rpr_shadow_feature_names = _extract_model_feature_names(_no_rpr_shadow_model)
        logger.info("SQPE no-RPR shadow model loaded from %s", NO_RPR_SHADOW_MODEL_PATH)
        return _no_rpr_shadow_model
    except Exception as exc:
        logger.warning("SQPE no-RPR shadow model load failed: %s", exc)
        _no_rpr_shadow_model = None
        _no_rpr_shadow_feature_names = None
        return None


def predict_sqpe_no_rpr_shadow(runner_features: dict) -> tuple[float | None, list[str]]:
    """Report-only no-RPR challenger prediction. Never affects live scoring."""
    model = _load_no_rpr_shadow_model()
    if model is None:
        return None, []
    feature_names = list(_no_rpr_shadow_feature_names or _feature_names_for_model(model))
    vec = [float(runner_features.get(f, 0.0)) for f in feature_names]
    X_df = pd.DataFrame(np.array([vec]), columns=feature_names)
    try:
        prob = float(model.predict_proba(X_df)[0, 1])
        return round(prob, 4), feature_names
    except Exception as exc:
        logger.warning("SQPE no-RPR shadow prediction failed: %s", exc)
        return None, feature_names


def _parse_sp(sp_str) -> float:
    if not sp_str:
        return 10.0
    s = str(sp_str).strip().upper()
    if s in ("EVENS", "EVS"):
        return 2.0
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)) / float(m.group(2)) + 1.0
    try:
        return float(s) + 1.0
    except ValueError:
        return 10.0


def _parse_dist(dist_str) -> float:
    if not dist_str:
        return 16.0
    s = str(dist_str).strip().lower()
    total = 0.0
    m_miles = re.search(r"(\d+(?:\.\d+)?)m", s)
    m_fur = re.search(r"(\d+(?:\.\d+)?)f", s)
    m_yds = re.search(r"(\d+)y", s)
    if m_miles:
        total += float(m_miles.group(1)) * 8
    if m_fur:
        total += float(m_fur.group(1))
    if m_yds:
        total += float(m_yds.group(1)) / 220
    return total if total > 0 else 16.0


def _parse_going(going_str):
    g = str(going_str or "").strip().upper()
    aw = 1 if any(x in g for x in ["STANDARD", "SLOW", "FAST", "TAPETA", "POLYTRACK"]) else 0
    codes = {
        "FIRM": 2.0,
        "GOOD TO FIRM": 1.5,
        "GOOD": 1.0,
        "GOOD TO SOFT": 0.5,
        "SOFT": 0.0,
        "HEAVY": -1.0,
        "YIELDING": 0.3,
        "STANDARD": 1.0,
    }
    for key, val in codes.items():
        if key in g:
            return val, aw
    return 0.5, aw


def _parse_class(class_str) -> float:
    s = str(class_str or "").strip().upper()
    m = re.search(r"CLASS\s*(\d)", s)
    if m:
        return float(m.group(1))
    if "GROUP 1" in s or "GRADE 1" in s:
        return 1.0
    if "GROUP 2" in s or "GRADE 2" in s:
        return 2.0
    if "LISTED" in s:
        return 2.5
    return 4.0


def _parse_wgt(wgt_str) -> float:
    s = str(wgt_str or "").strip()
    m = re.match(r"(\d+)-(\d+)", s)
    if m:
        return float(m.group(1)) * 14 + float(m.group(2))
    try:
        return float(s)
    except ValueError:
        return 126.0


def _parse_num(val) -> float:
    try:
        v = float(str(val).strip())
        return v if not math.isnan(v) else 0.0
    except (ValueError, TypeError):
        return 0.0


def _resolve_decimal_odds(runner: dict) -> float:
    """
    Resolve morning price to European decimal odds from whichever field is populated.

    Priority:
      1. _resolved_sp_dec — pre-cached by score_race_velo_prime (avoid double-compute)
      2. best_odds_decimal — normalizer output, already decimal format
         If value is 0 < v < 1.0, treat as implied probability and invert.
      3. sp — fractional string ("5/2", "4/6") via _parse_sp
      4. Default 10.0 (no price available)

    Never applies the +1 fractional correction to decimal-format fields.
    """
    cached = runner.get("_resolved_sp_dec")
    if cached is not None:
        try:
            return float(cached)
        except (TypeError, ValueError):
            pass

    bd = runner.get("best_odds_decimal")
    if bd is not None:
        try:
            bd_f = float(bd)
            if bd_f > 1.0:
                return round(bd_f, 2)  # proper decimal odds
            if 0.005 < bd_f < 1.0:
                return round(1.0 / bd_f, 2)  # probability → decimal
        except (TypeError, ValueError):
            pass

    sp_str = runner.get("sp")
    if sp_str:
        parsed = _parse_sp(sp_str)
        if parsed > 1.0:
            return parsed

    return 10.0


def build_v17_feature_vector(runner: dict, race: dict) -> dict[str, float]:
    """Build feature dictionary from raw runner+race dicts."""
    sp_dec = _resolve_decimal_odds(runner)
    dist_f = _parse_dist(race.get("dist") or race.get("distance_f") or race.get("distance"))
    going_code, is_aw = _parse_going(race.get("going"))

    feats = {
        "sp_dec": sp_dec,
        "log_sp": math.log(max(sp_dec, 1.01)),
        "implied_prob": 1.0 / max(sp_dec, 1.01),
        "dist_f": dist_f,
        "going_code": going_code,
        "is_aw": float(is_aw),
        "class_num": _parse_class(race.get("class") or race.get("class_raw") or race.get("race_class")),
        "wgt_lbs": _parse_wgt(runner.get("wgt") or runner.get("weight") or runner.get("weight_lbs")),
        "or_num": _parse_num(runner.get("or") or runner.get("or_rating") or runner.get("official_rating")),
        "rpr_num": _parse_num(runner.get("rpr")),
        "ts_num": _parse_num(runner.get("ts")),
        "field_size": _parse_num(race.get("ran") or race.get("runners_count") or len(race.get("runners", []))),
        "draw_num": _parse_num(runner.get("draw") or runner.get("stall")),
        "age_num": _parse_num(runner.get("age")),
        "or_vs_field": _parse_num(runner.get("or_vs_field", 0.0)),
        "rpr_vs_field": _parse_num(runner.get("rpr_vs_field", 0.0)),
        # sp_rank and is_fav pre-injected by score_race_velo_prime; fall back to field_size if missing
        "sp_rank": _parse_num(runner.get("sp_rank") or len(race.get("runners", []))),
        "is_fav": _parse_num(runner.get("is_fav", 0.0)),
    }
    feats["draw_pct"] = feats["draw_num"] / max(feats["field_size"], 1)

    # Missing flags for observability
    feats["or_missing"] = 1.0 if runner.get("official_rating") is None else 0.0
    feats["rpr_missing"] = 1.0 if runner.get("rpr") is None else 0.0
    feats["ts_missing"] = 1.0 if runner.get("ts") is None else 0.0

    from app.services.v17_feature_extractor import DEFAULTS

    for f in EXPECTED_FEATURES:
        if f not in feats:
            feats[f] = float(runner.get(f, DEFAULTS.get(f, 0.0)))

    return feats


def predict_sqpe_v17(runner_features: dict) -> float:
    """Predict win probability for a runner using SQPE v17."""
    model = _load_model()
    if model is None:
        return 0.5

    feature_names = _feature_names_for_model(model)
    vec = [float(runner_features.get(f, 0.0)) for f in feature_names]
    X = np.array([vec])
    try:
        X_df = pd.DataFrame(X, columns=feature_names)
        prob = float(model.predict_proba(X_df)[0, 1])
        return round(prob, 4)
    except Exception as e:
        logger.error(f"SQPE prediction failed: {e}")
        return 0.5
