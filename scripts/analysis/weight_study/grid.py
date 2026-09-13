import sys, os, itertools, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from sim import load, COMP
SP=sys.argv[1]
s=load(SP).sort_values(["race_id","horse"]).reset_index(drop=True)
KEYS=["sqpe","imp","mds","place"]
X=np.column_stack([s[COMP[k]].astype(float).to_numpy() for k in KEYS])
OK=~np.isnan(X)
for j,k in enumerate(KEYS):
    if k=="sqpe": continue
    rng=s.groupby("race_id")[COMP[k]].transform(lambda v: v.max()-v.min()).to_numpy()
    OK[:,j]&=~(rng<1e-6)
X=np.nan_to_num(X)
race_codes, starts = np.unique(s.race_id.to_numpy(), return_index=True)
ridx=np.repeat(np.arange(len(starts)), np.diff(np.append(starts,len(s))))
win=s.win.to_numpy(); top3=s.top3.to_numpy(); sp=s.sp_res.to_numpy(float)
month_of_race=s.groupby("race_id").month.first().reindex(race_codes).to_numpy()
def race_metrics(w):
    w=np.asarray(w,float); num=(X*OK)@w; den=OK@w
    sc=np.where(den>0,num/den,-1.0)
    mx=np.maximum.reduceat(sc,starts); is_max=sc>=mx[ridx]-1e-12
    first=np.zeros(len(sc),bool); c=np.cumsum(is_max); c0=np.append(0,c[starts[1:]-1]) if len(starts)>1 else np.array([0])
    first=is_max & ((c-c0[ridx])==1)
    tot=np.add.reduceat(np.clip(sc,0,None),starts)
    wi=np.where(win==1)[0]; p_w=np.clip(sc[wi],1e-6,None)/np.maximum(tot[ridx[wi]],1e-9)
    rank_w=np.array([ (sc[starts[r]:(starts[r+1] if r+1<len(starts) else len(sc))] > sc[i]).sum()+1 for i,r in zip(wi,ridx[wi])])
    ti=np.where(first)[0]
    R=len(starts)
    top_win=np.zeros(R); top_win[ridx[ti]]=win[ti]
    top_t3=np.zeros(R); top_t3[ridx[ti]]=top3[ti]
    top_sp=np.full(R,np.nan); top_sp[ridx[ti]]=sp[ti]
    logs=np.full(R,np.nan); logs[ridx[wi]]=np.log(np.clip(p_w,1e-4,1))
    wr=np.full(R,np.nan); wr[ridx[wi]]=rank_w
    return top_win, top_t3, top_sp, logs, wr
def summarise(m, mask):
    tw,t3,tsp,lg,wr=[a[mask] for a in m]
    ok=~np.isnan(tsp)&(tsp>1)
    return dict(races=int(mask.sum()), sr=tw.mean(), top3=t3.mean(), roi=((tw[ok]*tsp[ok]).sum()-ok.sum())/max(ok.sum(),1), logscore=np.nanmean(lg), winner_top3=np.mean(wr<=3))
grid=[w for w in itertools.product(np.arange(0,1.0001,0.05),repeat=3) if sum(w)<=1.0001]
grid=[(round(a,2),round(b,2),round(c,2),round(1-a-b-c,2)) for a,b,c in grid]
grid=[g for g in grid if g[0]+g[1]+g[2]+g[3]>0]
LIVE_W=(0.45/0.67,0.12/0.67,0.10/0.67,0.0)
cache={}
def M(w):
    if w not in cache: cache[w]=race_metrics(w)
    return cache[w]
