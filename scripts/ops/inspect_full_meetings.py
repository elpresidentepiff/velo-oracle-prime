import json
import re
from pathlib import Path

def inspect_full_meetings():
    path = Path('data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html')
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get('props', {}).get('pageProps', {}).get('initialState', {})
    
    # 1. Check byDate
    by_date = ps.get('meetings', {}).get('byDate', {})
    print(f'Dates in meetings.byDate: {list(by_date.keys())}')
    
    # 2. Check for 'Navan' or 'Punchestown' in the whole ps dict
    ps_str = json.dumps(ps)
    for target in ['Navan', 'Punchestown', 'Goodwood', 'Perth']:
        if target in ps_str:
            print(f"STRING '{target}' FOUND in initialState JSON")
            
    # 3. Check for specific race IDs that are definitely 06-07
    # (Based on user hint: Navan 922048+)
    races = ps.get('races', {}).get('byRaceId', {})
    found_0607 = []
    for rid, r in races.items():
        if '2026-06-07' in r.get('raceUrl', ''):
            found_0607.append((rid, r.get('meetingName'), r.get('startTime')))
            
    print(f"Found {len(found_0607)} races for 2026-06-07 in byRaceId")
    for r in found_0607[:10]:
        print(f"  {r}")

if __name__ == "__main__":
    inspect_full_meetings()
