import os
import json
from supabase import create_client
from pathlib import Path

# Setup
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
sb = create_client(URL, KEY)

COMMIT = "023f3f380822bc2d32835b4b2ebccad9038e1fea"

def audit_features():
    # 1. Get sample Tier X races
    res = sb.table("velo_verdicts").select("race_id, decision_tier, full_analysis").eq("git_commit_sha", COMMIT).eq("decision_tier", "X").limit(5).execute()
    
    print("FEATURE COVERAGE AUDIT: TIER X SAMPLES")
    print("=" * 60)
    
    for row in res.data:
        rid = row["race_id"]
        fa = row["full_analysis"]
        if isinstance(fa, str): fa = json.loads(fa)
        
        preds = fa.get("predictions", [])
        if not preds:
            print(f"Race {rid}: No predictions found in full_analysis")
            continue
            
        top = preds[0]
        print(f"\nRace {rid}: {top.get('horse')}")
        print(f"  SQPE Prob:   {top.get('sqpe_v17_prob')}")
        print(f"  VP Final:    {top.get('velo_prime_prob')}")
        print(f"  MDS:         {top.get('market_deception_score')}")
        print(f"  Improvement: {top.get('improvement_score')}")
        print(f"  Active:      {top.get('active_components')}")
        print(f"  Excluded:    {top.get('excluded_from_ensemble')}")
        
        # Check for flag indicators of missing data
        flags = top.get("verdict_flags", [])
        print(f"  Flags:       {flags}")

    # 2. Check the standard cache for one of these races to see raw feature presence
    print("\n\nRAW CACHE AUDIT")
    print("=" * 60)
    cache_path = Path("data/racecards_2026_05_27_standard.json")
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
        races = cache.get("racecards", [])
        if races:
            sample = races[0]
            print(f"Sample Race from Cache: {sample.get('course')} {sample.get('race_time')}")
            runners = sample.get("runners", [])
            if runners:
                r1 = runners[0]
                print(f"  Runner: {r1.get('horse')}")
                print(f"  OR:     {r1.get('official_rating')}")
                print(f"  RPR:    {r1.get('rpr')}")
                print(f"  TS:     {r1.get('ts') or r1.get('topspeed')}")
                print(f"  SP:     {r1.get('sp') or r1.get('odds')}")
                print(f"  Keys:   {list(r1.keys())[:10]}")

if __name__ == "__main__":
    audit_features()
