import json
import re
from pathlib import Path

def check_html_date():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/001_racecards_101_worcester_2026_06_06_919896_92b42469ed98.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    
    race_page = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("racePage", {}).get("data", {})
    print(f"File: {path.name}")
    print(f"Race Date: {race_page.get('raceDate')}")
    print(f"Course: {race_page.get('courseName')}")
    print(f"Time: {race_page.get('raceTime')}")

if __name__ == "__main__":
    check_html_date()
