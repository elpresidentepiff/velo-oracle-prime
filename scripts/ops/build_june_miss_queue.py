import json
from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import load_index, _by_uid, _by_name

def build_upcoming_miss_queue():
    load_index()
    
    PARSED_DIR = Path("data/racing_post_account_parsed")
    # All date-named injection files for June
    injection_files = list(PARSED_DIR.glob("2026-06-*/racecard_injection.json"))
    
    miss_urls = []
    seen_ids = set()
    
    for f in injection_files:
        print(f"Checking {f.parent.name}...")
        with open(f, "r", encoding="utf-8") as file:
            data = json.load(file)
            races = data if isinstance(data, list) else data.get("races", [])
            
            for race in races:
                for runner in race.get("runners", []):
                    name = runner.get("horse")
                    uid = runner.get("horse_id")
                    
                    if not uid: continue
                    uid = int(uid)
                    
                    # Check if in bank
                    exists = False
                    if uid in _by_uid:
                        exists = True
                    elif name and name.strip().lower() in _by_name:
                        exists = True
                        
                    if not exists and uid not in seen_ids:
                        # Build URL
                        slug = name.lower().replace(" ", "-").replace("'", "")
                        url = f"https://www.racingpost.com/profile/horse/{uid}/{slug}/form"
                        miss_urls.append(url)
                        seen_ids.add(uid)
                
    print(f"Total targeted misses for June 2-7: {len(miss_urls)}")
    
    out_path = Path("data/new_build/rp_scrape_queue/june_recovery_urls.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(miss_urls), encoding="utf-8")
    print(f"URL list written to {out_path}")

if __name__ == "__main__":
    build_upcoming_miss_queue()
