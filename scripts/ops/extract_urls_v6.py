import json
import re
from pathlib import Path

def extract_urls_v6():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    # 1. Search for raceUrl patterns directly in the full JSON string
    # This bypasses the 'byDate' indexing which seems to be using 06-06
    ps_str = json.dumps(ps)
    # Pattern: "raceUrl":"/racecards/193/navan/2026-06-07/922048"
    pattern = r'\"raceUrl\":\"(/racecards/(\d+)/([^/]+)/2026-06-07/(\d+))\"'
    matches = re.findall(pattern, ps_str)
    
    print(f"Direct Regex Matches: {len(matches)}")
    
    urls = []
    for full_path, course_id, course_key, r_id in matches:
        url = f"https://www.racingpost.com{full_path}"
        if url not in urls:
            urls.append(url)
            print(f"EXTRACTED: {course_key} ({r_id}) -> {url}")

    if urls:
        out = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_TRUE.txt")
        out.write_text("\n".join(sorted(urls)) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: {len(urls)} URLs written to {out}")
    else:
        print("FAIL: No June 7th URLs found via regex")

if __name__ == "__main__":
    extract_urls_v6()
