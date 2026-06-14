import json
import re
from pathlib import Path

def debug_keys_v2():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    meetings = ps.get("meetings", {})
    print("Meetings root keys:", sorted(meetings.keys()))
    
    by_date = meetings.get("byDate", {})
    print("Dates in byDate:", sorted(by_date.keys()))

if __name__ == "__main__":
    debug_keys_v2()
