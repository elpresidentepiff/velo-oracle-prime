#!/usr/bin/env python3
"""
normalise_hfs_legacy_scale.py

Option A: Normalise pre-2026 mpi and chaos_bloom from legacy 0-100 scale → 0-1 scale.
Mark 11,259 data-dark rows as EXCLUDED_DATA_DARK.

Usage:
    python scripts/normalise_hfs_legacy_scale.py --dry-run
    python scripts/normalise_hfs_legacy_scale.py --apply
"""

import os
import sys
import csv
import json
import time
import argparse
import asyncio
import aiohttp
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "historical_feature_store"
BATCH_SIZE = 500
BACKUP_PATH = Path("data/hfs_normalise_backup_pre_apply.csv")
DARK_FLAG = "EXCLUDED_DATA_DARK"

def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def fetch_page(filters: str, select: str, offset: int, limit: int = 1000) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?{filters}&select={select}&offset={offset}&limit={limit}"
    r = requests.get(url, headers=headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_all(filters: str, select: str) -> list:
    rows = []
    offset = 0
    while True:
        batch = fetch_page(filters, select, offset, 1000)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
        time.sleep(0.1)
    return rows

async def _patch_single(session: aiohttp.ClientSession, row_id: int, payload: dict, sem: asyncio.Semaphore) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.{row_id}"
    async with sem:
        try:
            async with session.patch(url, json=payload, headers=headers()) as r:
                return r.status in (200, 204)
        except Exception:
            return False

async def patch_rows_async(updates: list[dict]) -> int:
    """PATCH each row individually via asyncio (20 concurrent). Returns success count."""
    sem = asyncio.Semaphore(20)
    connector = aiohttp.TCPConnector(limit=20)
    timeout = aiohttp.ClientTimeout(total=30)
    updated = 0
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for row in updates:
            row_id = row.pop("id")
            tasks.append(_patch_single(session, row_id, row, sem))
        results = await asyncio.gather(*tasks)
        updated = sum(1 for r in results if r)
    return updated

def patch_rows(updates: list[dict]) -> int:
    return asyncio.run(patch_rows_async([dict(r) for r in updates]))

def stats(values: list[float]) -> dict:
    if not values:
        return {}
    n = len(values)
    mn = min(values)
    mx = max(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    std = variance ** 0.5
    return {"n": n, "min": round(mn, 4), "max": round(mx, 4), "mean": round(mean, 4), "std": round(std, 4)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply")
        sys.exit(1)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    print("=" * 68)
    print("HFS LEGACY SCALE NORMALISATION — Option A")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY'}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 68)

    # ── 1. Fetch pre-2026 rows with non-null mpi ─────────────────────────
    print("\n[1/5] Fetching pre-2026 non-null mpi rows...")
    pre2026_filter = "race_date=lt.2026-01-01&mpi=not.is.null"
    pre2026_select = "id,race_date,mpi,chaos_bloom,reconstruction_version"
    pre2026_rows = fetch_all(pre2026_filter, pre2026_select)
    print(f"  Fetched: {len(pre2026_rows):,} rows")

    if not pre2026_rows:
        print("  No rows found. Aborting.")
        sys.exit(1)

    # ── 2. Fetch dark rows (null mpi, any date) ───────────────────────────
    print("\n[2/5] Fetching data-dark rows (null mpi)...")
    dark_filter = "mpi=is.null"
    dark_select = "id,race_date,reconstruction_version"
    dark_rows = fetch_all(dark_filter, dark_select)
    # Filter: exclude already-flagged
    dark_rows = [r for r in dark_rows if r.get("reconstruction_version") != DARK_FLAG]
    print(f"  Fetched: {len(dark_rows):,} rows to flag as {DARK_FLAG}")

    # ── 3. Analyse pre-2026 scale ─────────────────────────────────────────
    print("\n[3/5] Analysing current scale...")
    mpi_values = [float(r["mpi"]) for r in pre2026_rows if r.get("mpi") is not None]
    cb_values = [float(r["chaos_bloom"]) for r in pre2026_rows if r.get("chaos_bloom") is not None]

    mpi_stats = stats(mpi_values)
    cb_stats = stats(cb_values)
    mpi_over1 = sum(1 for v in mpi_values if v > 1.0)
    cb_over1 = sum(1 for v in cb_values if v > 1.0)

    print(f"  mpi:        {mpi_stats}  ({mpi_over1}/{mpi_stats['n']} > 1.0 — {100*mpi_over1/mpi_stats['n']:.1f}%)")
    print(f"  chaos_bloom:{cb_stats}  ({cb_over1}/{cb_stats['n']} > 1.0 — {100*cb_over1/cb_stats['n']:.1f}%)")

    # Build normalised values preview
    norm_mpi = [round(min(1.0, max(0.0, v / 100.0)), 4) for v in mpi_values]
    norm_cb = [round(min(1.0, max(0.0, v / 100.0)), 4) for v in cb_values]
    print(f"\n  After ÷100:")
    print(f"  mpi:        {stats(norm_mpi)}")
    print(f"  chaos_bloom:{stats(norm_cb)}")

    # ── 4. Backup ─────────────────────────────────────────────────────────
    if args.apply:
        print(f"\n[4/5] Writing backup → {BACKUP_PATH}...")
        BACKUP_PATH.parent.mkdir(exist_ok=True)
        with open(BACKUP_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "race_date", "mpi", "chaos_bloom", "reconstruction_version"])
            writer.writeheader()
            writer.writerows(pre2026_rows)
        print(f"  Backup written: {len(pre2026_rows):,} rows → {BACKUP_PATH}")
    else:
        print(f"\n[4/5] Backup: skipped (dry-run)")

    # ── 5. Apply / report ─────────────────────────────────────────────────
    print(f"\n[5/5] {'Applying' if args.apply else 'Preview of'} normalisation...")

    if args.dry_run:
        print(f"\n  WOULD update {len(pre2026_rows):,} rows: mpi ÷100, chaos_bloom ÷100")
        print(f"  WOULD flag   {len(dark_rows):,} rows: reconstruction_version='{DARK_FLAG}'")
        print(f"\n  Sample normalised values (first 5):")
        for r in pre2026_rows[:5]:
            new_mpi = round(min(1.0, float(r["mpi"]) / 100.0), 4) if r.get("mpi") else None
            new_cb = round(min(1.0, float(r["chaos_bloom"]) / 100.0), 4) if r.get("chaos_bloom") else None
            print(f"    id={r['id']}  date={r['race_date']}  mpi: {r['mpi']} → {new_mpi}  chaos_bloom: {r.get('chaos_bloom')} → {new_cb}")
        print("\n  Run with --apply to execute.")
        return

    # Build update payloads for pre-2026 rows
    norm_updates = []
    for r in pre2026_rows:
        mpi_raw = float(r["mpi"]) if r.get("mpi") is not None else None
        cb_raw = float(r["chaos_bloom"]) if r.get("chaos_bloom") is not None else None
        payload = {
            "id": r["id"],
            "reconstruction_version": "hfs_signal_contract_v1_normalised_legacy",
        }
        if mpi_raw is not None:
            payload["mpi"] = round(min(1.0, max(0.0, mpi_raw / 100.0)), 4)
        if cb_raw is not None:
            payload["chaos_bloom"] = round(min(1.0, max(0.0, cb_raw / 100.0)), 4)
        norm_updates.append(payload)

    print(f"  Normalising {len(norm_updates):,} pre-2026 rows...")
    n_updated = patch_rows(norm_updates)
    print(f"  Done: {n_updated:,} rows updated")

    # Flag dark rows
    dark_updates = [
        {"id": r["id"], "reconstruction_version": DARK_FLAG}
        for r in dark_rows
    ]
    print(f"  Flagging {len(dark_updates):,} data-dark rows...")
    n_dark = patch_rows(dark_updates)
    print(f"  Done: {n_dark:,} rows flagged")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("NORMALISATION COMPLETE")
    print(f"  Pre-2026 rows normalised : {n_updated:,}")
    print(f"  Dark rows flagged        : {n_dark:,}")
    print(f"  Backup                   : {BACKUP_PATH}")
    print("=" * 68)
    print("\nNext: run scripts/audit_hfs_signal_integrity.py to re-classify HFS")

if __name__ == "__main__":
    main()
