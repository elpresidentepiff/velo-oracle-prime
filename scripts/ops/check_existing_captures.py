import re
from pathlib import Path
from collections import defaultdict

def check_existing_captures():
    labels = ['live-full-racepages-2026-06-07-refresh', 'live-full-racepages-2026-06-07-FINAL-V2']
    for label in labels:
        folder = Path(f'data/racing_post_account_raw/{label}')
        if not folder.exists():
            print(f"{label}: FOLDER MISSING")
            continue
        html_files = list(folder.glob('*.html'))
        by_venue = defaultdict(int)
        for f in html_files:
            m = re.search(r'\d{3}_racecards_\d+_([a-z_]+)_2026_06_07', f.name)
            if m: by_venue[m.group(1)] += 1
        print(f'{label}: {sum(by_venue.values())} races')
        for v in sorted(by_venue):
            print(f'  {v}: {by_venue[v]}')
        print()

if __name__ == "__main__":
    check_existing_captures()
