"""
VÉLØ — SQPE v16 Predictor
Thin wrapper: loads sqpe_v16.pkl, builds the 19-feature vector from raw runner data.

Usage:
    from app.engine.v16_predictor import V16Predictor
    p = V16Predictor()
    prob = p.predict(runner, race)        # single runner dict
    ranked = p.rank_field(runners, race)  # list of runner dicts
"""

import pickle
import re
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)

MODEL_PATH = Path("models/sqpe_v16/sqpe_v16.pkl")

FEATURE_COLS = [
    "sp_dec", "log_sp", "implied_prob",
    "dist_f", "going_code", "is_aw",
    "class_num", "wgt_lbs",
    "or_num", "rpr_num", "ts_num",
    "or_vs_field", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "age_num", "sp_rank", "is_fav",
]


# ── feature parsers (mirrors train_sqpe_v16.py) ──────────────────────────────

def _parse_sp(sp_str) -> float:
    if not sp_str or str(sp_str).strip() in ("", "–", "-", "nan"):
        return np.nan
    s = str(sp_str).strip().upper().rstrip("F").rstrip("J").strip()
    if s in ("EVENS", "EVS"):
        return 2.0
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)) / float(m.group(2)) + 1.0
    try:
        return float(s) + 1.0
    except ValueError:
        return np.nan


def _parse_dist(dist_str) -> float:
    if not dist_str:
        return np.nan
    s = str(dist_str).strip().lower()
    total = 0.0
    m_miles = re.search(r"(\d+(?:\.\d+)?)m", s)
    m_furlongs = re.search(r"(\d+(?:\.\d+)?)f", s)
    m_yards = re.search(r"(\d+)y", s)
    if m_miles:
        total += float(m_miles.group(1)) * 8
    if m_furlongs:
        total += float(m_furlongs.group(1))
    if m_yards:
        total += float(m_yards.group(1)) / 220
    return total if total > 0 else np.nan


def _parse_going(going_str):
    if not going_str:
        return 0.0, 0
    g = str(going_str).strip().upper()
    aw = 1 if any(x in g for x in ["STANDARD", "SLOW", "FAST", "TAPETA", "POLYTRACK", "FIBRESAND"]) else 0
    codes = {
        "FIRM": 2.0, "GOOD TO FIRM": 1.5, "GOOD": 1.0, "GOOD TO SOFT": 0.5,
        "SOFT": 0.0, "HEAVY": -1.0, "YIELDING": 0.3, "YIELDING TO SOFT": 0.1,
        "STANDARD": 1.0, "STANDARD TO SLOW": 0.5, "SLOW": 0.0, "FAST": 1.5,
    }
    for key, val in codes.items():
        if key in g:
            return val, aw
    return 0.5, aw


def _parse_class(class_str) -> float:
    if not class_str:
        return np.nan
    s = str(class_str).strip().upper()
    m = re.search(r"CLASS\s*(\d)", s)
    if m:
        return float(m.group(1))
    if "GROUP 1" in s or "GRADE 1" in s:
        return 1.0
    if "GROUP 2" in s or "GRADE 2" in s:
        return 2.0
    if "GROUP 3" in s or "GRADE 3" in s:
        return 3.0
    if "LISTED" in s:
        return 2.5
    return np.nan


def _parse_wgt(wgt_str) -> float:
    if not wgt_str:
        return np.nan
    s = str(wgt_str).strip()
    m = re.match(r"(\d+)-(\d+)", s)
    if m:
        return float(m.group(1)) * 14 + float(m.group(2))
    try:
        return float(s)
    except ValueError:
        return np.nan


