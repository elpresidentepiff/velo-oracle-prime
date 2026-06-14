import json
import re
from pathlib import Path
from collections import defaultdict

def surgical_audit():
    sources = [
        'live-full-racepages-2026-06-07-refresh',
        'live-full-racepages-2026-06-07-FINAL-V2'
    ]
    
    unique_races = {} # race_id -> (venue, folder, filename, size)
    
    print("--- SURGICAL ARTIFACT AUDIT: JUNE 7TH ---")
    
    for label in sources:
        folder = Path(f"data/racing_post_account_raw/{label}")
        if not folder.exists(): continue
        
        # Check every JSON manifest first as it has the URL truth
        json_files = list(folder.glob("*.json"))
        for jf in json_files:
            if jf.name == "manifest.json": continue
            try:
                data = json.loads(jf.read_text(encoding='utf-8'))
                url = data.get('source_url', '') or data.get('final_url', '')
                
                # Check for June 7th in the URL
                if "/2026-06-07/" in url:
                    # Extract Race ID: .../2026-06-07/922047
                    race_id = url.split('/')[-1]
                    venue = url.split('/')[5]
                    
                    # Store if valid and unique
                    html_file = jf.with_suffix('.html')
                    if html_file.exists():
                        size = html_file.stat().st_size
                        if size > 100000:
                            if race_id not in unique_races:
                                unique_races[race_id] = (venue, label, html_file.name, size)
                            else:
                                print(f"DUPLICATE DETECTED: Race {race_id} found in {label} (already seen in {unique_races[race_id][1]})")
                else:
                    # Report the contamination I previously included
                    date_match = re.search(r'/2026-06-\d\d/', url)
                    if date_match:
                        print(f"CONTAMINATION IDENTIFIED: {jf.name} in {label} is for date {date_match.group(0)}")
            except: pass

    print("\n--- THE REAL ONE TRUTH: JUNE 7TH CARD ---")
    venue_counts = defaultdict(int)
    for rid, (venue, folder, fname, size) in unique_races.items():
        venue_counts[venue] += 1
        
    print(f"TOTAL UNIQUE RACES: {len(unique_races)}")
    for v in sorted(venue_counts):
        print(f"  - {v}: {venue_counts[v]} races")

if __name__ == "__main__":
    surgical_audit()
