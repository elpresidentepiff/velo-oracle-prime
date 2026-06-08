import subprocess
import json
from pathlib import Path
import time
from datetime import datetime

def run_recovery():
    url_file = Path("data/new_build/rp_scrape_queue/june_recovery_urls.txt")
    if not url_file.exists():
        print(f"Error: {url_file} not found")
        return
        
    urls = url_file.read_text(encoding="utf-8").splitlines()
    print(f"Total horses to recover: {len(urls)}")
    
    # Skip what we've already done (175 + 250 = 425)
    already_done = 425
    remaining_urls = urls[already_done:]
    print(f"Remaining: {len(remaining_urls)}")
    
    chunk_size = 50
    # Process up to 10 chunks per turn
    max_chunks = 10 
    
    for c_idx in range(max_chunks):
        start = c_idx * chunk_size
        if start >= len(remaining_urls): break
        
        end = start + chunk_size
        chunk_urls = remaining_urls[start:end]
        
        # Unique timestamp-based label
        timestamp = datetime.now().strftime("%H%M%S")
        batch_label = f"june-chunk-{c_idx + 1}-{timestamp}"
        
        print(f"\n=== Starting {batch_label} ({len(chunk_urls)} URLs) ===")
        
        temp_url_file = Path(f"data/new_build/rp_scrape_queue/{batch_label}_urls.txt")
        temp_url_file.write_text("\n".join(chunk_urls), encoding="utf-8")
        
        # 1. Scrape into UNIQUE folder
        raw_dir = f"data/racing_post_account_raw/{batch_label}"
        print(f"Scraping into {raw_dir}...")
        scrape_cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(temp_url_file),
            "--date", batch_label, # Use batch_label as date to match subfolder expectation
            "--output-dir", raw_dir,
            "--delay-seconds", "1.0",
            "--execute", "--headed"
        ]
        subprocess.run(scrape_cmd)
        
        # 2. Parse into UNIQUE folder
        print(f"Parsing into {batch_label}...")
        parse_profiles_cmd = [
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", raw_dir,
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
        
        # 4. Build Passports
        print(f"Appending to bank...")
        build_passports_cmd = [
            "python", "scripts/ops/new_build_horse_passports.py"
        ]
        subprocess.run(build_passports_cmd)
        
        # 5. Rebuild lookup index
        print(f"Refreshing lookup index...")
        # Since pl.load_index() only loads once, we need to run the script or call a dedicated rebuild command.
        # Check if passport_lookup.py has a main that rebuilds something (likely just verifying load)
        subprocess.run(["python", "new_build_velo/passport_lookup.py"]) 
        
        print(f"=== {batch_label} complete ===")
        time.sleep(5)

if __name__ == "__main__":
    run_recovery()
