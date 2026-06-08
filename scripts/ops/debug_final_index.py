import json
import re
from pathlib import Path

def debug_final_index():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    print("KEYS in initialState:", sorted(ps.keys()))
    
    # Let's find where 'Navan' or 'Punchestown' is
    if 'Navan' in content:
        print("STRING 'Navan' FOUND in HTML")
        start = content.find('Navan')
        print("Context:", content[start:start+500])
    
    # Check 'racecards' object specifically
    rc = ps.get("racecards", {})
    print("\nRacecards structure keys:", sorted(rc.keys()))
    if 'meetings' in rc:
        print(f"Meetings type in racecards: {type(rc['meetings'])}")
        if isinstance(rc['meetings'], list):
            print(f"Meetings count: {len(rc['meetings'])}")
            if len(rc['meetings']) > 0:
                print("First meeting:", rc['meetings'][0])

if __name__ == "__main__":
    debug_final_index()
