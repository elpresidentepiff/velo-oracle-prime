import subprocess
import json
from pathlib import Path

def parse_batches():
    root = Path("data/racing_post_account_raw")
    # Exact parent dirs and the "date" folder name containing manifest
    batches = [
        (root / "june02-recov-b1-135010", "2026-06-02"),
        (root / "june02-recov-b2-135209", "2026-06-02"),
        (root / "june02-recov-b3-135429", "june02-recov-b3-135429"),
        (root / "june02-recov-b4-135614", "june02-recov-b4-135614"),
        (root / "june02-recov-b5-135759", "june02-recov-b5-135759")
    ]
    
    for raw_parent, date_label in batches:
        print(f"\n--- Parsing {date_label} in {raw_parent} ---")
        
        # Parse Profiles
        subprocess.run([
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", str(raw_parent),
            "--date", date_label,
            "--execute"
        ])
        
        # Parse History
        subprocess.run(["python", "scripts/ops/parse_rp_form_history.py", "--date", date_label])
        
        # Build Passports (APPEND-ONLY)
        subprocess.run(["python", "scripts/ops/new_build_horse_passports.py"])

if __name__ == "__main__":
    parse_batches()
