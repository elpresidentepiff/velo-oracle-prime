# scripts/backfill_historical_feature_store.py

"""
VÉLØ Batch Reconstructor (Phase 2) - HTTP PRODUCTION SPEC
---------------------------------------------------------
Rules enforced:
- NETWORK: Uses Supabase HTTP Client to bypass port 5432 restrictions.
- EXCLUSION: Runner-level (race_id + horse_id) atomic exclusion.
- ACCOUNTING: Manual heartbeat persistence for write-accounting.
- MODELS: Uses production ModelManager for specialist derivation.
"""

from __future__ import annotations
import argparse
import gc
import json
import logging
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import pvariance
from typing import Any, Dict, List, Optional, Sequence, Tuple

from supabase import create_client, Client

# ---- Project imports ----
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import _build_live_features, score_race_velo_prime
from app.services.model_manager import get_model_manager

# ---- Configuration ----
RECONSTRUCTION_VERSION = "V17_B1"
LOG = logging.getLogger("backfill_historical_feature_store")

@dataclass
class RunStats:
    races_attempted: int = 0
    runners_attempted: int = 0
    rows_generated: int = 0
    rows_written: int = 0
    rows_skipped: int = 0
    batches_processed: int = 0

def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

def get_sb_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY).")
    return create_client(url, key)

