import subprocess
from pathlib import Path

def capture_indices():
    dates = ['2026-06-02', '2026-06-03', '2026-06-04', '2026-06-05', '2026-06-06', '2026-06-07']
    
    for d in dates:
        print(f"Capturing index for {d}...")
        url = f"https://www.racingpost.com/racecards/{d}"
        url_file = Path(f"data/racing_post_url_lists/index_{d}.txt")
        url_file.parent.mkdir(parents=True, exist_ok=True)
        url_file.write_text(url, encoding="utf-8")
        
        cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(url_file),
            "--date", d,
            "--output-dir", f"data/racing_post_account_raw/index-{d}",
            "--execute", "--headed"
        ]
        subprocess.run(cmd)

if __name__ == "__main__":
    capture_indices()
