import subprocess
import json
from pathlib import Path
import time
from datetime import datetime

def fix_and_resume():
    root = Path("data/racing_post_account_raw")
    # Batches that were captured but not parsed correctly
    captured_batches = [
        ("june02-recov-b1-135010", "2026-06-02"),
        ("june02-recov-b2-135209", "2026-06-02")
    ]
    
    for batch_label, sub_date in captured_batches:
        raw_path = root / batch_label / sub_date
        print(f"\n--- Fixing Batch: {batch_label} ---")
        
        # 1. Parse Profiles (Using exact dir where manifest lives)
        parse_cmd = [
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", str(raw_path),
            "--date", batch_label,
            "--execute"
        ]
        subprocess.run(parse_cmd)
        
        # 2. Parse History
        subprocess.run(["python", "scripts/ops/parse_rp_form_history.py", "--date", batch_label])
        
        # 3. Append
        subprocess.run(["python", "scripts/ops/new_build_horse_passports.py"])

    # Now resume with next batches
    url_file = Path("data/new_build/rp_scrape_queue/june_02_missing_174.txt")
    urls = url_file.read_text(encoding="utf-8").splitlines()
    
    # We've done 40 so far
    already_captured = 40
    remaining_urls = urls[already_captured:]
    
    chunk_size = 20
    max_chunks = 3 # 60 more horses
    
    for i in range(max_chunks):
        start = i * chunk_size
        if start >= len(remaining_urls): break
        chunk = remaining_urls[start:start+chunk_size]
        
        timestamp = datetime.now().strftime("%H%M%S")
        batch_label = f"june02-recov-b{i + 3}-{timestamp}"
        
        print(f"\n=== Starting Chunk {i+3}: {batch_label} ({len(chunk)} URLs) ===")
        
        temp_file = Path(f"data/new_build/rp_scrape_queue/{batch_label}_urls.txt")
        temp_file.write_text("\n".join(chunk), encoding="utf-8")
        
        # Scrape into a FLAT structure for easier parsing
        raw_dir = root / batch_label
        scrape_cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(temp_file),
            "--date", batch_label, # Use batch_label as date to avoid deep nesting
            "--output-dir", str(raw_dir),
            "--delay-seconds", "2.0",
            "--execute", "--headed"
        ]
        subprocess.run(scrape_cmd)
        
        # Parse (raw-dir/batch_label should contain the manifest)
        subprocess.run([
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", str(raw_dir / batch_label),
            "--date", batch_label,
            "--execute"
        ])
        
        subprocess.run(["python", "scripts/ops/parse_rp_form_history.py", "--date", batch_label])
        subprocess.run(["python", "scripts/ops/new_build_horse_passports.py"])
        
        print(f"=== {batch_label} complete ===")
        time.sleep(5)

if __name__ == "__main__":
    fix_and_resume()
