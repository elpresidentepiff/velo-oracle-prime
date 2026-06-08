import json
import re
from pathlib import Path

def inspect_race_keys():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/001_racecards_101_worcester_2026_06_06_919896_92b42469ed98.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    race_data = ps.get("racePage", {}).get("data", {}).get("race", {})
    
    print("Race Keys:", race_data.keys())
    print(f"raceDate: {race_data.get('raceDate')}")
    print(f"courseName: {race_data.get('courseName')}")
    print(f"raceTime: {race_data.get('raceTime')}")

if __name__ == "__main__":
    inspect_race_keys()
