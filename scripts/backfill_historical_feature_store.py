# scripts/backfill_historical_feature_store.py

"""
VÉLØ Batch Reconstructor (Phase 2) - GO-LIVE SPEC
------------------------------------------------
Rules enforced:
- EXCLUSION: Runner-level (race_id + horse_id) to prevent partial race gaps.
- ORDER: Feature vectors strictly ordered [feats[k] for k in FEATURE_COLS].
- SPECIALIST: Loads specialist_models_v1.pkl to derive mpi/chaos/integrity.
- ACCOUNTING: Temp-table staged writes for 100% accurate write-accounting.
- FORCE: reconstruction_version='V17_B1', is_synthetic=True, narrative=Null.
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import pickle
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import pvariance
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# ---- Project imports ----
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import _build_live_features, score_race_velo_prime

# ---- Configuration ----
RECONSTRUCTION_VERSION = "V17_B1"
MODELS_PATH = ROOT / "models" / "specialist_models_v1.pkl"

# SQPE v17 feature order (Must match training vector)
FEATURE_COLS = [
    "sp_dec", "log_sp", "implied_prob", "dist_f", "going_code", "is_aw", "class_num", 
    "wgt_lbs", "or_num", "rpr_num", "ts_num", "or_vs_field", "rpr_vs_field", 
    "field_size", "draw_num", "draw_pct", "age_num", "sp_rank", "is_fav"
]

LOG = logging.getLogger("backfill_historical_feature_store")

@dataclass
class RunStats:
    races_attempted: int = 0
    runners_attempted: int = 0
    rows_generated: int = 0
    rows_written: int = 0
    rows_skipped: int = 0

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

def get_conn() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if dsn: return psycopg2.connect(dsn)
    raise RuntimeError("No database connection string found.")

def fetch_unprocessed_runners_batched(
    cur: RealDictCursor,
    batch_races: int,
    last_reconciled_at: Optional[datetime],
    last_race_id: Optional[str],
    limit_remaining: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Runner-Level Atomic Exclusion:
    Finds candidates from runner_results that do not have a corresponding
    row in historical_feature_store for this reconstruction version.
    """
    eff_limit = batch_races
    if limit_remaining is not None:
        eff_limit = min(eff_limit, max(0, limit_remaining))
    if eff_limit <= 0: return []

    # Identify the next block of races that have ANY missing runners
    sql = """
    WITH next_races AS (
        SELECT DISTINCT rr.race_id, res.reconciled_at
        FROM public.runner_results rr
        JOIN public.race_results res ON rr.race_id = res.race_id
        LEFT JOIN public.historical_feature_store hfs 
               ON rr.race_id = hfs.race_id 
              AND rr.horse_id = hfs.horse_id
              AND hfs.reconstruction_version = %s
        WHERE hfs.race_id IS NULL
          AND (%s::timestamptz IS NULL OR (res.reconciled_at, res.race_id) > (%s::timestamptz, %s::text))
        ORDER BY res.reconciled_at ASC, res.race_id ASC
        LIMIT %s
    )
    SELECT r.* FROM public.race_results r
    JOIN next_races nr ON r.race_id = nr.race_id
    ORDER BY r.reconciled_at ASC, r.race_id ASC;
    """
    cur.execute(sql, (RECONSTRUCTION_VERSION, last_reconciled_at, last_reconciled_at, last_race_id, eff_limit))
    return list(cur.fetchall())

