import json
import re
from pathlib import Path

def extract_urls_from_index():
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
    
    # Try different structures based on RP index page variations
    meetings_data = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("meetings", {})
    if not meetings_data:
        meetings_data = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("racecards", {}).get("meetings", {})
    
    print(f"Total Meetings Found: {len(meetings_data)}")
    
    urls = []
    # If meetings_data is a dict, keys are often course IDs or course keys
    # If it's a list, it's course objects
    if isinstance(meetings_data, dict):
        for m_id in meetings_data:
            m = meetings_data[m_id]
            if not isinstance(m, dict): continue
            course = m.get("courseName")
            for r in m.get("races", []):
                url = f"https://www.racingpost.com/racecards/{m.get('courseId')}/{m.get('courseKey')}/{m.get('raceDate')}/{r.get('raceId')}"
                urls.append(url)
                print(f"Found: {course} - {url}")
    elif isinstance(meetings_data, list):
        for m in meetings_data:
            if not isinstance(m, dict): continue
            course = m.get("courseName")
            for r in m.get("races", []):
                url = f"https://www.racingpost.com/racecards/{m.get('courseId')}/{m.get('courseKey')}/{m.get('raceDate')}/{r.get('raceId')}"
                urls.append(url)
                print(f"Found: {course} - {url}")

    if urls:
        output_path = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_REBUILT.txt")
        output_path.write_text("\n".join(urls) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: Wrote {len(urls)} URLs to {output_path}")
    else:
        print("FAIL: No URLs extracted from index")

if __name__ == "__main__":
    extract_urls_from_index()
