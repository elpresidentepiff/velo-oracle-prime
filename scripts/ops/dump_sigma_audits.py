"""Dump sigma_audits from Supabase to data/sigma_audits_dump.json."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.run_results_sigma import sb_get

def dump_sigma():
    print("Fetching sigma_audits from Supabase...")
    # Fetch all records. Using a large limit or multiple pages if needed.
    all_rows = []
    skip = 0
    limit = 1000
    while True:
        rows = sb_get(f"/sigma_audits?select=*&order=date.desc&limit={limit}&offset={skip}")
        if not rows:
            break
        all_rows.extend(rows)
        print(f"  Fetched {len(all_rows)} rows...")
        if len(rows) < limit:
            break
        skip += limit
    
    output_path = ROOT / "data" / "sigma_audits_dump.json"
    with open(output_path, "w") as f:
        json.dump(all_rows, f, indent=2)
    print(f"Successfully dumped {len(all_rows)} rows to {output_path}")

if __name__ == "__main__":
    dump_sigma()