def _num(val) -> float:
    if val is None:
        return np.nan
    s = str(val).strip()
    if s in ("", "–", "-", "nan"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


# ── field-level feature builder ──────────────────────────────────────────────

def build_features(runners: List[Dict[str, Any]], race: Dict[str, Any]) -> np.ndarray:
    """
    Build the 19-feature matrix for a full field.

    Args:
        runners: list of runner dicts. Each must have keys:
            sp, or_rating (or 'or'), rpr, ts, draw, age, wgt, (optionally: horse, jockey)
        race: race dict with keys:
            dist (or distance), going, class_raw (or 'class'), ran (field size)

    Returns:
        np.ndarray shape (n_runners, 19)
    """
    n = len(runners)
    dist_f = _parse_dist(race.get("dist") or race.get("distance", ""))
    going_code, is_aw = _parse_going(race.get("going", ""))
    class_num = _parse_class(race.get("class_raw") or race.get("class", ""))
    field_size = _num(race.get("ran") or race.get("field_size") or n)

    sp_decs = np.array([_parse_sp(r.get("sp", "")) for r in runners])
    or_nums = np.array([_num(r.get("or_rating") or r.get("or", "")) for r in runners])
    rpr_nums = np.array([_num(r.get("rpr", "")) for r in runners])
    ts_nums = np.array([_num(r.get("ts", "")) for r in runners])

    # Field-relative features (fill NaN with field mean before computing delta)
    or_safe = np.where(np.isnan(or_nums), np.nanmean(or_nums) if not np.all(np.isnan(or_nums)) else 0, or_nums)
    rpr_safe = np.where(np.isnan(rpr_nums), np.nanmean(rpr_nums) if not np.all(np.isnan(rpr_nums)) else 0, rpr_nums)
    or_vs_field = or_safe - np.mean(or_safe)
    rpr_vs_field = rpr_safe - np.mean(rpr_safe)

    # SP rank (1 = favourite)
    valid_sp = np.where(np.isnan(sp_decs), 999, sp_decs)
    sp_rank = np.argsort(np.argsort(valid_sp)) + 1
    is_fav = (sp_rank == 1).astype(float)

    rows = []
    for i, r in enumerate(runners):
        sp_dec = float(sp_decs[i]) if not np.isnan(sp_decs[i]) else 0.0
        log_sp = float(np.log(max(sp_dec, 1.01))) if sp_dec > 0 else 0.0
        implied_prob = 1.0 / max(sp_dec, 1.01) if sp_dec > 0 else 0.0
        draw_num = _num(r.get("draw", ""))
        draw_pct = (draw_num / max(field_size, 1)) if not np.isnan(draw_num) else 0.0

        row = [
            sp_dec if not np.isnan(sp_decs[i]) else 0.0,
            log_sp,
            implied_prob,
            dist_f if not np.isnan(dist_f) else 0.0,
            going_code,
            float(is_aw),
            class_num if not np.isnan(class_num) else 0.0,
            _parse_wgt(r.get("wgt", "")) or 0.0,
            float(or_nums[i]) if not np.isnan(or_nums[i]) else 0.0,
            float(rpr_nums[i]) if not np.isnan(rpr_nums[i]) else 0.0,
            float(ts_nums[i]) if not np.isnan(ts_nums[i]) else 0.0,
            float(or_vs_field[i]),
            float(rpr_vs_field[i]),
            float(field_size) if not np.isnan(field_size) else float(n),
            float(draw_num) if not np.isnan(draw_num) else 0.0,
            float(draw_pct) if not np.isnan(draw_pct) else 0.0,
            _num(r.get("age", "")) or 0.0,
            float(sp_rank[i]),
            float(is_fav[i]),
        ]
        rows.append(row)

    return pd.DataFrame(rows, columns=FEATURE_COLS)


# ── predictor class ───────────────────────────────────────────────────────────

class V16Predictor:
    def __init__(self, model_path: Path = MODEL_PATH):
        self._model = None
        self._path = model_path

    def _load(self):
        if self._model is None:
            with open(self._path, "rb") as f:
                self._model = pickle.load(f)
            log.info(f"SQPE v16 loaded from {self._path}")

    def predict(self, runner: Dict[str, Any], all_runners: List[Dict[str, Any]], race: Dict[str, Any]) -> float:
        """Return win probability for one runner, given full field context."""
        self._load()
        X = build_features(all_runners, race)
        idx = all_runners.index(runner)
        proba = self._model.predict_proba(X)[idx, 1]
        return float(proba)

    def rank_field(self, runners: List[Dict[str, Any]], race: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Score and rank all runners in a field.
        Returns list sorted by v16_prob descending, each entry has:
            horse, v16_prob, v16_score (0-100), sp_dec, or_rating, rpr
        """
        self._load()
        X = build_features(runners, race)
        probs = self._model.predict_proba(X)[:, 1]

        results = []
        for i, r in enumerate(runners):
            results.append({
                "rank": 0,
                "horse": r.get("horse") or r.get("horse_name", f"Runner {i+1}"),
                "v16_prob": round(float(probs[i]), 4),
                "v16_score": round(float(probs[i]) * 100, 1),
                "sp": r.get("sp", ""),
                "or_rating": r.get("or_rating") or r.get("or", ""),
                "rpr": r.get("rpr", ""),
                "ts": r.get("ts", ""),
                "draw": r.get("draw", ""),
            })

        results.sort(key=lambda x: x["v16_prob"], reverse=True)
        for i, res in enumerate(results):
            res["rank"] = i + 1
        return results
