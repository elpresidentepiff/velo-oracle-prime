import os
import shutil
from pathlib import Path

def consolidate():
    root = Path("data/racing_post_account_raw")
    dest = root / "recovery-consolidated" / "2026-05-31"
    dest.mkdir(parents=True, exist_ok=True)
    
    sources = [
        "today-recovery-all",
        "today-recovery-final-clean",
        "today-recovery-final-v2",
        "today-recovery-final-v3",
        "passport-recovery-headed-2026-05-31"
    ]
    
    count = 0
    uids_seen = set()
    
    for s in sources:
        s_dir = root / s / "2026-05-31"
        if not s_dir.exists(): continue
        
        for f in s_dir.glob("*.html"):
            parts = f.name.split("_")
            uid = None
            for i, p in enumerate(parts):
                if p == "horse" and i+1 < len(parts):
                    uid = parts[i+1]
                    break
            
            if uid and uid not in uids_seen:
                shutil.copy(f, dest / f.name)
                json_f = f.with_suffix(".json")
                if json_f.exists():
                    shutil.copy(json_f, dest / json_f.name)
                uids_seen.add(uid)
                count += 1
    
    print(f"Consolidated {count} unique horse profiles to {dest}")

if __name__ == "__main__":
    consolidate()