def fetch_unprocessed_runners_batched(
    sb: Client,
    batch_races: int,
    offset: int = 0,
    limit_races: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetches raw races. Complex exclusion logic is handled per race 
    to accommodate HTTP API constraints.
    """
    eff_limit = batch_races
    if limit_races is not None:
        eff_limit = min(eff_limit, limit_races)
    
    # Fetch recent races
    res = sb.table("race_results") \
        .select("*") \
        .order("reconciled_at", desc=False) \
        .range(offset, offset + eff_limit - 1) \
        .execute()
    return res.data or []

def fetch_runners_for_race(sb: Client, race_id: str) -> List[Dict[str, Any]]:
    res = sb.table("runner_results").select("*").eq("race_id", race_id).execute()
    return res.data or []

def check_runner_processed(sb: Client, race_id: str, horse_id: str) -> bool:
    res = sb.table("historical_feature_store") \
        .select("id") \
        .eq("race_id", race_id) \
        .eq("horse_id", horse_id) \
        .eq("reconstruction_version", RECONSTRUCTION_VERSION) \
        .limit(1) \
        .execute()
    return len(res.data) > 0

def build_rows_for_race(is_dry_run, 
    race: Dict[str, Any],
    runners: List[Dict[str, Any]],
    mm: Any,
    sb: Client
) -> Tuple[List[Dict[str, Any]], Counter, List[float], int, int]:
    rows: List[Dict[str, Any]] = []
    local_skips = Counter()
    chaos_values: List[float] = []
    sp_count, win_count = 0, 0

    norm_runners = []
    for rr in runners:
        # Check exclusion at runner level
        if not is_dry_run and check_runner_processed(sb, race["race_id"], rr["horse_id"]):
            local_skips["already_processed"] += 1
            continue

        norm_runners.append({
            "horse_id": rr["horse_id"], "horse_name": rr.get("horse_name"),
            "draw": rr.get("draw"), "age": rr.get("age"),
            "weight_lbs": float(rr["weight_lbs"]) if rr.get("weight_lbs") is not None else None,
            "official_rating": rr.get("official_rating"), "rpr": rr.get("rpr"), "ts": rr.get("ts"),
            "best_odds_decimal": float(rr["sp_dec"]) if rr.get("sp_dec") is not None else None,
            "is_winner": bool(rr.get("is_winner")), "position": rr.get("position"),
            "pdf_intel": {},
        })

    if not norm_runners:
        return [], local_skips, [], 0, 0

    nrace = {
        "race_id": race["race_id"], "course": race.get("course"),
        "going": race.get("going"), "race_class": race.get("race_class"),
        "distance_f": float(race["distance_f"]) if race.get("distance_f") is not None else None,
        "jurisdiction": race.get("jurisdiction"), "runners": norm_runners,
    }

    preds = score_race_velo_prime(nrace, sentient_state=None)
    pred_map = {p["horse_id"]: p for p in preds if p.get("horse_id") is not None}

    for r in norm_runners:
        p = pred_map.get(r["horse_id"])
        if not p:
            local_skips["missing_prediction"] += 1; continue

        feats = _build_live_features(r, nrace, [], [])
        ordered_vec = [feats.get(k, 0.0) for k in mm.ALL_V17_FEATURES]
        payload = dict(p)
        payload["strictly_ordered_vector"] = ordered_vec
        
        if r["best_odds_decimal"] is not None: sp_count += 1
        if r["is_winner"]: win_count += 1
        if payload.get("chaos_bloom") is not None: chaos_values.append(payload["chaos_bloom"])

        rows.append({
            "race_id": nrace["race_id"],
            "horse_id": r["horse_id"],
            "horse_name": r["horse_name"],
            "reconstruction_version": RECONSTRUCTION_VERSION,
            "race_date": race.get("reconciled_at")[:10] if race.get("reconciled_at") else None,
            "course": nrace["course"],
            "jurisdiction": nrace["jurisdiction"],
            "distance_f": nrace["distance_f"],
            "going": nrace["going"],
            "race_class": nrace["race_class"],
            "field_size": len(runners),
            "draw": r["draw"],
            "age": r["age"],
            "weight_lbs": r["weight_lbs"],
            "official_rating": r["official_rating"],
            "rpr": r["rpr"],
            "ts": r["ts"],
            "sp_dec": r["best_odds_decimal"],
            "implied_prob": (1.0 / r["best_odds_decimal"]) if (r["best_odds_decimal"] and r["best_odds_decimal"] > 0) else None,
            "or_vs_field": payload.get("or_vs_field"),
            "rpr_vs_field": payload.get("rpr_vs_field"),
            "draw_pct": payload.get("draw_pct"),
            "mpi": payload.get("mpi"),
            "chaos_bloom": payload.get("chaos_bloom"),
            "integrity_score": payload.get("integrity_score"),
            "power_anchor": payload.get("power_anchor"),
            "plot_conviction": payload.get("plot_conviction"),
            "or_delta_to_best_win": payload.get("or_delta_to_best_win"),
            "winner_flag": r["is_winner"],
            "placed_flag": bool(r["position"] in [2, 3]),
            "finish_position": r["position"],
            "is_synthetic": True,
            "source_tables": ["race_results", "runner_results"],
            "feature_json": payload,
        })
    return rows, local_skips, chaos_values, sp_count, win_count

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-races", type=int, default=None)
    parser.add_argument("--batch-races", type=int, default=10) # Smaller batch for HTTP
    parser.add_argument("--heartbeat-every", type=int, default=5)
    args = parser.parse_args()
    configure_logging()
    
    mm = get_model_manager()
    if not mm.get_status().get("initialized"):
        LOG.error("ModelManager failed initialization."); sys.exit(1)
    
    sb = get_sb_client()
    stats = RunStats(); global_skips = Counter()
    
    run_id = None
    if not args.dry_run:
        res = sb.table("historical_feature_backfill_runs").insert({"reconstruction_version": RECONSTRUCTION_VERSION}).execute()
        run_id = res.data[0]["id"]

    offset = 0
    limit_remaining = args.limit_races

    try:
        while True:
            races = fetch_unprocessed_runners_batched(sb, args.batch_races, offset, limit_remaining)
            if not races: break

            batch_rows, batch_chaos, batch_winners, runners_in_batch = [], [], 0, 0

            for race in races:
                runners = fetch_runners_for_race(sb, race["race_id"])
                if not runners:
                    global_skips["empty_race"] += 1; continue
                
                rows, l_skips, chaos_vals, _sp_c, wins = build_rows_for_race(args.dry_run, race, runners, mm, sb)
                batch_rows.extend(rows); batch_chaos.extend(chaos_vals); batch_winners += wins; 
                runners_in_batch += len(runners); global_skips.update(l_skips)
            
            if batch_rows and not args.dry_run:
                sb.table("historical_feature_store").upsert(batch_rows).execute()
                stats.rows_written += len(batch_rows)
            elif args.dry_run and batch_rows:
                LOG.info(f"[DRY-RUN] Sample: {batch_rows[0]['race_id']} | winners={batch_winners}")

            stats.races_attempted += len(races); stats.runners_attempted += runners_in_batch; stats.rows_generated += len(batch_rows); stats.batches_processed += 1
            offset += len(races)
            
            if limit_remaining is not None:
                limit_remaining -= len(races)
                if limit_remaining <= 0: break
            
            if run_id and (stats.batches_processed % args.heartbeat_every == 0):
                sb.table("historical_feature_backfill_runs").update({"rows_written": stats.rows_written, "rows_attempted": stats.rows_generated}).eq("id", run_id).execute()
                LOG.info(f"Heartbeat: {stats.rows_written} rows written.")

        if run_id:
            sb.table("historical_feature_backfill_runs").update({"status": "completed", "finished_at": datetime.now().isoformat()}).eq("id", run_id).execute()
    except Exception as e:
        if run_id: 
            sb.table("historical_feature_backfill_runs").update({"status": "failed", "error_message": str(e)}).eq("id", run_id).execute()
        LOG.exception("Backfill failure"); raise
    finally:
        LOG.info(f"Final: races={stats.races_attempted} | written={stats.rows_written}")

if __name__ == "__main__":
    main()
