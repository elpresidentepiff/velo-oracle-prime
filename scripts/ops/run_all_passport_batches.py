import subprocess
import os
from pathlib import Path

def run_batches():
    ROOT = Path("C:/Users/puror/velo-oracle-prime")
    URL_LIST_DIR = ROOT / "data/racing_post_url_lists"
    PYTHON_EXE = "python"
    COLLECTOR_SCRIPT = ROOT / "scripts/ops/racing_post_account_collector.py"
    
    # Jun 5-7 Batches
    for i in range(1, 7):
        batch_name = f"rp_profiles_jun05-07_batch_{i}.txt"
        batch_path = URL_LIST_DIR / batch_name
        if not batch_path.exists(): continue
        
        capture_label = f"passport-jun05-07-b{i}"
        print(f"Starting {capture_label}...")
        
        cmd = [
            PYTHON_EXE, str(COLLECTOR_SCRIPT), "capture",
            "--url-list", str(batch_path),
            "--date", capture_label,
            "--execute", "--headed", "--delay-seconds", "2.5"
        ]
        
        subprocess.run(cmd, cwd=str(ROOT))
        print(f"Finished {capture_label}.")

    # Jun 8-10 Batches
    for i in range(1, 7):
        batch_name = f"rp_profiles_jun08-10_batch_{i}.txt"
        batch_path = URL_LIST_DIR / batch_name
        if not batch_path.exists(): continue
        
        capture_label = f"passport-jun08-10-b{i}"
        print(f"Starting {capture_label}...")
        
        cmd = [
            PYTHON_EXE, str(COLLECTOR_SCRIPT), "capture",
            "--url-list", str(batch_path),
            "--date", capture_label,
            "--execute", "--headed", "--delay-seconds", "2.5"
        ]
        
        subprocess.run(cmd, cwd=str(ROOT))
        print(f"Finished {capture_label}.")

if __name__ == "__main__":
    run_batches()
