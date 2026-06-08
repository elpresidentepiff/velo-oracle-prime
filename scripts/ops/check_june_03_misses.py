import json
from pathlib import Path
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import load_index, _by_uid, _by_name

def check_misses():
    load_index()
    p = Path("data/racing_post_account_parsed/2026-06-03/racecard_injection.json")
    if not p.exists():
        print(f"Error: {p} not found")
        return
        
    data = json.load(p.open(encoding="utf-8"))
    races = data if isinstance(data, list) else data.get("races", [])
    
    miss_urls = []
    seen = set()
    total_runners = 0
    
    for race in races:
        for r in race.get("runners", []):
            total_runners += 1
            name = r.get("horse")
            uid_raw = r.get("horse_id")
            if not uid_raw: continue
            
            uid = int(uid_raw)
            exists = uid in _by_uid or (name and name.strip().lower() in _by_name)
            
            if not exists and uid not in seen:
                slug = name.lower().replace(" ", "-").replace("'", "").strip()
                url = f"https://www.racingpost.com/profile/horse/{uid}/{slug}/form"
                miss_urls.append(url)
                seen.add(uid)
                
    print(f"Total Runners: {total_runners}")
    print(f"June 3 Unique Misses: {len(miss_urls)}")
    
    out_path = Path("data/new_build/rp_scrape_queue/june_03_misses.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(miss_urls), encoding="utf-8")
    print(f"URL list written to {out_path}")

if __name__ == "__main__":
    check_misses()
