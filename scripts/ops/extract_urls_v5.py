import json
import re
from pathlib import Path

def extract_urls_v5():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    # Structure from debug_keys_v2: ps['meetings']['byDate']['2026-06-06']
    # The index was captured on June 6th, but it's for 'Tomorrow' (June 7th)
    meetings_data = ps.get("meetings", {}).get("byDate", {}).get("2026-06-06", {})
    if not meetings_data:
        print("FAIL: No data for 2026-06-06 found in index")
        return

    meetings_dict = meetings_data.get("meetings", {}).get("byMeetingId", {})
    races_dict = meetings_data.get("races", {}).get("byRaceId", {})
    
    print(f"Meetings in Index: {len(meetings_dict)}")
    
    urls = []
    for m_id, m in meetings_dict.items():
        course = m.get("name")
        course_id = m.get("meetingId")
        course_key = m.get("courseKey")
        
        r_ids = m.get("raceIds", [])
        for r_id in r_ids:
            if r_id in races_dict:
                race = races_dict[r_id]
                # GET THE REAL DATE FROM THE RACE OBJECT
                # The index 'byDate' might be the capture date, but raceUrl has the truth
                # "/results/31/lingfield/2026-06-01/919957"
                race_url_path = race.get("raceUrl", "")
                date_match = re.search(r'2026-\d\d-\d\d', race_url_path)
                if date_match:
                    r_date = date_match.group(0)
                    if r_date == "2026-06-07":
                        url = f"https://www.racingpost.com/racecards/{course_id}/{course_key}/{r_date}/{r_id}"
                        urls.append(url)
                        print(f"FOUND 06-07: {course} ({r_id}) -> {url}")
                    else:
                        print(f"SKIPPING {r_date}: {course} ({r_id})")

    if urls:
        out = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_TRUE.txt")
        out.write_text("\n".join(urls) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: {len(urls)} URLs written to {out}")
    else:
        print("FAIL: No June 7th URLs found in this index")

if __name__ == "__main__":
    extract_urls_v5()
