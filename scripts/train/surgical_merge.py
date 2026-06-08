"""
Surgical corpus build for Challenger V2.
Merges missing passport features into the unified corpus.
"""
import pandas as pd
from pathlib import Path

def surgical_merge():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    
    print("Loading existing unified corpus...")
    df = pd.read_parquet(TRAIN_DIR / "v2_unified_ts_enriched_full.parquet")
    
    print("Loading missing passport features...")
    passport = pd.read_parquet(TRAIN_DIR / "passport_features.parquet")
    
    # Identify what's missing
    REQUIRED = [
        "pp_career_runs", "pp_win_rate", "pp_place_rate",
        "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
        "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
        "pp_class_moved_up", "pp_class_moved_down"
    ]
    
    print("Performing surgical join...")
    # join on race_id and horse
    df = df.merge(passport, on=["race_id", "horse"], how="left")
    
    print(f"Merge complete. Columns: {df.columns.tolist()}")
    print(f"pp_career_runs present: {'pp_career_runs' in df.columns}")
    
    out_path = TRAIN_DIR / "v2_unified_ts_enriched_full_FIXED.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    surgical_merge()
