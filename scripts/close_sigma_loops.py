"""
VÉLØ — Sigma Loop Closer
========================
Pulls today's results from Racing API, reconciles against stored verdicts,
populates race_results / runner_results / velo_post_race_reviews / sigma_audits.

Single-run guard via pipeline_runs table — aborts if a run is already in_progress.

Run: python scripts/close_sigma_loops.py [--date YYYY-MM-DD]
"""

import os
import sys
import json
import logging
import argparse
import uuid
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("velo.sigma_closer")

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
RACING_API_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com").rstrip("/")
RACING_USER     = os.getenv("RACING_API_USERNAME", "")
RACING_PASS     = os.getenv("RACING_API_PASSWORD", "")
SUPA_URL        = os.getenv("SUPABASE_URL", "")
SUPA_KEY        = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                   or os.getenv("SUPABASE_SERVICE_KEY")
                   or os.getenv("SUPABASE_KEY", ""))

RUN_TYPE = "results_reconciliation"


# ─────────────────────────────────────────────────────────────
# Single-run guard
# ─────────────────────────────────────────────────────────────
def acquire_run_lock(db: Client, source_date: str) -> Optional[str]:
    """
    Insert a pipeline_run row with status=in_progress.
    Returns run_id if acquired, None if a run is already in_progress.
    """
    # Check for stale/active runs for this type + date
    existing = (
        db.table("pipeline_runs")
        .select("id, status, started_at")
        .eq("run_type", RUN_TYPE)
        .eq("source_date", source_date)
        .eq("status", "in_progress")
        .execute()
    )
    if existing.data:
        run = existing.data[0]
        log.warning(
            "Run already in_progress (id=%s started_at=%s). Aborting.",
            run["id"], run["started_at"],
        )
        return None

    run_id = str(uuid.uuid4())
    db.table("pipeline_runs").insert({
        "id": run_id,
        "service_name": "velo_sigma_closer",
        "run_type": RUN_TYPE,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "source_date": source_date,
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development"),
    }).execute()
    log.info("Run lock acquired: %s", run_id)
    return run_id


def release_run_lock(
    db: Client,
    run_id: str,
    status: str,
    races: int = 0,
    runners: int = 0,
    results: int = 0,
    error: Optional[str] = None,
) -> None:
    db.table("pipeline_runs").update({
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "races_processed": races,
        "runners_processed": runners,
        "results_processed": results,
        "error_message": error,
    }).eq("id", run_id).execute()
    log.info("Run lock released: %s → %s", run_id, status)


# ─────────────────────────────────────────────────────────────
# Racing API fetch
# ─────────────────────────────────────────────────────────────
def fetch_results(target_date: str) -> List[Dict]:
    """
    Fetch results from Racing API.
    Uses /v1/results/today for today, /v1/results?date=YYYY-MM-DD for past dates.
    """
    if not RACING_USER or not RACING_PASS:
        raise EnvironmentError("RACING_API_USERNAME / RACING_API_PASSWORD not set")

    session = requests.Session()
    session.auth = (RACING_USER, RACING_PASS)
    session.headers["Accept"] = "application/json"

    today = str(date.today())
    # Strip any trailing /v1 from base to avoid double-pathing
    base = RACING_API_BASE.rstrip("/").removesuffix("/v1")
    if target_date == today:
        url = f"{base}/v1/results/today"
        params = {}
    else:
        url = f"{base}/v1/results"
        params = {"date": target_date}

    log.info("GET %s %s", url, params or "")
    resp = session.get(url, params=params, timeout=30)

    if resp.status_code == 402:
        log.error("Racing API returned 402 — subscription tier does not include results. "
                  "Upgrade to Standard/Pro plan.")
        return []
    if resp.status_code == 404:
        log.warning("No results found for %s (404)", target_date)
        return []

    resp.raise_for_status()
    data = resp.json()

    # API returns either a list or {"results": [...]}
    if isinstance(data, list):
        return data
    return data.get("results", [])


