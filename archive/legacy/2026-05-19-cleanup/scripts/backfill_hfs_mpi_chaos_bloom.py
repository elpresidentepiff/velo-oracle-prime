"""
backfill_hfs_mpi_chaos_bloom.py
================================
Populate NULL mpi / chaos_bloom in historical_feature_store by computing
them from velo_verdicts source data (full_analysis.predictions per race).

Formula version: hfs_signal_contract_v1 (identical to VeloPrimePrediction._compute_hfs_signals)
  mpi         = velo_prime_prob * 0.6 + market_deception_score * 0.4  (bounded 0-1, null-safe)
  chaos_bloom = macro entropy from macro_chaos_mode + favourite_trap_risk (bounded 0-1, null-safe)

Usage:
    python scripts/backfill_hfs_mpi_chaos_bloom.py --dry-run
    python scripts/backfill_hfs_mpi_chaos_bloom.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
LOG = logging.getLogger("backfill_hfs_mpi_chaos_bloom")

SIGNAL_CONTRACT_VERSION = "hfs_signal_contract_v1"


# ── Formula (identical to VeloPrimePrediction._compute_hfs_signals) ────────────

def _compute_mpi(vp: Optional[float], mds: Optional[float]) -> Tuple[Optional[float], str, Optional[str]]:
    """Returns (mpi, mpi_source, mpi_block_reason)."""
    if vp is not None and mds is not None:
        raw = (vp * 0.6) + (mds * 0.4)
        return round(min(1.0, max(0.0, raw)), 4), "derived_from_vp_mds", None
    elif vp is not None:
        return round(min(1.0, max(0.0, vp)), 4), "derived_from_vp_only", "mds_missing"
    else:
        return None, "", "velo_prime_prob_missing"


def _compute_chaos_bloom(
    chaos_mode: Optional[Any], trap_risk: Optional[str]
) -> Tuple[Optional[float], str, Optional[str]]:
    """Returns (chaos_bloom, chaos_bloom_source, chaos_bloom_block_reason)."""
    if chaos_mode is None and trap_risk is None:
        return None, "", "macro_context_missing"

    base = 0.3
    if chaos_mode:
        base += 0.4
    if trap_risk in ("high", "HIGH", True, 1):
        base += 0.3
    elif trap_risk in ("medium", "MEDIUM"):
        base += 0.15
    return round(min(1.0, max(0.0, base)), 4), "derived_from_macro_field_trap", None


# ── Stats helper ───────────────────────────────────────────────────────────────

def _describe(values: List[float]) -> str:
    if not values:
        return "n=0"
    n = len(values)
    mn = min(values)
    mx = max(values)
    avg = statistics.mean(values)
    std = statistics.stdev(values) if n >= 2 else 0.0
    return f"n={n}  min={mn:.4f}  max={mx:.4f}  mean={avg:.4f}  std={std:.4f}"


# ── Supabase REST pagination ───────────────────────────────────────────────────

def _fetch_all(sb, table: str, select: str, filters: dict | None = None, page_size: int = 1000) -> List[dict]:
    """Paginate through all rows using range header."""
    rows = []
    offset = 0
    while True:
        q = sb.table(table).select(select).range(offset, offset + page_size - 1)
        if filters:
            for col, val in filters.items():
                if val == "IS NULL":
                    q = q.is_(col, "null")
                else:
                    q = q.eq(col, val)
        result = q.execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


# ── Main logic ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill mpi / chaos_bloom in historical_feature_store")
    parser.add_argument("--dry-run", action="store_true", help="Report proposed updates, no writes")
    parser.add_argument("--apply", action="store_true", help="Execute updates to DB")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of HFS rows to scan")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("Pass --dry-run or --apply")

    # Load .env
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

    # ── Step 1: Total counts from HFS ────────────────────────────────────────
    LOG.info("Fetching HFS totals...")

    # Fetch all HFS rows to get totals and nulls
    LOG.info("Fetching all HFS rows (may take a moment)...")
    all_hfs = _fetch_all(sb, "historical_feature_store", "race_id,horse_id,horse_name,mpi,chaos_bloom,feature_json")
    hfs_total = len(all_hfs)
    mpi_null_rows = [r for r in all_hfs if r.get("mpi") is None]
    cb_null_rows = [r for r in all_hfs if r.get("chaos_bloom") is None]
    mpi_null_count = len(mpi_null_rows)
    cb_null_count = len(cb_null_rows)

    # Rows with either null
    target_rows = [r for r in all_hfs if r.get("mpi") is None or r.get("chaos_bloom") is None]
    if args.limit:
        target_rows = target_rows[:args.limit]

    LOG.info("HFS total rows: %d", hfs_total)
    LOG.info("HFS mpi NULL:       %d (%.1f%%)", mpi_null_count, 100 * mpi_null_count / max(hfs_total, 1))
    LOG.info("HFS chaos_bloom NULL: %d (%.1f%%)", cb_null_count, 100 * cb_null_count / max(hfs_total, 1))
    LOG.info("Rows to process (mpi OR cb NULL): %d", len(target_rows))

    if not target_rows:
        LOG.info("Nothing to backfill — no NULL rows found.")
        return

    # ── Step 2: Build signal index from velo_verdicts ────────────────────────
    LOG.info("Fetching velo_verdicts for signal reconstruction...")
    vv_rows = _fetch_all(
        sb, "velo_verdicts",
        "race_id,full_analysis,velo_prime_prob,market_deception_score,top_rank_horse_id"
    )
    LOG.info("velo_verdicts rows fetched: %d", len(vv_rows))

    # Build (race_id, horse_id) → signal dict index from full_analysis.predictions
    signal_index: Dict[Tuple[str, str], Dict] = {}
    for vv in vv_rows:
        race_id = vv.get("race_id")
        if not race_id:
            continue
        fa = vv.get("full_analysis")
        if isinstance(fa, str):
            try:
                fa = json.loads(fa)
            except Exception:
                fa = {}
        if not isinstance(fa, dict):
            fa = {}

        predictions = fa.get("predictions", [])
        if not isinstance(predictions, list):
            predictions = []

        for runner in predictions:
            if not isinstance(runner, dict):
                continue
            h_id = runner.get("horse_id") or ""
            if not h_id:
                continue
            key = (race_id, h_id)
            signal_index[key] = {
                "velo_prime_prob": runner.get("velo_prime_prob"),
                "market_deception_score": runner.get("market_deception_score"),
                "macro_chaos_mode": runner.get("macro_chaos_mode"),
                "favourite_trap_risk": runner.get("favourite_trap_risk"),
            }

    LOG.info("Signal index entries built: %d", len(signal_index))

    # ── Step 3: Compute proposed updates ─────────────────────────────────────
    proposed: List[Dict] = []
    blocked_mpi = 0
    blocked_cb = 0
    eligible_mpi = 0
    eligible_cb = 0

    mpi_values: List[float] = []
    cb_values: List[float] = []

    for row in target_rows:
        race_id = row["race_id"]
        horse_id = row["horse_id"]
        current_mpi = row.get("mpi")
        current_cb = row.get("chaos_bloom")

        # Try signal_index first
        signals = signal_index.get((race_id, horse_id))

        # Fall back to feature_json on the HFS row itself
        if not signals:
            fj = row.get("feature_json")
            if isinstance(fj, str):
                try:
                    fj = json.loads(fj)
                except Exception:
                    fj = {}
            if isinstance(fj, dict) and fj:
                signals = {
                    "velo_prime_prob": fj.get("velo_prime_prob"),
                    "market_deception_score": fj.get("market_deception_score"),
                    "macro_chaos_mode": fj.get("macro_chaos_mode"),
                    "favourite_trap_risk": fj.get("favourite_trap_risk"),
                }
            else:
                signals = {}

        vp = signals.get("velo_prime_prob")
        mds = signals.get("market_deception_score")
        chaos_mode = signals.get("macro_chaos_mode")
        trap_risk = signals.get("favourite_trap_risk")

        # Compute MPI (only if currently NULL)
        new_mpi = current_mpi
        new_mpi_source = None
        new_mpi_block = None
        if current_mpi is None:
            new_mpi, new_mpi_source, new_mpi_block = _compute_mpi(vp, mds)
            if new_mpi is not None:
                eligible_mpi += 1
                mpi_values.append(new_mpi)
            else:
                blocked_mpi += 1

        # Compute chaos_bloom (only if currently NULL)
        new_cb = current_cb
        new_cb_source = None
        new_cb_block = None
        if current_cb is None:
            new_cb, new_cb_source, new_cb_block = _compute_chaos_bloom(chaos_mode, trap_risk)
            if new_cb is not None:
                eligible_cb += 1
                cb_values.append(new_cb)
            else:
                blocked_cb += 1

        # Only include if there's something to update
        has_mpi_update = current_mpi is None and new_mpi is not None
        has_cb_update = current_cb is None and new_cb is not None
        if has_mpi_update or has_cb_update:
            proposed.append({
                "race_id": race_id,
                "horse_id": horse_id,
                "horse_name": row.get("horse_name", ""),
                "before_mpi": current_mpi,
                "before_cb": current_cb,
                "new_mpi": new_mpi if has_mpi_update else current_mpi,
                "new_cb": new_cb if has_cb_update else current_cb,
                "mpi_source": new_mpi_source,
                "cb_source": new_cb_source,
                "mpi_block": new_mpi_block,
                "cb_block": new_cb_block,
            })

    # ── Step 4: Report ────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("BACKFILL HFS MPI / CHAOS BLOOM — DRY-RUN STATS" if args.dry_run else "BACKFILL HFS MPI / CHAOS BLOOM — APPLY")
    print("=" * 70)
    print(f"HFS rows scanned:                    {len(target_rows)}")
    print(f"HFS total rows:                      {hfs_total}")
    print(f"Rows with mpi NULL:                  {mpi_null_count}  ({100*mpi_null_count/max(hfs_total,1):.1f}%)")
    print(f"Rows with chaos_bloom NULL:          {cb_null_count}  ({100*cb_null_count/max(hfs_total,1):.1f}%)")
    print()
    print(f"Signal index coverage:               {len(signal_index)} (race_id, horse_id) pairs from velo_verdicts")
    print()
    print(f"MPI eligible for repair:             {eligible_mpi}")
    print(f"MPI blocked (missing inputs):        {blocked_mpi}")
    print(f"chaos_bloom eligible for repair:     {eligible_cb}")
    print(f"chaos_bloom blocked:                 {blocked_cb}")
    print()
    print(f"Rows with at least one update:       {len(proposed)}")
    print()
    print(f"MPI distribution (proposed):         {_describe(mpi_values)}")
    print(f"chaos_bloom distribution (proposed): {_describe(cb_values)}")
    print()

    # Sample 20
    sample = proposed[:20]
    if sample:
        print("Sample 20 proposed updates:")
        print(f"  {'race_id':<18} {'horse_id':<18} {'horse_name':<25} {'mpi_before':>10} {'mpi_after':>10} {'cb_before':>10} {'cb_after':>10}")
        print("  " + "-" * 102)
        for p in sample:
            print(
                f"  {str(p['race_id']):<18} {str(p['horse_id']):<18} {str(p['horse_name'])[:24]:<25}"
                f"  {str(p['before_mpi']):>10} {str(p['new_mpi']):>10}"
                f"  {str(p['before_cb']):>10} {str(p['new_cb']):>10}"
            )
    print()

    if args.dry_run:
        print("DRY-RUN mode — no writes performed.")
        print("To apply: python scripts/backfill_hfs_mpi_chaos_bloom.py --apply")
        return

    # ── Step 5: Apply ─────────────────────────────────────────────────────────
    updated = 0
    errors = 0
    BATCH_SIZE = 100

    for i in range(0, len(proposed), BATCH_SIZE):
        batch = proposed[i:i + BATCH_SIZE]
        for p in batch:
            try:
                update_payload = {}
                if p["before_mpi"] is None and p["new_mpi"] is not None:
                    update_payload["mpi"] = p["new_mpi"]
                if p["before_cb"] is None and p["new_cb"] is not None:
                    update_payload["chaos_bloom"] = p["new_cb"]
                if not update_payload:
                    continue
                sb.table("historical_feature_store").update(update_payload).eq(
                    "race_id", p["race_id"]
                ).eq("horse_id", p["horse_id"]).execute()
                updated += 1
            except Exception as e:
                LOG.error("Update failed for race=%s horse=%s: %s", p["race_id"], p["horse_id"], e)
                errors += 1

        LOG.info("Progress: %d / %d rows applied", min(i + BATCH_SIZE, len(proposed)), len(proposed))

    print(f"APPLY complete: {updated} rows updated, {errors} errors.")
    LOG.info("Backfill complete: updated=%d errors=%d", updated, errors)


if __name__ == "__main__":
    main()
