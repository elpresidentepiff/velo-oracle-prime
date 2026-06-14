import json
import re
from pathlib import Path

def extract_urls_from_index_v2():
    # Use the known working path
    path = Path("data/racing_post_account_raw/index-2026-06-07/2026-06-07/001_racecards_2026_06_07_7bf7bce8f817.html")
    if not path.exists():
        print("Error: Index HTML not found")
        return

    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    if not match:
        print("Error: __NEXT_DATA__ not found")
        return

    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    # Structure found in debug: ps['meetings']['byDate']['2026-06-01']...
    # BUT wait, the file is for 2026-06-07. Let's see if 2026-06-07 exists in the dict.
    meetings_by_date = ps.get("meetings", {}).get("byDate", {})
    print(f"Available dates in index: {list(meetings_by_date.keys())}")
    
    target_date = "2026-06-07"
    if target_date not in meetings_by_date:
        print(f"FAIL: Target date {target_date} not found in index data")
        # Check if it's stored under a different date due to timezone/stale data
        return

    day_data = meetings_by_date[target_date]
    meetings_dict = day_data.get("meetings", {}).get("byMeetingId", {})
    races_dict = day_data.get("races", {}).get("byRaceId", {})
    
    print(f"Meetings for {target_date}: {len(meetings_dict)}")
    print(f"Races for {target_date}: {len(races_dict)}")
    
    urls = []
    # Loop through meetings to get course info
    for m_id, m in meetings_dict.items():
        course_name = m.get("name")
        course_id = m.get("meetingId")
        course_key = m.get("courseKey")
        race_ids = m.get("raceIds", [])
        
        for r_id in race_ids:
            if r_id in races_dict:
                r = races_dict[r_id]
                # Construct canonical URL
                url = f"https://www.racingpost.com/racecards/{course_id}/{course_key}/{target_date}/{r_id}"
                urls.append(url)
                print(f"Found: {course_name} ({r_id}) -> {url}")

    if urls:
        output_path = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_REBUILT.txt")
        output_path.write_text("\n".join(urls) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: Wrote {len(urls)} URLs to {output_path}")
    else:
        print("FAIL: No URLs extracted from index")

if __name__ == "__main__":
    extract_urls_from_index_v2()
