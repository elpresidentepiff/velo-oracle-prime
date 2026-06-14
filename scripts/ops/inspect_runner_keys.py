import json
import re
from pathlib import Path

def inspect_runner_structure():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/001_racecards_101_worcester_2026_06_06_919896_92b42469ed98.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    runners = data['props']['pageProps']['initialState']['racePage']['data']['runners']
    
    # Let's see all keys for the first runner
    first_runner = runners[0]
    print(f"Horse: {first_runner.get('horseName')}")
    print("Keys found in runner object:")
    print(sorted(first_runner.keys()))
    
    print("\nAttempting to find any jockey-related fields:")
    for key, val in first_runner.items():
        if 'jockey' in key.lower():
            print(f"{key}: {val}")

if __name__ == "__main__":
    inspect_runner_structure()
