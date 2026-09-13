import os, json, urllib.request, urllib.parse, time, sys
import pandas as pd
from dotenv import load_dotenv; load_dotenv(".env")
U=os.environ["SUPABASE_URL"]; K=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
H={"apikey":K,"Authorization":f"Bearer {K}"}
KEEP=["horse","horse_id","velo_prime_prob","sqpe_v17_prob","improvement_score","market_deception_score","place_prob","longshot_prob",
      "release_day_prob","comment_intel_score","rpdc_release_score","rpdc_primary_tag","sqpe_no_rpr_shadow_prob","sp_dec","g_base_prob",
      "spotlight_score","ensemble_version","confidence_level","decision_tier","horse_state","race_archetype","mpi","chaos_bloom","nds_score",
      "or_missing","rpr_missing","ts_missing","horse_recent_avg_pos","trainer_course_win_pct","hdta_win_pct","g_shadow_multiplier"]
rows=[]; off=0; page=200
sel="race_id,generated_at,region,race_type,predicted_field_size,preds:full_analysis->predictions"
while True:
    url=f"{U}/rest/v1/velo_verdicts?select={urllib.parse.quote(sel, safe=',:>-_')}&order=generated_at.asc,race_id.asc&limit={page}&offset={off}"
    for attempt in range(4):
        try: b=json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=H),timeout=120).read()); break
        except Exception as e: print("retry",off,e,flush=True); time.sleep(5)
    else: sys.exit("failed")
    for v in b:
        preds=v.get("preds")
        if not isinstance(preds,list): continue
        for p in preds:
            if not isinstance(p,dict): continue
            r={k:p.get(k) for k in KEEP}
            for k in ("active_components",): r[k]=",".join(p.get(k) or []) if isinstance(p.get(k),list) else p.get(k)
            r.update(race_id=str(v["race_id"]), pred_race_id=str(p.get("race_id")), generated_at=v["generated_at"], region=v.get("region"), race_type=v.get("race_type"), field_size=v.get("predicted_field_size"))
            rows.append(r)
    off+=len(b); print("verdicts",off,"runners",len(rows),flush=True)
    if len(b)<page: break
df=pd.DataFrame(rows)
for c in ["horse_state","rpdc_primary_tag","race_archetype","confidence_level","decision_tier","ensemble_version","horse_id","horse","mpi","chaos_bloom"]:
    if c in df: df[c]=df[c].astype(str)
df.to_parquet(os.environ["OUT"], index=False); print("WROTE", len(df), "runners", df.race_id.nunique(), "races")
