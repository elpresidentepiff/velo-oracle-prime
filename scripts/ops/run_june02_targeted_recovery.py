import subprocess
import json
from pathlib import Path
import time
from datetime import datetime

def run_targeted_recovery():
    url_file = Path("data/new_build/rp_scrape_queue/june_02_missing_174.txt")
    if not url_file.exists():
        print(f"Error: {url_file} not found")
        return
        
    urls = url_file.read_text(encoding="utf-8").splitlines()
    print(f"Total horses to recover: {len(urls)}")
    
    batch_size = 20
    # We will process 2 batches in this turn to stay safe with timeouts
    max_batches = 2
    
    for b_idx in range(max_batches):
        start = b_idx * batch_size
        if start >= len(urls): break
        
        end = min(start + batch_size, len(urls))
        batch_urls = urls[start:end]
        
        timestamp = datetime.now().strftime("%H%M%S")
        batch_label = f"june02-recov-b{b_idx + 1}-{timestamp}"
        
        print(f"\n=== Starting {batch_label} ({len(batch_urls)} URLs) ===")
        
        temp_url_file = Path(f"data/new_build/rp_scrape_queue/{batch_label}_urls.txt")
        temp_url_file.write_text("\n".join(batch_urls), encoding="utf-8")
        
        # 1. Scrape (Headed, 2.5s delay)
        raw_dir = Path(f"data/racing_post_account_raw/{batch_label}")
        print(f"Scraping into {raw_dir}...")
        scrape_cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(temp_url_file),
            "--date", "2026-06-02",
            "--output-dir", str(raw_dir),
            "--delay-seconds", "2.5",
            "--execute", "--headed"
        ]
        subprocess.run(scrape_cmd)
        
        # 2. Parse Profiles
        print(f"Parsing into {batch_label}...")
        parse_profiles_cmd = [
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", str(raw_dir / "2026-06-02"),
            "--date", batch_label,
            "--execute"
        ]
        subprocess.run(parse_profiles_cmd)
        
        # 3. Parse Form History
        print(f"Extracting form history...")
        parse_history_cmd = [
            "python", "scripts/ops/parse_rp_form_history.py",
            "--date", batch_label
        ]
        subprocess.run(parse_history_cmd)
        
        # 4. Build Passports (APPEND-ONLY)
        print(f"Appending to bank...")
        build_passports_cmd = [
            "python", "scripts/ops/new_build_horse_passports.py"
        ]
        subprocess.run(build_passports_cmd)
        
        print(f"=== {batch_label} complete ===")
        time.sleep(10)

if __name__ == "__main__":
    run_targeted_recovery()
