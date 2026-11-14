"""Leak-free SQPE baseline on raceform 2017-2025.
Features: only what is known before the off (conditions, race type, official rating,
field shape, draw, age, weight). Excluded: RPR, Topspeed, SP/odds, any result-derived value.
Train 2017-2024, test 2025. Evaluated by money at SP, level stakes."""
import re, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

df = pd.read_parquet("data/raceform_leakfree_src.parquet")

def dist_f(s):
    s = (s or "").replace("½", ".5")
    m = re.search(r"(\d+)m", s); f = re.search(r"(\d+(?:\.\d+)?)f", s)
    t = (int(m.group(1))*8 if m else 0) + (float(f.group(1)) if f else 0)
    return t if t > 0 else np.nan

def wgt(s):
    m = re.fullmatch(r"(\d+)-(\d+)", (s or "").strip())
    return int(m.group(1))*14 + int(m.group(2)) if m else np.nan

def num(s):
    try: return float(s)
    except: return np.nan

def cls(s):
    m = re.search(r"(\d)", s or ""); return float(m.group(1)) if m else np.nan

def going(s):
    g = (s or "").lower()
    for k, v in [("heavy", -1), ("good to soft", 0.5), ("soft", 0), ("good to firm", 1.5),
                 ("firm", 2), ("good", 1), ("standard", 1), ("yielding", 0.3), ("slow", 0.5), ("fast", 2)]:
        if k in g: return v
    return np.nan

def sp_dec(s):
    s = (s or "").strip().upper().rstrip("FJCFTFS ")
    if s in ("EVS", "EVENS"): return 2.0
    m = re.fullmatch(r"(\d+)/(\d+)", s)
    if m and int(m.group(2)) > 0: return int(m.group(1))/int(m.group(2)) + 1
    return np.nan

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
df["win"] = (df.pos == "1").astype(int)
df["sp_dec"] = df.sp.map(sp_dec)  # EVALUATION ONLY, never a feature

FEATS = ["dist_f","going_code","class_num","wgt_lbs","or_num","or_vs_field","or_missing",
         "field_size","draw_num","draw_pct","age_num","type_code"]
d = df.dropna(subset=["pos"]).copy()
d = d[d.pos.str.fullmatch(r"\d+")]           # finishers with a position only
d["year"] = d.date.str[:4].astype(int)
tr, te = d[d.year <= 2024], d[d.year == 2025]
print("train rows", len(tr), "test rows", len(te), "test races", te.race_id.nunique())

m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=2607)
m.fit(tr[FEATS], tr.win)
te = te.assign(p=m.predict_proba(te[FEATS])[:, 1])
print("test AUC (runner win)", round(roc_auc_score(te.win, te.p), 4))

def race_eval(g, pick_col):
    out = {"races":0,"hits":0,"stake":0.0,"ret":0.0}
    for _, r in g.groupby("race_id"):
        r = r.dropna(subset=["sp_dec"])
        if r.empty: continue
        pick = r.loc[r[pick_col].idxmax()]
        out["races"] += 1; out["stake"] += 1
        if pick.win == 1:
            out["hits"] += 1; out["ret"] += pick.sp_dec
    out["hit_rate"] = round(out["hits"]/out["races"], 4)
    out["roi_pct"] = round(100*(out["ret"]-out["stake"])/out["stake"], 2)
    return out

fav = te.assign(neg=-te.sp_dec)
print("MODEL top pick  ", race_eval(te, "p"))
print("FAVOURITE (SP)  ", race_eval(fav, "neg"))
print("note: favourite hit rate uses SP; model uses no price features")
