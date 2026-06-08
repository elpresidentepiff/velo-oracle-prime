import json
import re
from pathlib import Path

def inspect_html_structure():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/001_racecards_101_worcester_2026_06_06_919896_92b42469ed98.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    
    # pageProps -> initialState -> racePage -> data -> raceDate
    # But earlier it returned None.
    
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    print("Initial State Keys:", ps.keys())
    
    if "racePage" in ps:
        rp = ps["racePage"]
        print("RacePage Keys:", rp.keys())
        if "data" in rp:
            d = rp["data"]
            print("Data Keys:", d.keys())
            print(f"raceDate: {d.get('raceDate')}")
            print(f"courseName: {d.get('courseName')}")
            print(f"raceTime: {d.get('raceTime')}")

if __name__ == "__main__":
    inspect_html_structure()
