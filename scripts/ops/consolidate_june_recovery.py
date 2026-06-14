import os
import shutil
from pathlib import Path

def consolidate():
    root = Path("data/racing_post_account_raw")
    dest = root / "june-recovery-consolidated" / "2026-06-02"
    dest.mkdir(parents=True, exist_ok=True)
    
    sources = [
        "june-batch-1",
        "passport-recovery-2026-06-02"
    ]
    
    count = 0
    uids_seen = set()
    
    for s in sources:
        # Check both the parent and the subfolder
        s_base = root / s
        s_dirs = [s_base] + list(s_base.glob("2026-*"))
        
        for s_dir in s_dirs:
            if not s_dir.is_dir(): continue
            
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
