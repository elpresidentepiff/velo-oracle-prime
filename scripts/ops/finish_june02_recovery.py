import subprocess
import json
from pathlib import Path
import time
from datetime import datetime

def finish_recovery():
    root = Path("data/racing_post_account_raw")
    url_file = Path("data/new_build/rp_scrape_queue/june_02_missing_174.txt")
    urls = url_file.read_text(encoding="utf-8").splitlines()
    
    # We've successfully captured and appended the first 100
    already_done = 100
    remaining_urls = urls[already_done:]
    print(f"Total remaining to recover: {len(remaining_urls)}")
    
    chunk_size = 25
    for i in range(0, len(remaining_urls), chunk_size):
        chunk = remaining_urls[i:i+chunk_size]
        
        timestamp = datetime.now().strftime("%H%M%S")
        batch_label = f"june02-final-b{i//chunk_size + 1}-{timestamp}"
        
        print(f"\n=== Starting Final Batch {i//chunk_size + 1}: {batch_label} ({len(chunk)} URLs) ===")
        
        temp_file = Path(f"data/new_build/rp_scrape_queue/{batch_label}_urls.txt")
        temp_file.write_text("\n".join(chunk), encoding="utf-8")
        
        # 1. Scrape
        raw_dir = root / batch_label
        scrape_cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(temp_file),
            "--date", batch_label,
            "--output-dir", str(raw_dir),
            "--delay-seconds", "2.0",
            "--execute", "--headed"
        ]
        subprocess.run(scrape_cmd)
        
        # 2. Parse (raw-dir/batch_label should contain the manifest)
        subprocess.run([
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", str(raw_dir / batch_label),
            "--date", batch_label,
            "--execute"
        ])
        
        # 3. Parse History
        subprocess.run(["python", "scripts/ops/parse_rp_form_history.py", "--date", batch_label])
        
        # 4. Append
        subprocess.run(["python", "scripts/ops/new_build_horse_passports.py"])
        
        print(f"=== {batch_label} complete ===")
        time.sleep(5)

if __name__ == "__main__":
    finish_recovery()
