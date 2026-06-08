import json
from pathlib import Path
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import load_index, _by_uid

def audit_coverage(date_str: str):
    load_index()
    p = Path(f"data/racing_post_account_parsed/{date_str}/racecard_injection.json")
    if not p.exists():
        print(f"Error: {p} not found")
        return
        
    data = json.load(p.open(encoding="utf-8"))
    races = data if isinstance(data, list) else data.get("races", [])
    
    venue_stats = {}
    total_hits = 0
    total_runners = 0
    
    for race in races:
        venue = race.get("course", "Unknown")
        if venue not in venue_stats:
            venue_stats[venue] = {"hits": 0, "total": 0}
            
        for r in race.get("runners", []):
            uid_raw = r.get("horse_id")
            if not uid_raw: continue
            
            total_runners += 1
            venue_stats[venue]["total"] += 1
            if int(uid_raw) in _by_uid:
                total_hits += 1
                venue_stats[venue]["hits"] += 1
                
    print(f"\n--- {date_str} Coverage Audit ---")
    print(f"{'Venue':<25} | {'Coverage':<10}")
    print("-" * 40)
    for v, s in sorted(venue_stats.items()):
        pct = (s["hits"]/s["total"]*100) if s["total"] > 0 else 0
        print(f"{v:<25} | {s['hits']}/{s['total']} ({pct:.1f}%)")
    
    total_pct = (total_hits/total_runners*100) if total_runners > 0 else 0
    print("-" * 40)
    print(f"{'TOTAL':<25} | {total_hits}/{total_runners} ({total_pct:.1f}%)")

if __name__ == "__main__":
    audit_coverage("2026-06-03")
