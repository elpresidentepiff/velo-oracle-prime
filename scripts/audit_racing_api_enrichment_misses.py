
import os
import json
import argparse
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def audit_misses(target_date: str):
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    token = target_date.replace("-", "_")
    
    # Load manifest
    card_path = ROOT / "data" / f"racecards_{token}_standard.json"
    if not card_path.exists():
        print(f"No card found at {card_path}")
        return
        
    with open(card_path) as f:
        card_data = json.load(f)
        races = card_data.get("racecards", [])

    # Load adapter
    from src.velo.racing_api_stat_adapter import RacingAPIStatAdapter, races_distance_to_dist
    adapter = RacingAPIStatAdapter.from_supabase()

    audit_results = []
    
    for race in races:
        course = race.get("course")
        course_id = race.get("course_id")
        dist_raw = race.get("distance_f")
        dist_norm = races_distance_to_dist(dist_raw)
        
        for runner in race.get("runners", []):
            horse = runner.get("horse")
            t_id = runner.get("trainer_id")
            j_id = runner.get("jockey_id")
            
            enrichment = adapter.enrich_runner(runner, race)
            status = enrichment["racing_api_stat_status"]
            
            # Detailed checks
            t_course_match = adapter.trainer_course_cache.get((t_id, course.lower())) if t_id and course else None
            j_course_match = adapter.jockey_course_cache.get((j_id, course.lower())) if j_id and course else None
            t_dist_match = adapter.trainer_distance_cache.get((t_id, dist_norm.lower())) if t_id and dist_norm else None
            j_dist_match = adapter.jockey_distance_cache.get((j_id, dist_norm.lower())) if j_id and dist_norm else None
            
            reason = "OK"
            if not t_id: reason = "missing_trainer_id"
            elif not j_id: reason = "missing_jockey_id"
            elif not dist_norm: reason = "dist_norm_fail"
            elif status == "MISSING": reason = "no_db_stats_at_threshold"
            
            audit_results.append({
                "horse": horse,
                "status": status,
                "reason": reason,
                "t_id": t_id,
                "j_id": j_id,
                "course": course,
                "dist_raw": dist_raw,
                "dist_norm": dist_norm,
                "t_course": "YES" if t_course_match else "NO",
                "j_course": "YES" if j_course_match else "NO",
                "t_dist": "YES" if t_dist_match else "NO",
                "j_dist": "YES" if j_dist_match else "NO"
            })

    df = pd.DataFrame(audit_results)
    
    # Save artifacts
    md_path = ROOT / "data" / f"racing_api_enrichment_miss_audit_{token}.md"
    json_path = ROOT / "data" / f"racing_api_enrichment_miss_audit_{token}.json"
    
    df.to_markdown(md_path, index=False)
    df.to_json(json_path, orient="records", indent=2)
    
    print(f"Audit complete for {target_date}")
    print(f"Total runners: {len(df)}")
    print(df["status"].value_counts())
    
    print("\nTarget Runners Analysis:")
    targets = ["Great Valley", "Slipway"]
    print(df[df["horse"].isin(targets)].to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    audit_misses(args.date)
