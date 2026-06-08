import json
import re
from pathlib import Path

def extract_all_urls_final():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
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
    
    # Try multiple meeting locations in the JSON
    meetings_data = ps.get("meetings", {}).get("byDate", {}).get("2026-06-07", {}).get("meetings", {}).get("byMeetingId", {})
    if not meetings_data:
         # Fallback to secondary structure
         meetings_data = ps.get("racecards", {}).get("meetings", [])
    
    print(f"Extraction context: meetings_data type={type(meetings_data)}")
    
    urls = []
    
    if isinstance(meetings_data, dict):
        for m_id, m in meetings_data.items():
            course = m.get("name")
            course_id = m.get("meetingId")
            course_key = m.get("courseKey")
            r_ids = m.get("raceIds", [])
            for r_id in r_ids:
                url = f"https://www.racingpost.com/racecards/{course_id}/{course_key}/2026-06-07/{r_id}"
                urls.append(url)
                print(f"EXTRACTED: {course} ({r_id})")
    elif isinstance(meetings_data, list):
        for m in meetings_data:
            course = m.get("courseName")
            course_id = m.get("courseId")
            course_key = m.get("courseKey")
            for r in m.get("races", []):
                r_id = r.get("raceId")
                url = f"https://www.racingpost.com/racecards/{course_id}/{course_key}/2026-06-07/{r_id}"
                urls.append(url)
                print(f"EXTRACTED: {course} ({r_id})")

    if urls:
        out = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_FINAL.txt")
        out.write_text("\n".join(urls) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: {len(urls)} URLs written to {out}")
    else:
        print("FAIL: No URLs found in index")

if __name__ == "__main__":
    extract_all_urls_final()
