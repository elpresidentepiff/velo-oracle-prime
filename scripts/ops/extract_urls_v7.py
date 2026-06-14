import json
import re
from pathlib import Path

def extract_urls_v7():
    path = Path("data/racing_post_account_raw/index-2026-06-07-FINAL/001_racecards_2026_06_07_7bf7bce8f817.html")
    content = path.read_text(encoding='utf-8')
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
    data = json.loads(match.group(1))
    ps = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    
    ps_str = json.dumps(ps)
    # Be extremely loose: search for any occurrence of 2026-06-07 inside a URL-like pattern
    pattern = r'/racecards/[^/]+/[^/]+/2026-06-07/\d+'
    matches = re.findall(pattern, ps_str)
    
    print(f"Loose Regex Matches: {len(matches)}")
    
    urls = []
    for match_path in matches:
        url = f"https://www.racingpost.com{match_path}"
        if url not in urls:
            urls.append(url)
            print(f"EXTRACTED: {url}")

    if urls:
        out = Path("data/racing_post_url_lists/rp_racecards_2026-06-07_TRUE.txt")
        out.write_text("\n".join(sorted(urls)) + "\n", encoding="utf-8")
        print(f"\nSUCCESS: {len(urls)} URLs written to {out}")
    else:
        print("FAIL: No June 7th URLs found via loose regex")

if __name__ == "__main__":
    extract_urls_v7()
