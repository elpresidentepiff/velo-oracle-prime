import duckdb
import pandas as pd
from pathlib import Path

def extract_reference():
    ROOT = Path(".")
    TARGET_PATH = ROOT / "hackathon" / "amd_harnessguard" / "demo_cases" / "reference_baseline.csv"
    
    con = duckdb.connect()
    
    # Healthy window: May 10-14
    files = [
        'data/velo_prime_verdicts_2026_05_10.json',
        'data/velo_prime_verdicts_2026_05_11.json',
        'data/velo_prime_verdicts_2026_05_12.json',
        'data/velo_prime_verdicts_2026_05_13.json',
        'data/velo_prime_verdicts_2026_05_14.json'
    ]
    
    print(f"Extracting healthy reference from {len(files)} files ...")
    
    sql = f"SELECT top.horse, top.improvement_score FROM read_json_auto({files}) WHERE top.horse IS NOT NULL"
    df = con.execute(sql).fetchdf()
    
    df.to_csv(TARGET_PATH, index=False)
    print(f"Reference baseline saved to {TARGET_PATH} ({len(df)} rows)")

if __name__ == "__main__":
    extract_reference()
