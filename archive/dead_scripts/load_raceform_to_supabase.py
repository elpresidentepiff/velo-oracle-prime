"""
Load raceform.csv (2017+) into Supabase raceform table.
Batches of 500 rows. Restartable via --offset.

Run: python scripts/load_raceform_to_supabase.py
     python scripts/load_raceform_to_supabase.py --offset 50000  (resume)
"""
import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PARQUET = Path("data/raceform_clean.parquet")
BATCH   = 500
START_YEAR = "2017-01-01"


def _clean_row(row: dict) -> dict:
    """Convert numpy scalars and NaN → Python natives / None."""
    out = {}
    for k, v in row.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out[k] = None
        elif isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = float(v)
        elif isinstance(v, (np.bool_,)):
            out[k] = bool(v)
        else:
            out[k] = v
    return out


def _to_smallint(val) -> int | None:
    """Convert float-that-is-an-int (e.g. 4.0) to int, or None."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _to_real(val) -> float | None:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        f = float(val)
        return None if np.isnan(f) else f
    except (ValueError, TypeError):
        return None


def prepare_row(row: dict) -> dict:
    return {
        "date":        str(row["date"]) if row.get("date") else None,
        "course":      row.get("course") or None,
        "race_id":     str(row.get("race_id")) if row.get("race_id") else None,
        "off":         row.get("off") or None,
        "race_name":   row.get("race_name") or None,
        "type":        row.get("type") or None,
        "class_raw":   row.get("class_raw") or None,
        "pattern":     row.get("pattern") or None,
        "rating_band": row.get("rating_band") or None,
        "age_band":    row.get("age_band") or None,
        "sex_rest":    row.get("sex_rest") or None,
        "dist":        row.get("dist") or None,
        "going":       row.get("going") or None,
        "ran":         _to_smallint(row.get("ran")),
        "num":         _to_smallint(row.get("num")),
        "pos":         str(row.get("pos")) if row.get("pos") is not None else None,
        "draw":        _to_smallint(row.get("draw")),
        "ovr_btn":     _to_real(row.get("ovr_btn")),
        "btn":         str(row.get("btn")) if row.get("btn") is not None else None,
        "horse":       row.get("horse") or None,
        "age":         _to_smallint(row.get("age")),
        "sex":         row.get("sex") or None,
        "wgt":         row.get("wgt") or None,
        "hg":          row.get("hg") or None,
        "time":        row.get("time") or None,
        "sp":          row.get("sp") or None,
        "jockey":      row.get("jockey") or None,
        "trainer":     row.get("trainer") or None,
        "prize":       _to_real(row.get("prize")),
        "or_rating":   str(row.get("or_rating")) if row.get("or_rating") is not None else None,
        "rpr":         str(row.get("rpr")) if row.get("rpr") is not None else None,
        "ts":          str(row.get("ts")) if row.get("ts") is not None else None,
        "sire":        row.get("sire") or None,
        "dam":         row.get("dam") or None,
        "damsire":     row.get("damsire") or None,
        "owner":       row.get("owner") or None,
        "comment":     row.get("comment") or None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0, help="Row offset to resume from")
    parser.add_argument("--limit",  type=int, default=0,  help="Max rows to load (0=all)")
    args = parser.parse_args()

    from supabase import create_client
    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", ""),
    )

    print("Loading parquet...")
    df = pd.read_parquet(PARQUET)
    df = df[df["date"] >= START_YEAR].copy()
    df["date"] = df["date"].astype(str)
    df = df.reset_index(drop=True)
    total = len(df)
    print(f"2017+ rows: {total:,}")

    start  = args.offset
    end    = total if args.limit == 0 else min(total, start + args.limit)
    df     = df.iloc[start:end]
    n      = len(df)
    print(f"Loading rows {start:,}–{start+n:,} in batches of {BATCH}")

    rows_done = 0
    errors    = 0
    t_start   = time.time()

    for batch_start in range(0, n, BATCH):
        chunk = df.iloc[batch_start: batch_start + BATCH]
        records = [prepare_row(r) for r in chunk.to_dict(orient="records")]

        try:
            sb.table("raceform").insert(records).execute()
            rows_done += len(records)
        except Exception as e:
            errors += 1
            abs_offset = start + batch_start
            print(f"  ERROR at offset {abs_offset}: {e}")
            if errors > 20:
                print("Too many errors — aborting. Resume with --offset", abs_offset)
                sys.exit(1)
            time.sleep(2)
            continue

        elapsed   = time.time() - t_start
        rate      = rows_done / elapsed if elapsed > 0 else 0
        remaining = (n - rows_done) / rate / 60 if rate > 0 else 0
        pct       = (start + rows_done) / total * 100

        if rows_done % 10000 < BATCH:
            print(f"  {start + rows_done:>8,} / {total:,}  ({pct:.1f}%)  "
                  f"{rate:.0f} rows/s  ~{remaining:.0f} min left")

    elapsed = time.time() - t_start
    print(f"\nDone. {rows_done:,} rows loaded in {elapsed/60:.1f} min. Errors: {errors}")
    print(f"Resume offset if needed: --offset {start + rows_done}")


if __name__ == "__main__":
    main()
