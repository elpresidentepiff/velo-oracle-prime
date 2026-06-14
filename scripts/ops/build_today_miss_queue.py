import json
from pathlib import Path
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import load_index, _by_uid, _by_name

def build_today_miss_queue():
    target_date = "2026_05_31"
    cache_path = Path(f"data/racecards_{target_date}_standard.json")
    
    if not cache_path.exists():
        print(f"Error: Cache file not found at {cache_path}")
        return

    load_index()
    
    with open(cache_path, "r", encoding="utf-8") as f:
        races = json.load(f)
        
    uk_ire_courses = ["Nottingham", "Fakenham", "Thirsk", "Listowel", "Kilbeggan"]
    
    miss_urls = []
    seen_ids = set()
    
    for race in races:
        if race.get("course") not in uk_ire_courses:
            continue
            
        for runner in race.get("runners", []):
            name = runner.get("horse")
            uid = runner.get("horse_id")
            
            # Check if in bank
            exists = False
            if uid and int(uid) in _by_uid:
                exists = True
            elif name and name.strip().lower() in _by_name:
                exists = True
                
            if not exists and uid not in seen_ids:
                # Build URL: https://www.racingpost.com/profile/horse/UID/NAME/form
                slug = name.lower().replace(" ", "-").replace("'", "")
                url = f"https://www.racingpost.com/profile/horse/{uid}/{slug}/form"
                miss_urls.append(url)
                seen_ids.add(uid)
                
    print(f"Targeted misses for today: {len(miss_urls)}")
    
    out_path = Path("data/new_build/rp_scrape_queue/today_misses_urls.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(miss_urls), encoding="utf-8")
    print(f"URL list written to {out_path}")

if __name__ == "__main__":
    build_today_miss_queue()
