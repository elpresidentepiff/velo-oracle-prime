import os, json, urllib.request, time, sys
import pandas as pd
from dotenv import load_dotenv; load_dotenv(".env")
U=os.environ["SUPABASE_URL"]; K=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
H={"apikey":K,"Authorization":f"Bearer {K}"}
def pull(table, sel, filt, order, out):
    rows=[]; off=0; page=1000
    while True:
        url=f"{U}/rest/v1/{table}?select={sel}&{filt}&order={order}&limit={page}&offset={off}"
        for a in range(4):
            try: b=json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=H),timeout=120).read()); break
            except Exception as e: print("retry",table,off,e,flush=True); time.sleep(5)
        else: sys.exit("fail")
        rows+=b; off+=len(b)
        if len(b)<page: break
    df=pd.DataFrame(rows); df.to_parquet(out,index=False); print(table, len(df), flush=True)
SPD=os.environ["SPD"]
pull("racing_horse_runs","race_id,horse_id,horse,run_date,course,position,position_int,sp_dec","run_date=gte.2026-04-01","run_date.asc,race_id.asc,horse_id.asc",f"{SPD}/horse_runs.parquet")
pull("velo_race_truth","race_id,race_date,course,off_time,scored_at,verdict_generated_at,finish_pos,winner_name,actual_winner_sp,result_outcome","race_date=gte.2026-04-01","race_date.asc,race_id.asc",f"{SPD}/race_truth.parquet")
