import json
import re
from pathlib import Path

def extract_urls_v4():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    # We found '2026-06-06' in byDate, which is likely the key used for 'Today'
    meetings_data = ps.get("meetings", {}).get("byDate", {}).get("2026-06-06", {})
    if not meetings_data:
        print("FAIL: No data for 2026-06-06 found in index")
        return

    meetings_dict = meetings_data.get("meetings", {}).get("byMeetingId", {})
    
    print(f"Meetings: {len(meetings_dict)}")
    
    urls = []
    for m_id, m in meetings_dict.items():
        course = m.get("name")
        course_id = m.get("meetingId")
        course_key = m.get("courseKey")
        # Check date in meeting object
        m_date = m.get("meetingDate") # Might be here
        if not m_date:
            # Fallback to hardcoded June 7th since that's the mission date
            m_date = "2026-06-07"
            
        r_ids = m.get("raceIds", [])
        for r_id in r_ids:
            url = f"https://www.racingpost.com/racecards/{course_id}/{course_key}/{m_date}/{r_id}"
            urls.append(url)
            print(f"FOUND: {course} ({r_id}) -> {url}")

    if urls:
        out = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_FINAL.txt")
        out.write_text("\n".join(urls) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: {len(urls)} URLs written to {out}")
    else:
        print("FAIL: No URLs extracted")

if __name__ == "__main__":
    extract_urls_v4()
