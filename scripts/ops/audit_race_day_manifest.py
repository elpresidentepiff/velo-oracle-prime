
import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def audit_manifest(target_date: str):
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    token = target_date.replace("-", "_")
    
    print(f"VÉLØ Race-Day Manifest Audit — {target_date}")
    print("=" * 60)
    
    # 1. Check local files
    std_path = ROOT / "data" / f"racecards_{token}_standard.json"
    merged_files = list(ROOT.glob(f"data/racecard_merged/*_{target_date}.json"))
    
    print(f"A. Standard Card Exists: {'YES' if std_path.exists() else 'NO'}")
    print(f"B. Merged Files Count:   {len(merged_files)}")
    
    # 2. Extract Race IDs
    race_ids = []
    if std_path.exists():
        with open(std_path) as f:
            data = json.load(f)
            # Use 'racecards' key instead of 'races'
            race_ids.extend([r["race_id"] for r in data.get("racecards", []) if r.get("race_id")])
            
    for mf in merged_files:
        with open(mf) as f:
            data = json.load(f)
            for time, race in data.get("races", {}).items():
                if race.get("race_id"):
                    race_ids.append(race["race_id"])
                    
    unique_ids = list(set(race_ids))
    print(f"C. Unique Race IDs:      {len(unique_ids)}")
    
    if not unique_ids:
        print("FAIL: No race manifest found.")
        return

    # 3. Check Supabase Verdicts
    v_resp = sb.table("velo_verdicts").select("race_id,full_analysis").in_("race_id", unique_ids).execute()
    verdicts = v_resp.data
    print(f"D. Verdicts Found:       {len(verdicts)} / {len(unique_ids)}")
    
    # 4. Coverage Metrics
    stats = {
        "fa": 0, "horse_id": 0, "trainer_id": 0, "jockey_id": 0, "course_id": 0, "dist": 0
    }
    
    for v in verdicts:
        fa = v.get("full_analysis") or {}
        predictions = []
        if isinstance(fa, dict) and "predictions" in fa:
            predictions = fa["predictions"]
        elif isinstance(fa, list):
            predictions = fa
            
        if predictions:
            stats["fa"] += 1
            top = predictions[0]
            if top.get("horse_id"): stats["horse_id"] += 1
            if top.get("trainer_id"): stats["trainer_id"] += 1
            if top.get("jockey_id"): stats["jockey_id"] += 1
            if top.get("course_id"): stats["course_id"] += 1
            if top.get("distance_f") or top.get("dist_f"): stats["dist"] += 1

    print(f"E. Full Analysis Coverage: {stats['fa']}")
    print(f"F. Horse ID Coverage:     {stats['horse_id']}")
    print(f"G. Trainer ID Coverage:   {stats['trainer_id']}")
    print(f"H. Jockey ID Coverage:    {stats['jockey_id']}")
    print(f"I. Course ID Coverage:    {stats['course_id']}")
    print(f"J. Distance Coverage:     {stats['dist']}")
    
    possible = min(stats["trainer_id"], stats["jockey_id"], stats["course_id"])
    print(f"K. Enrichment Possible:   {possible}")
    
    if len(verdicts) < len(unique_ids):
        print("\nWARNING: Some manifest races are missing verdicts in Supabase.")
    if possible == 0:
        print("\nFAIL: Cannot enrich. Critical join IDs (trainer/jockey/course) are missing from verdicts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    audit_manifest(args.date)
