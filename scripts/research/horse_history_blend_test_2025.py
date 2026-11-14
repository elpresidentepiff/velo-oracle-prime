#!/usr/bin/env python3
"""Horse-history model with jockey/trainer features, blended with the market price.
Train 2017-2023, choose the blend weight on 2024 (validation), test on 2025 (holdout).
Market price is used ONLY as the blend input and for evaluation, never inside the model."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services.horse_history_features import compute_history_features, parse_sp_dec
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
# market: implied prob normalised within race
df["p_mkt"] = (1.0 / df["sp_dec"]) / df.groupby("race_id")["sp_dec"].transform(lambda s: (1.0 / s).sum())
FEATS = BASE + [f for f in __import__("app.services.horse_history_features", fromlist=["HISTORY_FEATURES"]).HISTORY_FEATURES]

def logit(p): p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))

tr, va, te = df[df.year <= 2023], df[df.year == 2024], df[df.year == 2025]
m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=2607)
m.fit(tr[FEATS].fillna(-1), tr["y"])
for d in (va, te):
    d["p_model"] = m.predict_proba(d[FEATS].fillna(-1))[:, 1]

def race_roi(d, score):
    hits = ret = n = 0
    for _, r in d.groupby("race_id"):
        pick = r.loc[r[score].idxmax()]
        n += 1
        if pick["y"] == 1: hits += 1; ret += pick["sp_dec"]
    return {"races": n, "hit": round(hits / n, 4), "roi_pct": round(100 * (ret - n) / n, 2)}

def blend(d, w):
    return logit(d["p_model"].values) + w * logit(d["p_mkt"].values)

best = None
for w in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
    v = va.assign(score=blend(va, w))
    ll = log_loss(va["y"], 1 / (1 + np.exp(-v["score"])))
    roi = race_roi(v, "score")["roi_pct"]
    print(f"2024 validation w={w}: logloss={ll:.5f} roi={roi}")
    if best is None or ll < best[1]:
        best = (w, ll)
w = best[0]
te = te.assign(score=blend(te, w))
out = {
    "blend_weight_chosen_on_2024": w,
    "test_2025_auc_model_only": round(roc_auc_score(te["y"], te["p_model"]), 4),
    "test_2025_model_only": race_roi(te, "p_model"),
    "test_2025_blend": race_roi(te, "score"),
    "test_2025_favourite": race_roi(te.assign(neg=-te["sp_dec"]), "neg"),
}
print(json.dumps(out, indent=2, default=float))
