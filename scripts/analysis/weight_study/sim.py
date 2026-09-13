import pandas as pd, numpy as np
def load(SP):
    s=pd.read_parquet(f"{SP}/study.parquet")
    s=s[s.evaluable].copy()
    s["win"]=(s.position_int==1).astype(int); s["top3"]=(s.position_int<=3).astype(int)
    s["month"]=s.race_date.astype(str).str[:7]
    return s
COMP={"sqpe":"sqpe_v17_prob","imp":"improvement_score","mds":"market_deception_score","place":"place_prob","rpdc":"rpdc_release_score",
      "norpr":"sqpe_no_rpr_shadow_prob","comment":"comment_intel_score","release":"release_day_prob","longshot":"longshot_prob"}
def score(s, w):
    """Live-engine blend: weighted average over components that are non-null for the runner,
    with a component dropped for a whole race when it is constant across the field."""
    num=np.zeros(len(s)); den=np.zeros(len(s))
    for k,wt in w.items():
        if wt==0: continue
        col=COMP[k]; x=s[col].astype(float)
        rng=s.groupby("race_id")[col].transform(lambda v: v.max()-v.min() if v.notna().sum()>=2 else np.nan)
        ok=x.notna() & ~(rng<1e-6)
        if k=="sqpe": ok=x.notna()          # sqpe is never killed in the live engine
        num+=np.where(ok, wt*x.fillna(0), 0); den+=np.where(ok, wt, 0)
    return pd.Series(np.where(den>0, num/den, np.nan), index=s.index)
def evaluate(s, sc):
    d=s.assign(sc=sc)
    d["rk"]=d.groupby("race_id").sc.rank(ascending=False, method="first")
    tot=d.groupby("race_id").sc.transform("sum")
    d["p"]=d.sc/tot
    top=d[d.rk==1]
    roi_rows=top[top.sp_res.notna() & (top.sp_res>1)]
    ret=(roi_rows.win*roi_rows.sp_res).sum()-len(roi_rows)
    wp=d[d.win==1].p.clip(1e-4,1)
    return {"races":len(top),"sr":top.win.mean(),"top3_rate":top.top3.mean(),"roi":ret/max(len(roi_rows),1),
            "winner_in_top3":(d[d.win==1].rk<=3).mean(),"logscore":np.log(wp).mean(),"mean_winner_rank":d[d.win==1].rk.mean()}
LIVE={"sqpe":0.45,"imp":0.12,"mds":0.10}
