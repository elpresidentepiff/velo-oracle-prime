import duckdb
import pandas as pd
from pathlib import Path

def extract_persistence():
    ROOT = Path(".")
    DB_PATH = ROOT / "data" / "analytics" / "velo_analytics.db"
    REF_PATH = ROOT / "hackathon" / "amd_harnessguard" / "demo_cases" / "persistence_reference.csv"
    INC_PATH = ROOT / "hackathon" / "amd_harnessguard" / "demo_cases" / "supabase_decision_tier_null" / "incident_data.csv"
    
    con = duckdb.connect(str(DB_PATH))
    
    # Healthy baseline
    print("Extracting healthy persistence reference...")
    ref_df = con.execute("SELECT horse, assigned_product, tier FROM innovation_protocol WHERE assigned_product IS NOT NULL AND tier IS NOT NULL LIMIT 200").fetchdf()
    ref_df.to_csv(REF_PATH, index=False)
    
    # Incident data (from innovation_protocol where NULLs exist)
    print("Extracting null persistence incident...")
    inc_df = con.execute("SELECT horse, assigned_product, tier FROM innovation_protocol WHERE assigned_product IS NULL OR tier IS NULL LIMIT 200").fetchdf()
    inc_df.to_csv(INC_PATH, index=False)
    
    print(f"Saved {len(ref_df)} healthy rows to {REF_PATH}")
    print(f"Saved {len(inc_df)} null rows to {INC_PATH}")
    con.close()

if __name__ == "__main__":
    extract_persistence()
