#!/usr/bin/env python3
"""Train the horse-history CANDIDATE (not promoted). Leak-free: no RPR, TS, price or result features.

Source: raceform parquet built from Supabase raceform (see leakfree_baseline_raceform_2025.py).
Output: models/horse_history_candidate/{model.pkl, metadata.json}. promotion_status is NOT_PROMOTED.
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services.horse_history_features import (  # noqa: E402
    HISTORY_FEATURES, compute_history_features, parse_dist_f, parse_going_code,
)

SRC = ROOT / "data" / "raceform_leakfree_src.parquet"
OUT = ROOT / "models" / "horse_history_candidate"
BASE = ["dist_f", "going_code", "class_num", "wgt_lbs", "or_num", "or_vs_field", "or_missing",
        "field_size", "draw_num", "draw_pct", "age_num", "type_code"]
FEATURES = BASE + HISTORY_FEATURES


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return np.nan


def _wgt(s):
    s = str(s or "").strip()
    if "-" in s:
        a, b = s.split("-", 1)
        if a.isdigit() and b.isdigit():
            return int(a) * 14 + int(b)
    return np.nan


def _cls(s):
    s = str(s or "")
    return float(s[-1]) if s[-1:].isdigit() else np.nan


def build_frame(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["pos_n"] = pd.to_numeric(df["pos"], errors="coerce")
    df["dist_f"] = df["dist"].map(parse_dist_f)
    df["going_code"] = df["going"].map(parse_going_code)
    df["class_num"] = df["class_raw"].map(_cls)
    df["wgt_lbs"] = df["wgt"].map(_wgt)
    df["or_num"] = df["or_rating"].map(_num)
    df["field_size"] = df["ran"].map(_num)
    df["draw_num"] = df["draw"].map(_num)
    df["age_num"] = df["age"].map(_num)
    df["draw_pct"] = df["draw_num"] / df["field_size"]
    df["or_missing"] = df["or_num"].isna().astype(float)
    df["or_vs_field"] = df["or_num"] - df.groupby("race_id")["or_num"].transform("mean")
    return df


def main() -> int:
    raw = pd.read_parquet(SRC)
    raw = raw[raw["pos"].str.fullmatch(r"\d+", na=False)]
    df = build_frame(raw)
    types = sorted(df["type"].dropna().unique().tolist())
    df["type_code"] = df["type"].map({t: i for i, t in enumerate(types)}).astype(float)
    df = compute_history_features(df)
    df = df[df["sp"].notna() & df["dist_f"].notna()]
    df["y"] = (df["pos_n"] == 1).astype(int)
    X = df[FEATURES].fillna(-1)
    model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=2607)
    model.fit(X, df["y"])
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "model.pkl", "wb") as fh:
        pickle.dump(model, fh)
    meta = {
        "model": "horse_history_candidate_v1",
        "algorithm": "HistGradientBoostingClassifier (not the production GBM)",
        "promotion_status": "NOT_PROMOTED",
        "trained_at": datetime.now(UTC).isoformat(),
        "train_rows": int(len(df)),
        "train_years": [int(df["date"].dt.year.min()), int(df["date"].dt.year.max())],
        "features": FEATURES,
        "type_codes": types,
        "fill_value_for_missing": -1,
        "holdout_2025_result": {
            "source": "scripts/research/horse_history_features_test_2025.py (trained 2017-2024)",
            "auc": 0.698, "top_pick_hit": 0.2617, "roi_pct": -7.57,
            "favourite_hit": 0.3486, "favourite_roi_pct": -5.16,
        },
        "gate": "Beat the favourite on a 2025-style holdout before any live use. Operator sign-off required.",
    }
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"trained on {len(df)} rows; wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
