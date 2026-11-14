"""Horse-history features, as of the race date. ONE implementation for training and live.

Every feature for a runner uses only that horse's runs strictly before the race date.
A runner's own result is never used, and adding later rows cannot change an earlier
feature. Missing values are NaN here; the model fill (-1) is applied by the caller.

Inputs are plain DataFrames with these columns:
  horse, date (datetime), race_id, course, dist_f, going_code, class_num, pos_n (NaN if
  unknown or a non-finisher), or_num, sp_dec (history rows only use pos_n and or_num).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

HISTORY_FEATURES = [
    "runs_prior", "win_rate_prior", "place_rate_prior", "days_since_run", "last_pos",
    "runs_since_win", "runs_since_place", "or_last", "or_change", "or_vs_best",
    "class_change", "avg_pos_last3",
    "course_runs", "course_win_rate", "dist_runs", "dist_win_rate",
    "going_runs", "going_win_rate",
]


def _dist_bucket(dist_f: pd.Series) -> pd.Series:
    return (dist_f.fillna(0) // 2).astype(int)


def compute_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return df (same row order) with HISTORY_FEATURES added, all as-of prior runs.

    Works on the full historical table (training) and on history plus today's runners
    (live). For a row, only earlier rows of the same horse contribute.
    """
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["_ord"] = np.arange(len(out))
    out = out.sort_values(["horse", "date", "race_id", "_ord"], kind="mergesort")
    out["_win"] = (out["pos_n"] == 1).astype(float)
    out["_place"] = (out["pos_n"] <= 3).astype(float)
    g = out.groupby("horse", sort=False)

    out["runs_prior"] = g.cumcount()
    wins_prior = g["_win"].transform(lambda s: s.shift(1).fillna(0).cumsum())
    places_prior = g["_place"].transform(lambda s: s.shift(1).fillna(0).cumsum())
    out["win_rate_prior"] = (wins_prior + 0.1) / (out["runs_prior"] + 1.0)
    out["place_rate_prior"] = (places_prior + 0.3) / (out["runs_prior"] + 1.0)
    last_date = g["date"].shift(1)
    out["days_since_run"] = (out["date"] - last_date).dt.days.clip(upper=730).fillna(365)
    out["last_pos"] = g["pos_n"].shift(1).fillna(0)

    out["runs_since_win"] = _runs_since(out, "_win")
    out["runs_since_place"] = _runs_since(out, "_place")

    out["or_last"] = g["or_num"].shift(1)
    out["or_change"] = out["or_num"] - out["or_last"]
    out["or_vs_best"] = out["or_num"] - g["or_num"].transform(lambda s: s.shift(1).cummax())
    out["class_change"] = out["class_num"] - g["class_num"].shift(1)
    out["avg_pos_last3"] = g["pos_n"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()).fillna(10)

    out["_dist_b"] = _dist_bucket(out["dist_f"])
    _group_rate(out, ["horse", "course"], "course")
    _group_rate(out, ["horse", "_dist_b"], "dist")
    _group_rate(out, ["horse", "going_code"], "going")

    out = out.sort_values("_ord").drop(columns=["_ord", "_win", "_place", "_dist_b"])
    return out


def _runs_since(out: pd.DataFrame, flag: str) -> np.ndarray:
    """Prior runs since the horse's most recent prior row with flag set (all prior runs if none).

    Expects `out` sorted by horse then date (as compute_history_features leaves it).
    """
    horses = out["horse"].to_numpy()
    hit_flag = out[flag].to_numpy() == 1
    res = np.zeros(len(out))
    prev, k, hit = None, 0, -1
    for i in range(len(out)):
        if horses[i] != prev:
            prev, k, hit = horses[i], 0, -1
        res[i] = (k - hit - 1) if hit >= 0 else k
        if hit_flag[i]:
            hit = k
        k += 1
    return res


def _group_rate(out: pd.DataFrame, keys: list[str], name: str) -> None:
    gg = out.groupby(keys, sort=False)
    runs = gg.cumcount()
    wins = gg["_win"].transform(lambda s: s.shift(1).fillna(0).cumsum())
    out[f"{name}_runs"] = runs
    out[f"{name}_win_rate"] = (wins + 0.1) / (runs + 1.0)


# ── parsers shared with the historical test (raceform text formats) ──

def parse_dist_f(s) -> float:
    s = str(s or "").replace("½", ".5")
    m = re.search(r"(\d+)m", s)
    f = re.search(r"(\d+(?:\.\d+)?)f", s)
    t = (int(m.group(1)) * 8 if m else 0) + (float(f.group(1)) if f else 0)
    return t if t > 0 else np.nan


def parse_going_code(s):
    g = str(s or "").lower()
    for k, v in [("heavy", -1), ("good to soft", 0.5), ("soft", 0), ("good to firm", 1.5),
                 ("firm", 2), ("good", 1), ("standard", 1), ("yielding", 0.3), ("slow", 0.5), ("fast", 2)]:
        if k in g:
            return v
    return np.nan


def normalise_name(name) -> str:
    """Match key across raceform ('Name (IRE)') and racing_horse_runs ('Name')."""
    return re.sub(r"\s*\([A-Za-z]{2,4}\)\s*$", "", str(name or "")).strip().lower()