# ─────────────────────────────────────────────────────────────
# Insert race_results + runner_results
# ─────────────────────────────────────────────────────────────
def store_race_result(db: Client, race_id: str, api_result: Dict) -> int:
    """
    Upsert one race into race_results.
    Returns count of runner_results inserted.
    """
    now = datetime.now(timezone.utc).isoformat()

    # race_results row
    race_row = {
        "race_id": race_id,
        "winning_time_detail": api_result.get("winning_time"),
        "tote_win": _safe_float(api_result.get("tote_win")),
        "tote_place": api_result.get("tote_place"),       # jsonb
        "tote_exacta": _safe_float(api_result.get("tote_exacta")),
        "tote_csf": _safe_float(api_result.get("tote_csf")),
        "tote_trifecta": _safe_float(api_result.get("tote_trifecta")),
        "tote_tricast": _safe_float(api_result.get("tote_tricast")),
        "non_runners": api_result.get("non_runners", []),
        "reconciled_at": now,
    }
    db.table("race_results").upsert(race_row, on_conflict="race_id").execute()

    # runner_results rows
    runners = api_result.get("runners", [])
    count = 0
    for r in runners:
        horse_id = r.get("horse_id") or r.get("id", "")
        if not horse_id:
            continue
        position = _safe_int(r.get("position"))
        row = {
            "race_id": race_id,
            "horse_id": horse_id,
            "position": position,
            "position_text": str(r.get("position", "")),
            "sp": str(r.get("sp", "")),
            "sp_dec": _safe_float(r.get("sp_dec") or r.get("sp")),
            "bsp": _safe_float(r.get("bsp")),
            "btn": _safe_float(r.get("btn")),
            "ovr_btn": _safe_float(r.get("ovr_btn")),
            "time": r.get("time", ""),
            "prize": _safe_float(r.get("prize")),
            "in_running_comment": r.get("in_running_comment", ""),
            "is_winner": (position == 1),
        }
        db.table("runner_results").upsert(
            row, on_conflict="race_id,horse_id"
        ).execute()
        count += 1

    log.info("  race %s → %d runner_results stored", race_id, count)
    return count


# ─────────────────────────────────────────────────────────────
# Generate post-race reviews
# ─────────────────────────────────────────────────────────────
def generate_review(
    db: Client,
    verdict: Dict,
    api_result: Dict,
    runners_result: List[Dict],
) -> Dict:
    """
    Compare a verdict against actual results.
    Returns a velo_post_race_reviews row.
    """
    top_pick_id = verdict["top_rank_horse_id"]
    verdict_id  = verdict["verdict_id"]
    race_id     = verdict["race_id"]

    # Find winner from runners_result (position may be string from API)
    winner = next((r for r in runners_result if _safe_int(r.get("position")) == 1), None)
    winner_id = winner.get("horse_id", "") if winner else ""
    winner_sp = _safe_float(winner.get("sp_dec")) if winner else None

    # Find top_pick in results
    top_pick_result = next(
        (r for r in runners_result if r.get("horse_id") == top_pick_id), None
    )
    top_pick_pos = _safe_int(top_pick_result.get("position")) if top_pick_result else None
    top_pick_won    = (top_pick_pos == 1)
    top_pick_placed = (top_pick_pos is not None and top_pick_pos <= 3)

    # Accuracy score: 1.0 = win, 0.5 = placed, 0.0 = miss
    if top_pick_won:
        accuracy = 1.0
        outcome_label = "WIN"
    elif top_pick_placed:
        accuracy = 0.5
        outcome_label = "PLACED"
    else:
        accuracy = 0.0
        outcome_label = "MISS"

    # Classify miss reason
    miss_reason = None
    patch_note  = None
    if not top_pick_won:
        top_score = float(verdict.get("top_rank_score", 0))
        confidence = verdict.get("confidence_level", "")
        selections = verdict.get("selections", [])

        if confidence == "HIGH" and not top_pick_won:
            miss_reason = "high_confidence_miss"
            patch_note = (
                f"HIGH confidence pick {top_pick_id} finished pos={top_pick_pos}. "
                f"Winner was {winner_id} (SP {winner_sp}). "
                f"Review: class_anchor_overtrusted or release_window_missed."
            )
        elif top_pick_pos is None:
            miss_reason = "non_runner_or_untracked"
        elif winner_sp and winner_sp > 10:
            miss_reason = "outsider_hedge_omitted"
            patch_note = f"Winner {winner_id} was {winner_sp} SP — longshot not in selections."
        else:
            miss_reason = "market_decoy_followed"

    # Full review outcome
    selections = verdict.get("selections", [])
    placed_selections = []
    for sel in selections:
        horse_id = sel.get("horse_id", "")
        result = next((r for r in runners_result if r.get("horse_id") == horse_id), None)
        if result:
            placed_selections.append({
                "horse_id": horse_id,
                "position": result.get("position"),
                "sp": result.get("sp_dec"),
                "outcome": "win" if _safe_int(result.get("position")) == 1 else
                           "placed" if (_safe_int(result.get("position")) or 99) <= 3 else "miss",
            })

    review_outcome = {
        "outcome": outcome_label,
        "top_pick_position": top_pick_pos,
        "winner_id": winner_id,
        "winner_sp": winner_sp,
        "miss_reason": miss_reason,
        "patch_note": patch_note,
        "selections_results": placed_selections,
        "verdict_confidence": verdict.get("confidence_level"),
        "verdict_score": float(verdict.get("top_rank_score", 0)),
    }

    notes = (
        f"{outcome_label}: {top_pick_id} pos={top_pick_pos}, "
        f"winner={winner_id}@{winner_sp}SP. "
        f"{'Patch: ' + patch_note if patch_note else ''}"
    )

    return {
        "verdict_id": verdict_id,
        "race_id": race_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "top_pick_won": top_pick_won,
        "top_pick_placed": top_pick_placed,
        "top_pick_position": top_pick_pos,
        "actual_winner_id": winner_id,
        "actual_winner_sp": winner_sp,
        "verdict_accuracy_score": accuracy,
        "review_outcome": review_outcome,
        "notes": notes[:500],
    }


