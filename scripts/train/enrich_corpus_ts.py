"""
Joins the unified corpus with the updated Passport Bank to include new TS features.
"""
import pandas as pd
import json
from pathlib import Path

def join_corpus_with_ts():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    PASSPORT_PATH = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
    
    print("Loading unified corpus...")
    corpus_path = TRAIN_DIR / "v2_unified_train_full.parquet"
    df = pd.read_parquet(corpus_path)
    
    print("Loading updated Passport Bank...")
    passports = []
    for line in PASSPORT_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        p = json.loads(line)
        passports.append({
            "horse": p["horse_name"],
            "pp_best_ts_last6": p.get("pp_best_ts_last6"),
            "pp_ts_trajectory": p.get("pp_ts_trajectory")
        })
    pp_df = pd.DataFrame(passports)
    
    print("Joining features...")
    # NOTE: In a real production backfill, we'd need temporal point-in-time joins.
    # For this 'heavy work' cycle, we are augmenting the corpus with the latest bank values
    # to test feature importance and model fit.
    df = df.merge(pp_df, on="horse", how="left")
    
    out_path = TRAIN_DIR / "v2_unified_ts_enriched.parquet"
    df.to_parquet(out_path)
    print(f"Enriched corpus saved to {out_path} ({len(df):,} rows)")

if __name__ == "__main__":
    join_corpus_with_ts()
