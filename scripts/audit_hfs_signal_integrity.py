"""
audit_hfs_signal_integrity.py
==============================
Connects to Supabase and runs a full HFS signal integrity audit.
Outputs to stdout and data/hfs_signal_integrity_audit_latest.md.

Classification:
  HFS_TRAINING_BLOCKED         — mpi/cb null > 10%, parity off, duplicates, missing vectors
  HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME — passes null check but total rows < 5000
  HFS_TRAINING_READY           — all checks pass, total rows >= 5000

Usage:
    python scripts/audit_hfs_signal_integrity.py
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
LOG = logging.getLogger("audit_hfs_signal_integrity")


def _fetch_all(sb, table: str, select: str, page_size: int = 1000):
    rows = []
    offset = 0
    while True:
        q = sb.table(table).select(select).range(offset, offset + page_size - 1)
        result = q.execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _describe(values):
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "std": None}
    n = len(values)
    return {
        "n": n,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.stdev(values), 4) if n >= 2 else 0.0,
    }


def _sp_bracket(sp):
    if sp is None:
        return "unknown"
    if sp <= 2.0:
        return "evens_or_under"
    if sp <= 4.0:
        return "2.0-4.0"
    if sp <= 8.0:
        return "4.0-8.0"
    if sp <= 16.0:
        return "8.0-16.0"
    if sp <= 33.0:
        return "16.0-33.0"
    return "33.0+"


def main():
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            from app.core.runtime_env import load_optional_env_file
            load_optional_env_file(env_path)
        except Exception:
            pass

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        LOG.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(url, key)

    LOG.info("Fetching all HFS rows for audit...")
    rows = _fetch_all(
        sb, "historical_feature_store",
        "race_id,horse_id,race_date,mpi,chaos_bloom,winner_flag,placed_flag,"
        "finish_position,sp_dec,field_size,feature_json"
    )
    total = len(rows)
    LOG.info("Fetched %d HFS rows", total)

    # ── Partition: 2026+ vs pre-2026 ────────────────────────────────────────
    rows_2026 = [r for r in rows if (r.get("race_date") or "") >= "2026-01-01"]
    rows_pre2026 = [r for r in rows if (r.get("race_date") or "") < "2026-01-01"]

    # ── MPI stats ──────────────────────────────────────────────────────────
    mpi_vals = [r["mpi"] for r in rows if r.get("mpi") is not None]
    mpi_null = sum(1 for r in rows if r.get("mpi") is None)
    mpi_null_pct = 100 * mpi_null / max(total, 1)

    # ── chaos_bloom stats ──────────────────────────────────────────────────
    cb_vals = [r["chaos_bloom"] for r in rows if r.get("chaos_bloom") is not None]
    cb_null = sum(1 for r in rows if r.get("chaos_bloom") is None)
    cb_null_pct = 100 * cb_null / max(total, 1)

    # ── Winner / placed parity ─────────────────────────────────────────────
    winner_count = sum(1 for r in rows if r.get("winner_flag") is True)
    placed_count = sum(1 for r in rows if r.get("placed_flag") is True)
    winner_pct = 100 * winner_count / max(total, 1)
    placed_pct = 100 * placed_count / max(total, 1)

    # ── Duplicate (race_id, horse_id) combos ──────────────────────────────
    key_counts = Counter((r["race_id"], r["horse_id"]) for r in rows)
    duplicates = sum(v - 1 for v in key_counts.values() if v > 1)

    # ── Missing strictly_ordered_vector (stored in feature_json) ──────────
    def _has_ordered_vec(r):
        fj = r.get("feature_json")
        if isinstance(fj, dict):
            return bool(fj.get("strictly_ordered_vector"))
        if isinstance(fj, str):
            try:
                parsed = json.loads(fj)
                return bool(parsed.get("strictly_ordered_vector"))
            except Exception:
                return False
        # If feature_json is None, the row has no vector
        return False

    missing_vec = sum(1 for r in rows if not _has_ordered_vec(r))
    missing_vec_pct = 100 * missing_vec / max(total, 1)

    # ── field_size distribution (deciles) ─────────────────────────────────
    fs_vals = [r["field_size"] for r in rows if r.get("field_size") is not None]
    fs_counter = Counter(
        f"{int(v)}" if v is not None else "unknown"
        for v in fs_vals
    )
    # Group into buckets
    fs_ranges = {"2-5": (2, 5), "6-8": (6, 8), "9-12": (9, 12), "13-16": (13, 16), "17+": (17, 9999)}
    fs_deciles = {}
    for bucket, (lo, hi) in fs_ranges.items():
        fs_deciles[bucket] = sum(v for k, v in fs_counter.items() if k.isdigit() and lo <= int(k) <= hi)

    # ── SP distribution ───────────────────────────────────────────────────
    sp_bracket_counter = Counter(_sp_bracket(r.get("sp_dec")) for r in rows)

    # ── Classification logic ───────────────────────────────────────────────
    BLOCKED_REASONS = []
    if mpi_null_pct > 10:
        BLOCKED_REASONS.append(f"mpi null% = {mpi_null_pct:.1f}% (> 10% threshold)")
    if cb_null_pct > 10:
        BLOCKED_REASONS.append(f"chaos_bloom null% = {cb_null_pct:.1f}% (> 10% threshold)")
    if winner_pct < 5 or winner_pct > 40:
        BLOCKED_REASONS.append(f"winner parity = {winner_pct:.1f}% (outside 5-40% band)")
    if duplicates > 100:
        BLOCKED_REASONS.append(f"duplicate rows = {duplicates} (> 100 threshold)")
    if missing_vec_pct > 5:
        BLOCKED_REASONS.append(f"missing vectors = {missing_vec_pct:.1f}% (> 5% threshold)")

    if BLOCKED_REASONS:
        classification = "HFS_TRAINING_BLOCKED"
    elif total < 5000:
        classification = "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME"
    else:
        classification = "HFS_TRAINING_READY"

    # ── Build report ──────────────────────────────────────────────────────
    mpi_stats = _describe(mpi_vals)
    cb_stats = _describe(cb_vals)

    lines = []

    def out(line=""):
        lines.append(line)
        print(line)

    out()
    out("=" * 70)
    out("HFS SIGNAL INTEGRITY AUDIT")
    out(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    out("=" * 70)
    out()
    out("## Row Counts")
    out(f"  Total HFS rows:                    {total}")
    out(f"  2026+ rows (live era):             {len(rows_2026)}")
    out(f"  Pre-2026 archive rows:             {len(rows_pre2026)}")
    out()
    out("## MPI Signal")
    out(f"  Null count:                        {mpi_null}  ({mpi_null_pct:.1f}%)")
    out(f"  Non-null count:                    {mpi_stats['n']}")
    if mpi_stats["n"] > 0:
        out(f"  min:  {mpi_stats['min']}")
        out(f"  max:  {mpi_stats['max']}")
        out(f"  mean: {mpi_stats['mean']}")
        out(f"  std:  {mpi_stats['std']}")
    out()
    out("## Chaos Bloom Signal")
    out(f"  Null count:                        {cb_null}  ({cb_null_pct:.1f}%)")
    out(f"  Non-null count:                    {cb_stats['n']}")
    if cb_stats["n"] > 0:
        out(f"  min:  {cb_stats['min']}")
        out(f"  max:  {cb_stats['max']}")
        out(f"  mean: {cb_stats['mean']}")
        out(f"  std:  {cb_stats['std']}")
    out()
    out("## Winner / Placed Parity")
    out(f"  winner_flag=True count:            {winner_count}  ({winner_pct:.1f}%)")
    out(f"  placed_flag=True count:            {placed_count}  ({placed_pct:.1f}%)")
    out()
    out("## Data Quality")
    out(f"  Duplicate (race_id, horse_id):     {duplicates}")
    out(f"  Missing strictly_ordered_vector:   {missing_vec}  ({missing_vec_pct:.1f}%)")
    out()
    out("## Field Size Distribution")
    for bracket, count in fs_deciles.items():
        pct = 100 * count / max(total, 1)
        out(f"  {bracket}:  {count}  ({pct:.1f}%)")
    out()
    out("## SP Distribution")
    for bracket in ["evens_or_under", "2.0-4.0", "4.0-8.0", "8.0-16.0", "16.0-33.0", "33.0+", "unknown"]:
        count = sp_bracket_counter.get(bracket, 0)
        pct = 100 * count / max(total, 1)
        out(f"  {bracket}:  {count}  ({pct:.1f}%)")
    out()
    out("=" * 70)
    out(f"CLASSIFICATION: {classification}")
    out("=" * 70)
    if BLOCKED_REASONS:
        out("BLOCKED REASONS:")
        for reason in BLOCKED_REASONS:
            out(f"  - {reason}")
    else:
        out("No blocking conditions detected.")
    out()
    if classification == "HFS_TRAINING_BLOCKED":
        out("Playbook G training: BLOCKED — resolve issues above before training.")
    elif classification == "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME":
        out("Playbook G training: BLOCKED — signal repaired but row count < 5000.")
        out(f"  Current rows: {total}. Need >= 5000 before training.")
    else:
        out("Playbook G training: READY — all integrity checks pass.")
    out()

    # ── Write to data/ ─────────────────────────────────────────────────────
    out_path = ROOT / "data" / "hfs_signal_integrity_audit_latest.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(lines))
    LOG.info("Audit written to %s", out_path)
    print(f"\nAudit saved to: {out_path}")

    return classification


if __name__ == "__main__":
    main()
