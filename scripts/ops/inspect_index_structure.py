import json
import re
from pathlib import Path

def inspect_index_structure():
    path = Path("data/racing_post_account_raw/index-2026-06-06/2026-06-06/001_racecards_2026_06_06_f06e551f3a55.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    
    props = data.get("props", {})
    page_props = props.get("pageProps", {})
    initial_state = page_props.get("initialState", {})
    
    print("Initial State Keys:", sorted(initial_state.keys()))
    
    if "racecards" in initial_state:
        print("Racecards Keys:", sorted(initial_state["racecards"].keys()))
        meetings = initial_state["racecards"].get("meetings")
        print(f"Meetings type: {type(meetings)}")
        if isinstance(meetings, list):
            print(f"Meetings length: {len(meetings)}")
        elif isinstance(meetings, dict):
            print(f"Meetings keys: {sorted(meetings.keys())}")

if __name__ == "__main__":
    inspect_index_structure()
