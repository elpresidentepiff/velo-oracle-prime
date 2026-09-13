import pandas as pd, numpy as np, re, os
SP=os.environ["SPD"]
c=pd.read_parquet(f"{SP}/runner_components.parquet"); hr=pd.read_parquet(f"{SP}/horse_runs.parquet"); rt=pd.read_parquet(f"{SP}/race_truth.parquet")
num=["velo_prime_prob","sqpe_v17_prob","improvement_score","market_deception_score","place_prob","rpdc_release_score","sqpe_no_rpr_shadow_prob","comment_intel_score","release_day_prob","longshot_prob","sp_dec","g_base_prob","spotlight_score"]
for k in num: c[k]=pd.to_numeric(c[k],errors="coerce")
norm=lambda s: re.sub(r"[^a-z0-9]","",re.sub(r"\s*\((gb|ire|fr|usa|ger|ity|aus|nz|saf|jpn|can|spa|swe|den|nor|bel|hol|pol|cze|hun|brz|arg|chi|uae|qat|ksa|tur)\)\s*$","",str(s).lower()))
c["hn"]=c.horse.map(norm)
# race date + off time
rt["race_id"]=rt.race_id.astype(str)
c=c.merge(rt[["race_id","race_date","off_time","course"]].drop_duplicates("race_id"),on="race_id",how="left")
def date_from_id(r):
    m=re.search(r"(20\d\d)[-_]?(\d\d)[-_]?(\d\d)",r); return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
c["race_date"]=c.race_date.fillna(c.race_id.map(date_from_id))
def off_from_id(r):
    m=re.search(r"_(\d{1,2})[.:]?(\d\d)$",r); return f"{m.group(1)}.{m.group(2)}" if m else None
c["off_time"]=c.off_time.fillna(c.race_id.map(off_from_id))
# results join 1: race_id + horse_id
hr["race_id"]=hr.race_id.astype(str); hr["horse_id"]=hr.horse_id.astype(str); hr["hn"]=hr.horse.map(norm)
hr["position_int"]=pd.to_numeric(hr.position_int,errors="coerce"); hr["sp_res"]=pd.to_numeric(hr.sp_dec,errors="coerce")
j1=c.merge(hr[["race_id","horse_id","position","position_int","sp_res","run_date"]],on=["race_id","horse_id"],how="left")
# join 2 (fallback): race date + normalised horse name
miss=j1.position.isna()
h2=hr.drop_duplicates(["run_date","hn"],keep=False)[["run_date","hn","position","position_int","sp_res","race_id"]].rename(columns={"race_id":"res_race_id"})
fb=j1.loc[miss,["race_date","hn"]].reset_index().merge(h2,left_on=["race_date","hn"],right_on=["run_date","hn"],how="inner").set_index("index")
for k in ["position","position_int","sp_res","run_date"]: j1.loc[fb.index,k]=fb[k]
j1["join_method"]=np.where(~miss,"id",np.where(j1.index.isin(fb.index),"name","none"))
# join 3 (fallback): local full-field results files (data/results/rp_results_*, data/results_*), never placed-only
import glob, json
loc=[]
for f in glob.glob("data/results/rp_results_2026_*.json")+glob.glob("data/results_2026_*.json"):
    d="-".join(re.search(r"(\d{4})_(\d\d)_(\d\d)",f).groups())
    try:
        jj=json.load(open(f)); rr=jj if isinstance(jj,list) else (jj.get("results") or jj.get("races") or [])
    except Exception: continue
    depth=sum(len(x.get("runners") or []) for x in rr)/max(len(rr),1)
    if depth<5: continue
    for x in rr:
        for u in x.get("runners") or []:
            if u.get("non_runner"): continue
            pos=str(u.get("position") or ""); 
            loc.append({"race_id":str(x.get("race_id")),"horse_id":str(u.get("horse_rp_uid") or u.get("horse_id") or ""),"hn":norm(u.get("horse")),
                        "run_date":d,"position":pos,"position_int":pd.to_numeric(pos,errors="coerce"),"sp_res":pd.to_numeric(u.get("sp_dec"),errors="coerce"),"src":f})
loc=pd.DataFrame(loc).drop_duplicates(["race_id","horse_id","hn"])
miss=j1.position.isna()
a=j1.loc[miss,["race_id","horse_id"]].reset_index().merge(loc.drop_duplicates(["race_id","horse_id"]),on=["race_id","horse_id"],how="inner").set_index("index")
for k in ["position","position_int","sp_res","run_date"]: j1.loc[a.index,k]=a[k]
j1.loc[a.index,"join_method"]="local_id"
miss=j1.position.isna()
l2=loc.drop_duplicates(["run_date","hn"],keep=False)
b=j1.loc[miss,["race_date","hn"]].reset_index().merge(l2,left_on=["race_date","hn"],right_on=["run_date","hn"],how="inner").set_index("index")
for k in ["position","position_int","sp_res","run_date"]: j1.loc[b.index,k]=b[k]
j1.loc[b.index,"join_method"]="local_name"
# if date still unknown use run_date from results
j1["race_date"]=j1.race_date.fillna(j1.run_date)
# pre-race filter: generated_at (UTC) must be before off time (BST = UTC+1)
def off_utc(row):
    d,o=row.race_date,row.off_time
    if not d or not o or not re.match(r"^\d{1,2}[.:]\d\d$",str(o)): return pd.NaT
    h,m=map(int,re.split(r"[.:]",str(o)));  h = h+12 if h<11 else h
    return pd.Timestamp(f"{d} {h:02d}:{m:02d}", tz="Europe/London").tz_convert("UTC")
races=j1.drop_duplicates("race_id")[["race_id","race_date","off_time","generated_at"]].copy()
races["off_utc"]=races.apply(off_utc,axis=1); races["gen"]=pd.to_datetime(races.generated_at,utc=True,format="ISO8601")
races["pre_race"]=np.where(races.off_utc.notna(), races.gen<races.off_utc, races.gen.dt.date.astype(str)<=races.race_date.astype(str))
races["pre_race_basis"]=np.where(races.off_utc.notna(),"off_time","date_only")
j1=j1.merge(races[["race_id","pre_race","pre_race_basis"]],on="race_id")
# race-level evaluability
g=j1.groupby("race_id")
rs=pd.DataFrame({"n":g.size(),"joined":g.position.apply(lambda s:s.notna().sum()),"winners":g.position_int.apply(lambda s:(s==1).sum()),
                 "pre_race":g.pre_race.first(),"date":g.race_date.first()})
rs["join_cov"]=rs.joined/rs.n
rs["evaluable"]=(rs.winners==1)&(rs.join_cov>=0.7)&rs.pre_race&(rs.n>=3)
j1=j1.merge(rs[["evaluable","join_cov"]],left_on="race_id",right_index=True)
print("runners",len(j1),"races",j1.race_id.nunique())
print("join method:",j1.join_method.value_counts().to_dict())
print("race filter: total",len(rs),"| winners==1:",(rs.winners==1).sum(),"| join_cov>=0.7:",(rs.join_cov>=0.7).sum(),"| pre_race:",rs.pre_race.sum(),"| evaluable:",rs.evaluable.sum())
print("pre_race basis:",races.pre_race_basis.value_counts().to_dict(),"| NOT pre-race races:",(~races.pre_race.astype(bool)).sum())
print("evaluable races by month:",rs[rs.evaluable].date.astype(str).str[:7].value_counts().sort_index().to_dict())
j1.to_parquet(f"{SP}/study.parquet",index=False)
