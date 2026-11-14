"""Horse-history features (as-of, strictly before race date) + leak-free model.
Test: train 2017-2024, evaluate 2025. No RPR/TS, no price features."""
import re, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

src = open("scripts/research/leakfree_baseline_raceform_2025.py").read()
helpers = src[src.index("def dist_f"):src.index('df["dist_f"]')]
exec(helpers)

df = pd.read_parquet("data/raceform_leakfree_src.parquet")
df = df[df.pos.str.fullmatch(r"\d+", na=False)].copy()
df["date"] = pd.to_datetime(df.date)
df["pos_n"] = df.pos.astype(int)
df["win"] = (df.pos_n == 1).astype(int)
df["place"] = (df.pos_n <= 3).astype(int)
df["dist_f"] = df.dist.map(dist_f)
df["going_code"] = df.going.map(going)
df["class_num"] = df.class_raw.map(cls)
df["wgt_lbs"] = df.wgt.map(wgt)
df["or_num"] = df.or_rating.map(num)
df["field_size"] = df.ran.map(num)
df["draw_num"] = df.draw.map(num)
df["age_num"] = df.age.map(num)
df["draw_pct"] = df.draw_num / df.field_size
df["or_missing"] = df.or_num.isna().astype(float)
df["or_vs_field"] = df.or_num - df.groupby("race_id").or_num.transform("mean")
df["type_code"] = df.type.astype("category").cat.codes
df["sp_dec"] = df.sp.map(sp_dec)
df["year"] = df.date.dt.year

df = df.sort_values(["horse", "date", "race_id"]).reset_index(drop=True)
g = df.groupby("horse", sort=False)

def prior_sum(col):
    return g[col].transform(lambda s: s.shift(1).fillna(0).cumsum())
def prior_n():
    return g.cumcount()

df["runs_prior"] = prior_n()
df["wins_prior"] = prior_sum("win")
df["places_prior"] = prior_sum("place")
df["win_rate_prior"] = (df.wins_prior + 0.1) / (df.runs_prior + 1.0)   # smoothed
df["place_rate_prior"] = (df.places_prior + 0.3) / (df.runs_prior + 1.0)
df["last_date"] = g.date.shift(1)
df["days_since_run"] = (df.date - df.last_date).dt.days.clip(upper=730).fillna(365)
df["last_pos"] = g.pos_n.shift(1).fillna(0)

# runs since last win / last place (count of prior runs after the most recent win/place)
def runs_since(flag):
    out = np.zeros(len(df))
    for _, idx in g.indices.items():
        hit = -1
        for k, i in enumerate(idx):
            out[i] = (k - hit - 1) if hit >= 0 else k  # prior runs since flag (k = prior count)
            if flag[i]: hit = k
    return out
df["runs_since_win"] = runs_since(df.win.values.astype(bool))
df["runs_since_place"] = runs_since(df.place.values.astype(bool))

df["or_last"] = g.or_num.shift(1)
df["or_change"] = df.or_num - df.or_last
df["or_best_prior"] = g.or_num.transform(lambda s: s.shift(1).cummax())
df["or_vs_best"] = df.or_num - df.or_best_prior
df["class_change"] = df.class_num - g.class_num.shift(1)
df["avg_pos_last3"] = g.pos_n.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean()).fillna(10)

def group_rate(keys, name):
    gg = df.groupby(keys, sort=False)
    runs = gg.cumcount()
    wins = gg.win.transform(lambda s: s.shift(1).fillna(0).cumsum())
    df[f"{name}_runs"] = runs
    df[f"{name}_win_rate"] = (wins + 0.1) / (runs + 1.0)

df["dist_bucket"] = (df.dist_f.fillna(0) // 2).astype(int)
group_rate(["horse", "course"], "course")
group_rate(["horse", "dist_bucket"], "dist")
group_rate(["horse", "going_code"], "going")

HIST = ["runs_prior","win_rate_prior","place_rate_prior","days_since_run","last_pos",
        "runs_since_win","runs_since_place","or_last","or_change","or_vs_best","class_change",
        "avg_pos_last3","course_runs","course_win_rate","dist_runs","dist_win_rate",
        "going_runs","going_win_rate"]
BASE = ["dist_f","going_code","class_num","wgt_lbs","or_num","or_vs_field","or_missing",
        "field_size","draw_num","draw_pct","age_num","type_code"]

d = df[df.sp_dec.notna() & df.dist_f.notna()].copy()
tr = d[d.year <= 2024]; te = d[d.year == 2025]
print("train", len(tr), "test", len(te), "test races", te.race_id.nunique())

def race_eval(g2, col, sign=1):
    hits = ret = n = 0
    for _, r in g2.groupby("race_id"):
        pick = r.loc[(sign * r[col]).idxmax()]
        n += 1
        if pick.win == 1: hits += 1; ret += pick.sp_dec
    return dict(races=n, hit=round(hits/n, 4), roi_pct=round(100*(ret-n)/n, 2))

for name, feats in [("leak-free base", BASE), ("base + horse history", BASE + HIST)]:
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=2607)
    m.fit(tr[feats].fillna(-1), tr.win)
    te = te.assign(p=m.predict_proba(te[feats].fillna(-1))[:, 1])
    print(name, "AUC", round(roc_auc_score(te.win, te.p), 4), "top pick", race_eval(te, "p"))
print("favourite", race_eval(te, "sp_dec", sign=-1))
