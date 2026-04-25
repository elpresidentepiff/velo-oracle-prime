"""
VELO Training Data Prep
========================
Converts raceform.csv (1.7M rows, 633MB) into data/raceform_clean.parquet
for use by train_sqpe_v17.py.

Processes in 200k-row chunks — never loads full file into RAM.
Renames columns to match train_sqpe_v17.py's expected schema.

Usage:
    python scripts/build_training_data.py
    python scripts/build_training_data.py --uk-ire-only
    python scripts/build_training_data.py --from-year 2018

Output: data/raceform_clean.parquet  (~150-180 MB)
Then:   python scripts/train_sqpe_v17.py --raceform data/raceform_clean.parquet
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SRC   = Path("C:/Users/puror/Downloads/raceform.csv")
OUT   = Path("data/raceform_clean.parquet")
CHUNK = 200_000

# Courses to exclude when --uk-ire-only (international tracks)
INTERNATIONAL = re.compile(
    r"Sha Tin|Happy Valley|Randwick|Flemington|Moonee|Caulfield|Ascot \(AUS\)|"
    r"Longchamp|Chantilly|Deauville|Meydan|Nad Al Sheba|Laurel|Aqueduct|"
    r"Santa Anita|Ellerslie|Trentham|Riccarton",
    re.IGNORECASE,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",       default=str(SRC))
    parser.add_argument("--output",      default=str(OUT))
    parser.add_argument("--uk-ire-only", action="store_true",
                        help="Remove international tracks (US, AUS, NZ, FR etc.)")
    parser.add_argument("--from-year",   type=int, default=2015)
    parser.add_argument("--to-year",     type=int, default=2025)
    args = parser.parse_args()

    src = Path(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"ERROR: {src} not found"); sys.exit(1)

    print(f"Input : {src}  ({src.stat().st_size / 1e6:.0f} MB)")
    print(f"Output: {out}")
    print()

    writer = None
    total = 0
    wins  = 0

    for i, chunk in enumerate(pd.read_csv(
        src,
        encoding="utf-8",
        encoding_errors="replace",
        chunksize=CHUNK,
        low_memory=False,
        dtype=str,
    )):
        # ── Rename to match train_sqpe_v17.py schema ──────────────────────────
        chunk = chunk.rename(columns={
            "or":    "or_rating",   # 'or' is a Python reserved word — rename
            "class": "class_raw",   # rename for clarity
        })

        # Ensure race_id exists
        if "race_id" not in chunk.columns:
            chunk["race_id"] = (
                chunk.get("course", "unk").astype(str) + "_" +
                chunk.get("date",   "0").astype(str)   + "_" +
                chunk.get("off",    "0").astype(str)
            )

        # ── Filters ───────────────────────────────────────────────────────────
        chunk["_year"] = pd.to_datetime(chunk["date"], errors="coerce").dt.year
        chunk = chunk[
            (chunk["_year"] >= args.from_year) &
            (chunk["_year"] <= args.to_year)
        ]

        if args.uk_ire_only and "course" in chunk.columns:
            chunk = chunk[~chunk["course"].str.contains(INTERNATIONAL, na=False)]

        if chunk.empty:
            continue

        # ── Drop _year helper ─────────────────────────────────────────────────
        chunk = chunk.drop(columns=["_year"])

        # ── Write parquet (append) ────────────────────────────────────────────
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out, table.schema, compression="snappy")
        writer.write_table(table)

        total += len(chunk)
        wins  += (chunk["pos"].astype(str).str.strip() == "1").sum()
        print(f"  Chunk {i+1:>3}: {len(chunk):>7,} rows  |  total: {total:>9,}  "
              f"wins: {wins:>7,} ({wins/total*100:.1f}%)")

    if writer:
        writer.close()

    if total == 0:
        print("No rows matched filters."); sys.exit(0)

    out_mb = out.stat().st_size / 1e6
    print()
    print("=" * 60)
    print(f"  Total rows  : {total:,}")
    print(f"  Win rows    : {wins:,}  ({wins/total*100:.1f}%)")
    print(f"  Output size : {out_mb:.0f} MB  (was {src.stat().st_size/1e6:.0f} MB)")
    print(f"  Output      : {out}")
    print("=" * 60)
    print()
    print("Next:")
    print("  python scripts/train_sqpe_v17.py --raceform data/raceform_clean.parquet")


if __name__ == "__main__":
    main()
