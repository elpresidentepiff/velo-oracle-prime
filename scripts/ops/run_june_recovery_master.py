import subprocess
import json
from pathlib import Path
import time

def run_recovery():
    url_file = Path("data/new_build/rp_scrape_queue/june_recovery_urls.txt")
    if not url_file.exists():
        print(f"Error: {url_file} not found")
        return
        
    urls = url_file.read_text(encoding="utf-8").splitlines()
    print(f"Total horses to recover: {len(urls)}")
    
    batch_size = 100
    # Process next 5 batches
    max_batches = 5 

    for b_idx in range(max_batches):
        start = (b_idx + 1) * batch_size # Start after the first 100 we just did
        if start >= len(urls): break

        end = start + batch_size
        batch_urls = urls[start:end]
        batch_label = f"june-batch-{b_idx + 2}" # Offset to batch 2

        print(f"\n=== Starting {batch_label} ({len(batch_urls)} URLs) ===")

        batch_url_file = Path(f"data/new_build/rp_scrape_queue/{batch_label}_urls.txt")
        batch_url_file.write_text("\n".join(batch_urls), encoding="utf-8")

        # 1. Scrape
        print(f"Scraping {batch_label}...")
        scrape_cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(batch_url_file),
            "--date", "2026-06-02",
            "--output-dir", f"data/racing_post_account_raw/{batch_label}",
            "--delay-seconds", "1.5",
            "--execute", "--headed"
        ]
        subprocess.run(scrape_cmd)

        # 2. Parse Profiles
        print(f"Parsing profiles for {batch_label}...")
        parse_profiles_cmd = [
            "python", "scripts/ops/parse_racing_post_account_capture.py",
            "--raw-dir", f"data/racing_post_account_raw/{batch_label}/2026-06-02",
            "--date", batch_label,
            "--execute"
        ]
        subprocess.run(parse_profiles_cmd)

        # 3. Parse Form History
        print(f"Extracting form history for {batch_label}...")
        parse_history_cmd = [
            "python", "scripts/ops/parse_rp_form_history.py",
            "--date", batch_label
        ]
        subprocess.run(parse_history_cmd)

        # 4. Build Passports (Append-only)
        print(f"Building passports for {batch_label}...")
        build_passports_cmd = [
            "python", "scripts/ops/new_build_horse_passports.py"
        ]
        subprocess.run(build_passports_cmd)

        print(f"=== {batch_label} complete ===\n")
        time.sleep(5)

if __name__ == "__main__":
    run_recovery()
