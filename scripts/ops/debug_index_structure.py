import json
import re
from pathlib import Path

def debug_structure():
    path = Path("data/racing_post_account_raw/index-2026-06-07/2026-06-07/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    # 1. Check 'meetings'
    m_data = ps.get("meetings", {})
    print(f"Meetings type: {type(m_data)}")
    if isinstance(m_data, dict):
        keys = list(m_data.keys())
        print(f"Meetings keys: {keys[:5]}")
        if keys:
            print(f"Sample meeting: {m_data[keys[0]]}")
            
    # 2. Check 'races'
    r_data = ps.get("races", {})
    print(f"Races type: {type(r_data)}")
    if isinstance(r_data, dict):
        keys = list(r_data.keys())
        print(f"Races keys: {keys[:5]}")
        if keys:
            print(f"Sample race: {r_data[keys[0]]}")

if __name__ == "__main__":
    debug_structure()
