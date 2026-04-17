"""
One-time job: compute all v17 doctrine features and save to parquet.
After this runs, audit + future training loads data/raceform_v17_features.parquet directly.

Usage:
    python scripts/save_engineered_features.py

Takes ~30-40 min. Only needs to run once (or when raceform_clean.parquet is updated).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from scripts.train_sqpe_v17 import engineer_v16_features, engineer_v17_doctrine, ALL_FEATURES

SRC = Path("data/raceform_clean.parquet")
OUT = Path("data/raceform_v17_features.parquet")

print(f"Loading {SRC} ...")
df = pd.read_parquet(SRC)
df = df.rename(columns={"class": "class_raw", "or": "or_rating"}, errors="ignore")
if "race_id" not in df.columns:
    df["race_id"] = df["course"].astype(str) + "_" + df["date"].astype(str) + "_" + df["off"].astype(str)
df = df[~df["pos"].astype(str).str.strip().isin(["", "nan", "NaN"])]
print(f"  {len(df):,} rows")

print("Engineering v16 features ...")
df = engineer_v16_features(df)

print("Sorting chronologically ...")
df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)

print(f"Computing v17 doctrine features ({df['horse'].nunique():,} horses) ...")
df = engineer_v17_doctrine(df)

df = df.sort_values("date_parsed").reset_index(drop=True)

# Save all columns needed for audit + training
keep = ["race_id", "date", "date_parsed", "course", "horse", "jockey", "trainer",
        "type", "pos", "target", "_yr"] + ALL_FEATURES
keep = [c for c in keep if c in df.columns]
df["_yr"] = df["date_parsed"].dt.year

print(f"Saving to {OUT} ...")
df[keep].to_parquet(OUT, engine="pyarrow", compression="snappy", index=False)
print(f"Done. {OUT.stat().st_size/1e6:.0f} MB")
print(f"\nAll future scripts can now load: pd.read_parquet('data/raceform_v17_features.parquet')")
