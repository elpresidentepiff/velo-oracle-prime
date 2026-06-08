import re
import json
from pathlib import Path

def extract():
    RAW_DIR = Path("data/racing_post_account_raw")
    html_files = list(RAW_DIR.glob("index-*/2026-*/001_racecards_*.html"))
    print(f"Found {len(html_files)} index files to scan")
    
    dates = ['2026-06-02', '2026-06-03', '2026-06-04', '2026-06-05', '2026-06-06', '2026-06-07']
    
    for d in dates:
        all_date_urls = set()
        for html_path in html_files:
            html = html_path.read_text(encoding="utf-8", errors="replace")
            # Pattern for race URLs in JSON blobs (no trailing slash)
            pattern = r'\"raceUrl\":\"(/racecards/\d+/[^/]+/' + d + r'/\d+)\"'
            urls = re.findall(pattern, html)
            all_date_urls.update(urls)
            
        print(f"{d}: {len(all_date_urls)} races found")
        
        if all_date_urls:
            full_urls = [f"https://www.racingpost.com{u}" for u in sorted(list(all_date_urls))]
            out_path = Path(f"data/racing_post_url_lists/rp_racecards_{d}.txt")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("\n".join(full_urls), encoding="utf-8")
            print(f"  Saved to {out_path}")
            
if __name__ == "__main__":
    extract()
