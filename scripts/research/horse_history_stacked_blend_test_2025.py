#!/usr/bin/env python3
"""Proper blend test (replaces horse_history_blend_test_2025.py, whose logit sum was not calibrated).

Train the history model on 2017-2023. On 2024 (out of sample for the model) fit a logistic
stacker on [logit(model), logit(market)] -> calibrated win probability. Test the stacker on 2025.
The market price is used only as a stacker input and for evaluation, never inside the model.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services.horse_history_features import (
    HISTORY_FEATURES, compute_history_features, parse_sp_dec)
from scripts.research.train_horse_history_candidate import build_frame, BASE

raw = pd.read_parquet(ROOT / "data" / "raceform_leakfree_src.parquet")
jt = pd.read_parquet(ROOT / "data" / "raceform_jt.parquet")[["race_id", "horse", "jockey", "trainer"]]
raw = raw.merge(jt, on=["race_id", "horse"], how="left")
raw = raw[raw["pos"].str.fullmatch(r"\d+", na=False)]
df = build_frame(raw)
df["type_code"] = df["type"].map({t: i for i, t in enumerate(sorted(df["type"].dropna().unique()))}).astype(float)
df["sp_dec"] = df["sp"].map(parse_sp_dec)
df = compute_history_features(df)
df = df[df["sp_dec"].notna() & (df["sp_dec"] > 1.0) & df["dist_f"].notna()].copy()
df["y"] = (df["pos_n"] == 1).astype(int)
df["year"] = df["date"].dt.year
df["p_mkt"] = (1.0 / df["sp_dec"]) / df.groupby("race_id")["sp_dec"].transform(lambda s: (1.0 / s).sum())
FEATS = BASE + HISTORY_FEATURES

def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))

tr, va, te = df[df.year <= 2023], df[df.year == 2024].copy(), df[df.year == 2025].copy()
m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=2607)
m.fit(tr[FEATS].fillna(-1), tr["y"])
va["p_model"] = m.predict_proba(va[FEATS].fillna(-1))[:, 1]
te["p_model"] = m.predict_proba(te[FEATS].fillna(-1))[:, 1]

def X(d): return np.column_stack([logit(d["p_model"]), logit(d["p_mkt"])])
stacker = LogisticRegression(C=1.0, max_iter=1000).fit(X(va), va["y"])
te["p_stack"] = stacker.predict_proba(X(te))[:, 1]

def race_pick(d, col):
    hits = ret = n = 0
    for _, r in d.groupby("race_id"):
        pick = r.loc[r[col].idxmax()]
        n += 1
        if pick["y"] == 1:
            hits += 1; ret += pick["sp_dec"]
    return {"races": n, "top_pick_hit": round(hits / n, 4), "roi_pct": round(100 * (ret - n) / n, 2)}

fav = te.assign(fav_score=-te["sp_dec"])
out = {
    "stacker_coefficients": {"logit_model": round(float(stacker.coef_[0][0]), 4),
                              "logit_market": round(float(stacker.coef_[0][1]), 4),
                              "intercept": round(float(stacker.intercept_[0]), 4)},
    "test_2025_logloss": {"model_only": round(log_loss(te.y, te.p_model), 5),
                          "market_only": round(log_loss(te.y, te.p_mkt), 5),
                          "stacked": round(log_loss(te.y, te.p_stack), 5)},
    "test_2025_auc": {"model_only": round(roc_auc_score(te.y, te.p_model), 4),
                      "stacked": round(roc_auc_score(te.y, te.p_stack), 4)},
    "test_2025_picks": {"model_only": race_pick(te, "p_model"),
                        "stacked": race_pick(te, "p_stack"),
                        "favourite": race_pick(fav, "fav_score")},
}
print(json.dumps(out, indent=2, default=float))
