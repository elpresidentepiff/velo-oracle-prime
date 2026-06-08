import subprocess
from pathlib import Path

def run_batches():
    url_file = Path("data/racing_post_url_lists/batch_100.txt")
    urls = url_file.read_text(encoding="utf-8").splitlines()
    
    # Skip already captured
    already_captured = 21 # 16 from before + 5 from debug
    remaining_urls = urls[already_captured:]
    
    chunk_size = 20
    for i in range(0, len(remaining_urls), chunk_size):
        chunk = remaining_urls[i:i+chunk_size]
        print(f"Processing chunk {i//chunk_size + 1} ({len(chunk)} URLs)...")
        
        temp_file = Path("data/racing_post_url_lists/temp_chunk.txt")
        temp_file.write_text("\n".join(chunk), encoding="utf-8")
        
        cmd = [
            "python", "scripts/ops/racing_post_account_collector.py", "capture",
            "--url-list", str(temp_file),
            "--date", "2026-06-02",
            "--output-dir", "data/racing_post_account_raw/passport-recovery-2026-06-02",
            "--delay-seconds", "1.0",
            "--execute", "--headed"
        ]
        subprocess.run(cmd)
        print(f"Chunk {i//chunk_size + 1} complete.")

if __name__ == "__main__":
    run_batches()
