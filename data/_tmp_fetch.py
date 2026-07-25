import json, os, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(r"C:\Users\puror\velo-oracle-prime")
load_dotenv(ROOT / ".env")

out = {}

# New Build
nb_path = ROOT / "data/new_build/reports/two_lane_readiness_2026_06_23.json"
nb = json.loads(nb_path.read_text(encoding="utf-8"))
nb_index = {}
for sc in nb.get("race_day_scorecards", []):
    rid = str(sc.get("race_id",""))
    top3 = sc.get("lane_a_top3", [])
    if rid and top3:
        nb_index[rid] = {"horse": top3[0].get("horse"), "prob": top3[0].get("prob")}
out["nb"] = nb_index

# Supabase No-RPR
from supabase import create_client
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
rows = sb.table("velo_verdicts").select("race_id,full_analysis").gte("generated_at","2026-06-22T00:00:00").lte("generated_at","2026-06-22T23:59:59").execute()
norpr_index = {}
for row in (rows.data or []):
    rid = str(row.get("race_id",""))
    fa = row.get("full_analysis") or {}
    preds = fa.get("predictions",[]) if isinstance(fa,dict) else []
    if preds:
        best = max(preds, key=lambda p: float(p.get("sqpe_no_rpr_shadow_prob") or 0), default=None)
        if best:
            norpr_index[rid] = {"horse": best.get("horse"), "prob": float(best.get("sqpe_no_rpr_shadow_prob") or 0)}
out["norpr"] = norpr_index

Path(r"C:\Users\puror\velo-oracle-prime\data\_multimodel_june23_tmp.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