def fetch_runners_for_races(cur: RealDictCursor, race_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Helper to fetch all runners for a batch of race IDs."""
    if not race_ids: return {}
    sql = "SELECT * FROM public.runner_results WHERE race_id = ANY(%s::text[])"
    cur.execute(sql, (list(race_ids),))
    out = defaultdict(list)
    for row in cur.fetchall():
        out[row["race_id"]].append(dict(row))
    return out

def build_rows_for_race(race: Dict[str, Any], runners: List[Dict[str, Any]], spec_models: Any) -> Tuple[List[Tuple[Any, ...]], Counter, List[float], int, int]:
    rows, local_skips, chaos_values = [], Counter(), []
    sp_count, win_count = 0, 0

    nrace = {
        "race_id": race["race_id"], "course": race.get("course"),
        "going": race.get("going"), "race_class": race.get("race_class"),
        "distance_f": float(race["distance_f"]) if race.get("distance_f") else None,
        "jurisdiction": race.get("jurisdiction"),
        "runners": []
    }

    norm_runners = []
    for rr in runners:
        norm_runners.append({
            "horse_id": rr["horse_id"], "horse_name": rr.get("horse_name"),
            "draw": rr.get("draw"), "age": rr.get("age"),
            "weight_lbs": float(rr["weight_lbs"]) if rr.get("weight_lbs") else None,
            "official_rating": rr.get("official_rating"), "rpr": rr.get("rpr"), "ts": rr.get("ts"),
            "best_odds_decimal": float(rr["sp_dec"]) if rr.get("sp_dec") else None,
            "is_winner": bool(rr.get("is_winner")), "position": rr.get("position"),
            "pdf_intel": {}
        })
    nrace["runners"] = norm_runners

    preds = score_race_velo_prime(nrace, sentient_state=None)
    pred_map = {p["horse_id"]: p for p in preds}

    for r in norm_runners:
        p = pred_map.get(r["horse_id"])
        if not p: 
            local_skips["scoring_skipped_runner"] += 1
            continue

        # 1. Strict Feature Ordering
        feats = _build_live_features(r, nrace, [], [])
        vector = [[feats.get(k, 0.0) for k in FEATURE_COLS]]

        # 2. Specialist Prediction (using loaded model)
        mpi = spec_models['mpi'].predict(vector)[0] if 'mpi' in spec_models else None
        chaos = spec_models['chaos_bloom'].predict(vector)[0] if 'chaos_bloom' in spec_models else None
        integrity = spec_models['integrity_score'].predict(vector)[0] if 'integrity_score' in spec_models else None

        if r["best_odds_decimal"]: sp_count += 1
        if r["is_winner"]: win_count += 1
        if chaos is not None: chaos_values.append(chaos)

        rows.append((
            nrace["race_id"], r["horse_id"], r["horse_name"], RECONSTRUCTION_VERSION,
            race.get("reconciled_at").date(), nrace["course"], nrace["jurisdiction"],
            nrace["distance_f"], nrace["going"], nrace["race_class"], len(runners),
            r["draw"], r["age"], r["weight_lbs"],
            r["official_rating"], r["rpr"], r["ts"],
            r["best_odds_decimal"], (1.0/r["best_odds_decimal"]) if r["best_odds_decimal"] and r["best_odds_decimal"] > 0 else None,
            feats.get("or_vs_field"), feats.get("rpr_vs_field"), feats.get("draw_pct"),
            mpi, chaos, integrity, feats.get("power_anchor"),
            feats.get("plot_conviction"), feats.get("or_delta_to_best_win"),
            r["is_winner"], bool(r["position"] in [2,3]), r["position"],
            True, None, None, # is_synthetic, narrative, story
            ['race_results', 'runner_results'], json.dumps(feats)
        ))

    return rows, local_skips, chaos_values, sp_count, win_count

def main() -> None:
    parser = argparse.ArgumentParser(description="VÉLØ Batch Reconstructor (Go-Live)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-races", type=int, default=None)
    parser.add_argument("--batch-races", type=int, default=2000)
    args = parser.parse_args()

    configure_logging()
    if not MODELS_PATH.exists(): LOG.error(f"Models missing: {MODELS_PATH}"); sys.exit(1)
    with MODELS_PATH.open("rb") as f: spec_models = pickle.load(f)
    
    conn = get_conn(); cur = conn.cursor(cursor_factory=RealDictCursor)
    stats = RunStats(); global_skips = Counter()
    
    run_id = None
    if not args.dry_run:
        cur.execute("INSERT INTO public.historical_feature_backfill_runs (reconstruction_version) VALUES (%s) RETURNING id", (RECONSTRUCTION_VERSION,))
        run_id = cur.fetchone()["id"]; conn.commit()

    last_reconciled_at, last_race_id = None, None
    limit_rem = args.limit_races

    try:
        while True:
            races = fetch_unprocessed_runners_batched(cur, args.batch_races, last_reconciled_at, last_race_id, limit_rem)
            if not races: break

            by_race = fetch_runners_for_races(cur, [r["race_id"] for r in races])
            batch_rows, batch_chaos, batch_winners, runners_in_batch = [], [], 0, 0

            for race in races:
                runners = by_race.get(race["race_id"], [])
                if not runners: global_skips["empty_race"] += 1; continue
                
                rows, local_skips, chaos, sp_c, wins = build_rows_for_race(race, runners, spec_models)
                batch_rows.extend(rows); batch_chaos.extend(chaos); batch_winners += wins; 
                runners_in_batch += len(runners); global_skips.update(local_skips)

            if not batch_rows: raise RuntimeError("Fail-fast: Zero rows generated")
            if not batch_winners: raise RuntimeError("Fail-fast: No winners in batch")
            if len(batch_chaos) > 1 and pvariance(batch_chaos) == 0: raise RuntimeError("Fail-fast: Zero variance in metrics")

            if not args.dry_run:
                cur.execute("CREATE TEMP TABLE tmp_hfs (LIKE public.historical_feature_store INCLUDING DEFAULTS) ON COMMIT DROP")
                cols = """race_id, horse_id, horse_name, reconstruction_version, race_date, course, jurisdiction,
                          distance_f, going, race_class, field_size, draw, age, weight_lbs,
                          official_rating, rpr, ts, sp_dec, implied_prob, or_vs_field, rpr_vs_field, draw_pct,
                          mpi, chaos_bloom, integrity_score, power_anchor, plot_conviction, or_delta_to_best_win,
                          winner_flag, placed_flag, finish_position, is_synthetic, narrative_disruption, story_anchor,
                          source_tables, feature_json"""
                execute_values(cur, f"INSERT INTO tmp_hfs ({cols}) VALUES %s", batch_rows)
                
                cur.execute(f"INSERT INTO public.historical_feature_store ({cols}) SELECT * FROM tmp_hfs ON CONFLICT (race_id, horse_id, reconstruction_version) DO NOTHING")
                written = cur.rowcount
                stats.rows_written += written
                stats.rows_skipped += (len(batch_rows) - written)
                conn.commit()
            else:
                LOG.info(f"[DRY-RUN] Sample: {batch_rows[0][0]} | {batch_rows[0][2]}")

            stats.races_attempted += len(races); stats.runners_attempted += runners_in_batch; stats.rows_generated += len(batch_rows)
            last = races[-1]; last_reconciled_at, last_race_id = last["reconciled_at"], last["race_id"]
            if limit_rem:
                limit_rem -= len(races)
                if limit_rem <= 0: break

        if run_id:
            cur.execute("""UPDATE public.historical_feature_backfill_runs SET 
                        status='completed', finished_at=NOW(), rows_written=%s, 
                        rows_attempted=%s, rows_skipped=%s, skip_reasons=%s::jsonb 
                        WHERE id=%s""", 
                        (stats.rows_written, stats.rows_generated, stats.rows_skipped, json.dumps(dict(global_skips)), run_id))
            conn.commit()

    except Exception as e:
        if run_id: 
            conn.rollback()
            cur.execute("UPDATE public.historical_feature_backfill_runs SET status='failed', finished_at=NOW(), error_message=%s WHERE id=%s", (str(e), run_id))
            conn.commit()
        LOG.exception("Backfill failed"); raise e
    finally:
        LOG.info(f"Final Summary: {stats.races_attempted} races attempted | {stats.rows_written} written.")
        cur.close(); conn.close()

if __name__ == "__main__":
    main()
