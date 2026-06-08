import json
import re
from pathlib import Path

def debug_index_jockeys():
    path = Path("data/racing_post_account_raw/index-2026-06-06/2026-06-06/001_racecards_2026_06_06_f06e551f3a55.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    if not match:
        print("Error: __NEXT_DATA__ not found in index")
        return

    data = json.loads(match.group(1))
    # Index pages have a different structure
    meetings = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("racecards", {}).get("meetings", [])
    
    print(f"Total Meetings in Index: {len(meetings)}")
    for m in meetings:
        if m.get("courseName") == "Worcester":
            print("Found Worcester Meeting in Index")
            for r in m.get("races", []):
                if r.get("raceId") == 919896:
                    print(f"Found Race 919896: {r.get('raceTitle')}")
                    # Does the index have runners?
                    runners = r.get("runners", [])
                    print(f"Runners in index for this race: {len(runners)}")

if __name__ == "__main__":
    debug_index_jockeys()
