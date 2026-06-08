import json
import re
from pathlib import Path

def debug_jockeys():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/001_racecards_101_worcester_2026_06_06_919896_92b42469ed98.html")
    if not path.exists():
        print(f"Error: File not found {path}")
        return

    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    if not match:
        print("Error: __NEXT_DATA__ not found")
        return

    data = json.loads(match.group(1))
    race_page = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("racePage", {}).get("data", {})
    runners = race_page.get("runners", [])

    print(f"Total Runners: {len(runners)}")
    for r in runners[:10]:
        print(f"Horse: {r.get('horseName')} | Jockey: {r.get('jockeyName')} | jockeyId: {r.get('jockeyId')}")

if __name__ == "__main__":
    debug_jockeys()