def write_sigma_audit(db: Client, race_id: str, review: Dict, verdict: Dict) -> None:
    outcome = review["review_outcome"]
    db.table("sigma_audits").insert({
        "event_type": "post_race_review",
        "race_id": race_id,
        "horse_id": verdict.get("top_rank_horse_id"),
        "verdict_id": review["verdict_id"],
        "outcome": outcome.get("outcome"),
        "miss_reason": outcome.get("miss_reason"),
        "patch_note": outcome.get("patch_note"),
        "confidence_level": verdict.get("confidence_level"),
        "verdict_score": float(verdict.get("top_rank_score", 0)),
        "top_pick_position": review.get("top_pick_position"),
        "actual_winner_id": review.get("actual_winner_id"),
        "actual_winner_sp": review.get("actual_winner_sp"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


# ─────────────────────────────────────────────────────────────
# Create rp_imports storage bucket
# ─────────────────────────────────────────────────────────────
def ensure_rp_imports_bucket(db: Client) -> None:
    try:
        buckets = db.storage.list_buckets()
        names = [b["name"] if isinstance(b, dict) else b.name for b in buckets]
        if "rp_imports" not in names:
            db.storage.create_bucket("rp_imports", options={"public": False})
            log.info("Created Supabase storage bucket: rp_imports")
        else:
            log.info("Bucket rp_imports already exists")
    except Exception as e:
        log.error("Failed to create rp_imports bucket: %s", e)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main(target_date: str) -> None:
    if not SUPA_URL or not SUPA_KEY:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    db = create_client(SUPA_URL, SUPA_KEY)
    log.info("=== VÉLØ Sigma Loop Closer — %s ===", target_date)

    # Step 0: Create rp_imports bucket if missing
    ensure_rp_imports_bucket(db)

    # Step 1: Single-run guard
    run_id = acquire_run_lock(db, target_date)
    if not run_id:
        sys.exit(1)

    races_done = 0
    runners_done = 0
    reviews_done = 0

    try:
        # Step 2: Load verdicts for target_date from DB
        rows = (
            db.table("velo_verdicts")
            .select("id, race_id, confidence_level, top_rank_horse_id, top_rank_score, selections")
            .execute()
        )
        # Filter to verdicts whose race is on target_date
        race_rows = (
            db.table("races")
            .select("race_id, date")
            .eq("date", target_date)
            .execute()
        )
        dated_race_ids = {r["race_id"] for r in race_rows.data}
        verdicts = [
            {**v, "verdict_id": v["id"]}
            for v in rows.data
            if v["race_id"] in dated_race_ids
        ]
        log.info("Found %d verdicts for %s", len(verdicts), target_date)

        if not verdicts:
            log.warning("No verdicts found for %s — nothing to reconcile", target_date)
            release_run_lock(db, run_id, "completed", 0, 0, 0)
            return

        verdict_by_race = {v["race_id"]: v for v in verdicts}

        # Step 3: Fetch results from Racing API
        api_results = fetch_results(target_date)
        log.info("Racing API returned %d race results", len(api_results))

        if not api_results:
            log.warning(
                "No results returned from Racing API for %s. "
                "Races may not have finished yet, or subscription tier "
                "may not include results. Marking run as partial.",
                target_date,
            )
            release_run_lock(db, run_id, "partial", 0, 0, 0,
                             error="Racing API returned 0 results")
            return

        # Step 4: Match, store, review
        for api_race in api_results:
            race_id = api_race.get("race_id") or api_race.get("id", "")
            if not race_id:
                continue

            # Only store results for races we have in our races table (FK constraint)
            if race_id not in dated_race_ids:
                continue

            # Store race_results + runner_results
            runner_count = store_race_result(db, race_id, api_race)
            races_done += 1
            runners_done += runner_count

            # Generate review if we have a verdict
            if race_id in verdict_by_race:
                verdict = verdict_by_race[race_id]
                runners_list = api_race.get("runners", [])

                # Normalise horse_id field (API may use 'horse_id' or 'id')
                for r in runners_list:
                    if "horse_id" not in r and "id" in r:
                        r["horse_id"] = r["id"]

                review = generate_review(db, verdict, api_race, runners_list)

                # Upsert review
                db.table("velo_post_race_reviews").upsert(
                    review, on_conflict="verdict_id"
                ).execute()

                # Sigma audit
                try:
                    write_sigma_audit(db, race_id, review, verdict)
                except Exception as e:
                    log.warning("sigma_audit write failed for %s: %s", race_id, e)

                outcome = review["review_outcome"].get("outcome", "?")
                log.info(
                    "  verdict %s → %s (pos=%s, winner=%s@%s)",
                    race_id, outcome,
                    review.get("top_pick_position"),
                    review.get("actual_winner_id"),
                    review.get("actual_winner_sp"),
                )
                reviews_done += 1

        # Step 5: Summary
        log.info("")
        log.info("=== RECONCILIATION COMPLETE ===")
        log.info("  races processed  : %d", races_done)
        log.info("  runners processed: %d", runners_done)
        log.info("  reviews generated: %d", reviews_done)

        # Counts by outcome
        if reviews_done > 0:
            review_rows = (
                db.table("velo_post_race_reviews")
                .select("top_pick_won, top_pick_placed, verdict_accuracy_score")
                .execute()
            )
            wins   = sum(1 for r in review_rows.data if r.get("top_pick_won"))
            placed = sum(1 for r in review_rows.data if r.get("top_pick_placed") and not r.get("top_pick_won"))
            misses = sum(1 for r in review_rows.data if not r.get("top_pick_placed"))
            log.info("  wins    : %d", wins)
            log.info("  placed  : %d", placed)
            log.info("  misses  : %d", misses)
            if reviews_done > 0:
                strike = wins / reviews_done * 100
                log.info("  strike rate: %.1f%%", strike)

        release_run_lock(db, run_id, "completed",
                         races=races_done, runners=runners_done, results=reviews_done)

    except Exception as exc:
        log.exception("Fatal error in sigma loop closer")
        release_run_lock(db, run_id, "failed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Date to reconcile (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()
    main(args.date)
