#!/usr/bin/env python3
"""US racing model: leak-free history features on US flat/dirt races (raceform course '(USA)').

Train 2017-2023, choose the blend weight on 2024, test on 2025 (Jan-Jul). The market price is a
stacker input and evaluation only, never a model feature. Source: raceform rows with course ilike '%(USA)%'.
Pass --parquet for a local extract, or run inside Railway where Supabase is reachable.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services.horse_history_features import HISTORY_FEATURES, compute_history_features, parse_sp_dec
from scripts.research.train_horse_history_candidate import build_frame, BASE

def load(parquet):
    if parquet:
        return pd.read_parquet(parquet)
    from app.services.raceform_source import load_raceform
    return load_raceform(course_ilike="*(USA)*")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--parquet", default=None); a = ap.parse_args()
    raw = load(a.parquet)
    raw = raw[raw["pos"].astype(str).str.fullmatch(r"\d+", na=False)]
    df = build_frame(raw)
    # US going words not in the UK map: sloppy/muddy treated as soft (0.0)
    g = raw.set_index(raw.index)["going"].astype(str).str.lower()
    df.loc[g.reindex(df.index).isin(["sloppy", "muddy"]).values, "going_code"] = 0.0
    df["type_code"] = df["type"].map({t: i for i, t in enumerate(sorted(df["type"].dropna().unique()))}).astype(float)
    df["sp_dec"] = df["sp"].map(parse_sp_dec)
    df = compute_history_features(df)
    df = df[df["sp_dec"].notna() & (df["sp_dec"] > 1.0) & df["dist_f"].notna()].copy()
    df["y"] = (df["pos_n"] == 1).astype(int)
    df["year"] = df["date"].dt.year
    df["p_mkt"] = (1.0 / df["sp_dec"]) / df.groupby("race_id")["sp_dec"].transform(lambda s: (1.0 / s).sum())
    FEATS = BASE + HISTORY_FEATURES
    tr, va, te = df[df.year <= 2023], df[df.year == 2024].copy(), df[df.year == 2025].copy()
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=2607)
    m.fit(tr[FEATS].fillna(-1), tr["y"])
    va["p_model"] = m.predict_proba(va[FEATS].fillna(-1))[:, 1]
    te["p_model"] = m.predict_proba(te[FEATS].fillna(-1))[:, 1]
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    X = lambda d: np.column_stack([lg(d["p_model"].values), lg(d["p_mkt"].values)])
    st = LogisticRegression(C=1.0, max_iter=1000).fit(X(va), va["y"])
    te["p_stack"] = st.predict_proba(X(te))[:, 1]
    def picks(d, col, sign=1):
        hits = ret = n = 0
        for _, r in d.groupby("race_id"):
            pk = r.loc[(sign * r[col]).idxmax()]
            n += 1
            if pk["y"] == 1: hits += 1; ret += pk["sp_dec"]
        return {"races": n, "top_pick_hit": round(hits / n, 4), "roi_pct": round(100 * (ret - n) / n, 2)}
    out = {
        "rows": {"train": len(tr), "val_2024": len(va), "test_2025": len(te)},
        "stacker": {"logit_model": round(float(st.coef_[0][0]), 4), "logit_market": round(float(st.coef_[0][1]), 4)},
        "logloss_2025": {"model_only": round(log_loss(te.y, te.p_model), 5),
                         "market_only": round(log_loss(te.y, te.p_mkt), 5),
                         "stacked": round(log_loss(te.y, te.p_stack), 5)},
        "auc_2025": {"model_only": round(roc_auc_score(te.y, te.p_model), 4), "stacked": round(roc_auc_score(te.y, te.p_stack), 4)},
        "picks_2025": {"model_only": picks(te, "p_model"), "stacked": picks(te, "p_stack"),
                       "favourite": picks(te, "sp_dec", sign=-1)},
    }
    print(json.dumps(out, indent=2, default=float))

if __name__ == "__main__":
    main()
