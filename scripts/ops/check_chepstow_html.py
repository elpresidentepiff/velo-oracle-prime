import json
import re
from pathlib import Path

def check_chepstow_html():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/008_racecards_12_chepstow_2026_06_06_920070_a95b83337acb.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    race_data = ps.get("racePage", {}).get("data", {}).get("race", {})
    
    print(f"File: {path.name}")
    print(f"Race ID: {race_data.get('raceId')}")
    print(f"Race Date: {race_data.get('raceDate')}")
    print(f"Course: {race_data.get('courseName')}")
    print(f"Time: {race_data.get('raceTime')}")

if __name__ == "__main__":
    check_chepstow_html()