allmask=np.ones(len(starts),bool)
print("grid size",len(grid),flush=True)
# full-sample table for reference points
ref={"LIVE (0.45/0.12/0.10)":LIVE_W,"sqpe only":(1,0,0,0),"imp only":(0,1,0,0),"mds only":(0,0,1,0),"place only":(0,0,0,1),"legacy-like (sqpe.45 mds.10 place.08)":(0.45/0.63,0,0.10/0.63,0.08/0.63)}
for n,w in ref.items(): print(f"{n:40s}", {k:round(v,4) for k,v in summarise(M(w),allmask).items()},flush=True)
# rolling-origin: train months < test month
months=sorted(set(month_of_race)); results=[]
for tm in ["2026-06","2026-07","2026-08","2026-09"]:
    tr=np.isin(month_of_race,[m for m in months if m<tm]); te=month_of_race==tm
    scored=[(summarise(M(w),tr),w) for w in grid]
    best_ls=max(scored,key=lambda x:x[0]["logscore"])[1]; best_sr=max(scored,key=lambda x:(x[0]["sr"],x[0]["logscore"]))[1]
    for label,w in [("LIVE",LIVE_W),("best_train_logscore",best_ls),("best_train_sr",best_sr)]:
        r=summarise(M(w),te); r.update(test_month=tm,rule=label,w=w,train_races=int(tr.sum())); results.append(r)
    print(tm,"train",int(tr.sum()),"best_ls",best_ls,"best_sr",best_sr,flush=True)
df=pd.DataFrame(results); df.to_csv(f"{SP}/rolling_oos.csv",index=False)
print(df[["test_month","rule","w","races","sr","top3","roi","logscore","winner_top3"]].round(4).to_string())
# pooled OOS vs LIVE with paired bootstrap on races
rng=np.random.default_rng(7)
for rule in ["best_train_logscore","best_train_sr"]:
    tw_live=[];tw_new=[];ret_live=[];ret_new=[];ls_live=[];ls_new=[]
    for tm in ["2026-06","2026-07","2026-08","2026-09"]:
        te=month_of_race==tm; wnew=df[(df.test_month==tm)&(df.rule==rule)].w.iloc[0]
        for store,w in ((("L"),LIVE_W),(("N"),wnew)):
            tw,t3,tsp,lg,wr=[a[te] for a in M(w)]
            ret=np.where(~np.isnan(tsp)&(tsp>1), tw*tsp-1, np.nan)
            if store=="L": tw_live+=list(tw); ret_live+=list(ret); ls_live+=list(lg)
            else: tw_new+=list(tw); ret_new+=list(ret); ls_new+=list(lg)
    a=np.array(tw_new)-np.array(tw_live); rr=np.array(ret_new)-np.array(ret_live); ll=np.array(ls_new)-np.array(ls_live)
    n=len(a); bs=[]; bsr=[]
    for _ in range(4000):
        i=rng.integers(0,n,n); bs.append(a[i].mean()); bsr.append(np.nanmean(rr[i]))
    print(f"POOLED OOS {rule}: races={n} SR live={np.mean(tw_live):.4f} new={np.mean(tw_new):.4f} diff={a.mean():+.4f} 95%CI[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}] "
          f"| ROI live={np.nanmean(ret_live):+.4f} new={np.nanmean(ret_new):+.4f} diff 95%CI[{np.percentile(bsr,2.5):+.4f},{np.percentile(bsr,97.5):+.4f}] | logscore diff={np.nanmean(ll):+.4f}")
# full-sample landscape (descriptive, in-sample): top 10 by logscore and by SR
full=[(summarise(M(w),allmask),w) for w in grid]
print("\nIN-SAMPLE top 8 by logscore:")
for r,w in sorted(full,key=lambda x:-x[0]["logscore"])[:8]: print("  ",w,{k:round(v,4) for k,v in r.items()})
print("IN-SAMPLE top 8 by SR:")
for r,w in sorted(full,key=lambda x:(-x[0]["sr"],-x[0]["logscore"]))[:8]: print("  ",w,{k:round(v,4) for k,v in r.items()})
json.dump([{"w":w,**{k:float(v) for k,v in r.items()}} for r,w in full], open(f"{SP}/grid_full.json","w"))
