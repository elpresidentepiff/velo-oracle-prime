import json
import re
from pathlib import Path

def string_search_jockeys():
    path = Path("data/racing_post_account_raw/live-full-racepages-2026-06-06/001_racecards_101_worcester_2026_06_06_919896_92b42469ed98.html")
    content = path.read_text(encoding='utf-8')
    
    # Famous jockeys likely to be at Worcester
    target_names = ["Bowen", "Cobden", "Skelton", "Hughes", "Freddie Keighley", "Sheehan"]
    
    for name in target_names:
        idx = content.find(name)
        if idx != -1:
            print(f"FOUND string '{name}' at index {idx}")
            # Show context
            print(f"Context: {content[idx-100:idx+100]}")
        else:
            print(f"NOT FOUND: '{name}'")

if __name__ == "__main__":
    string_search_jockeys()
