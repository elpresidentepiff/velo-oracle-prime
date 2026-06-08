import json
import re
from pathlib import Path

def build_missing_profile_urls():
    ROOT = Path(".")
    URL_LIST_DIR = ROOT / "data" / "racing_post_url_lists"
    PASSPORT_PATH = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
    
    # 1. Load existing horse IDs from passport bank
    existing_horse_ids = set()
    if PASSPORT_PATH.exists():
        with PASSPORT_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    hid = data.get("horse_rp_uid")
                    if hid:
                        existing_horse_ids.add(str(hid))
    print(f"Loaded {len(existing_horse_ids)} existing horse IDs from bank.")

    # 2. Scan injection files for June 5-7
    target_dates = ["2026-06-05", "2026-06-06", "2026-06-07"]
    missing_horses = {} # horse_id -> url
    
    for date in target_dates:
        injection_path = ROOT / "data" / "racing_post_account_parsed" / date / "racecard_injection.json"
        if not injection_path.exists():
            print(f"Warning: Injection file missing for {date}")
            continue
            
        with injection_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            
        for race in data.get("races", []):
            for runner in race.get("runners", []):
                if runner.get("non_runner"):
                    continue
                    
                hid = str(runner.get("horse_id"))
                if hid not in existing_horse_ids:
                    h_url = runner.get("horse_url")
                    if h_url:
                        # Extract name and ID to build form URL
                        # /profile/horse/8498832/trooper#race-id=920030
                        m = re.match(r'/profile/horse/(\d+)/([^/#]+)', h_url)
                        if m:
                            form_url = f"https://www.racingpost.com/profile/horse/{m.group(1)}/{m.group(2)}/form"
                            missing_horses[hid] = form_url
                            
    print(f"Identified {len(missing_horses)} missing horse profiles.")
    
    # 3. Write full list
    all_urls = sorted(list(missing_horses.values()))
    full_list_path = URL_LIST_DIR / "rp_profiles_jun05-07_missing.txt"
    full_list_path.write_text("\n".join(all_urls) + "\n", encoding="utf-8")
    print(f"Wrote full list to {full_list_path}")
    
    # 4. Chunk into batches of 250
    batch_size = 250
    for i in range(0, len(all_urls), batch_size):
        batch_num = (i // batch_size) + 1
        batch_urls = all_urls[i : i + batch_size]
        batch_path = URL_LIST_DIR / f"rp_profiles_jun05-07_batch_{batch_num}.txt"
        batch_path.write_text("\n".join(batch_urls) + "\n", encoding="utf-8")
        print(f"Wrote batch {batch_num} ({len(batch_urls)} URLs) to {batch_path}")

if __name__ == "__main__":
    build_missing_profile_urls()
