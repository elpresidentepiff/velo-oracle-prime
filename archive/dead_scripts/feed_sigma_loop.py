"""
VÉLØ — Sigma → Playbook G Doctrine Feed (Supabase-native, v2)
=============================================================
Standalone trigger for the auto-pipeline between sigma reconciliation outputs
and Playbook G doctrine ingestion. Replaces the old sigma_input JSON file reader.

VOX calls this after a sigma debrief has been written to Supabase.
Can also be run manually: python scripts/feed_sigma_loop.py --date YYYY-MM-DD

Reads velo_post_race_reviews + velo_verdicts from Supabase for the given date,
reconstructs run_reviews, and feeds them into SentientLoopbackEngine.

Idempotent — re-running for the same date is a safe no-op (dedup via
learned_patterns.pattern_name = 'playbook_g_fed_{date}').
"""

import json
import sys
import os
import logging
import argparse
from pathlib import Path
from datetime import datetime, date, timezone

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("velo.feed_sigma_loop")

SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY", "")
)


def load_reviews_from_db(db, target_date: str):
    """
    Reconstruct run_reviews + verdicts_by_race from Supabase for a given date.
    Returns (run_reviews, verdicts_by_race). Both empty if nothing found.
    """
    # Load races for date
    race_rows = (
        db.table("races")
        .select("race_id, date, course")
        .eq("date", target_date)
        .execute()
    )
    race_context = {
        r["race_id"]: {"date": r.get("date", ""), "course": r.get("course", "")}
        for r in race_rows.data
    }
    dated_race_ids = set(race_context.keys())
    if not dated_race_ids:
        log.warning("No races found in DB for %s", target_date)
        return [], {}

    # Load verdicts
    verdict_rows = (
        db.table("velo_verdicts")
        .select(
            "id, race_id, confidence_level, top_rank_horse_id, top_rank_score, "
            "decision_tier, full_analysis, velo_prime_prob"
        )
        .in_("race_id", list(dated_race_ids))
        .execute()
    )
    verdicts_by_race = {}
    for v in verdict_rows.data:
        verdicts_by_race[v["race_id"]] = {
            **v,
            "verdict_id":  v["id"],
            "race_date":   race_context.get(v["race_id"], {}).get("date", ""),
            "race_course": race_context.get(v["race_id"], {}).get("course", ""),
        }

    # Load post-race reviews
    review_rows = (
        db.table("velo_post_race_reviews")
        .select(
            "verdict_id, race_id, top_pick_won, top_pick_placed, top_pick_position, "
            "actual_winner_id, actual_winner_sp, verdict_accuracy_score, review_outcome"
        )
        .in_("race_id", list(dated_race_ids))
        .execute()
    )

    run_reviews = []
    for r in review_rows.data:
        race_id = r["race_id"]
        verdict = verdicts_by_race.get(race_id, {})
        ro = r.get("review_outcome") or {}
        if isinstance(ro, str):
            try:
                ro = json.loads(ro)
            except Exception:
                ro = {}

        if r.get("top_pick_won"):
            outcome = "WIN"
        elif r.get("top_pick_placed"):
            outcome = "PLACED"
        else:
            outcome = "MISS"

        run_reviews.append({
            "race_id":           race_id,
            "outcome":           outcome,
            "decision_tier":     verdict.get("decision_tier") or "?",
            "miss_reason":       ro.get("miss_reason"),
            "signal_attribution": ro.get("signal_attribution", {}),
            "top_pick_position": r.get("top_pick_position"),
            "actual_winner_sp":  r.get("actual_winner_sp"),
            "winner_id":         r.get("actual_winner_id", ""),
            "score":             float(verdict.get("top_rank_score") or 0),
            "confidence":        verdict.get("confidence_level"),
        })

    log.info(
        "Loaded %d reviews + %d verdicts for %s",
        len(run_reviews), len(verdicts_by_race), target_date,
    )
    return run_reviews, verdicts_by_race


def feed(target_date: str) -> dict:
    """
    Entry point callable by VOX or run directly.
    Returns a summary dict.
    """
    if not SUPA_URL or not SUPA_KEY:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    from supabase import create_client
    db = create_client(SUPA_URL, SUPA_KEY)
    log.info("=== Sigma → Playbook G Feed — %s ===", target_date)

    run_reviews, verdicts_by_race = load_reviews_from_db(db, target_date)
    if not run_reviews:
        return {
            "status":  "no_reviews",
            "date":    target_date,
            "fed":     0,
            "message": f"No post-race reviews found in DB for {target_date}.",
        }

    # Delegate to close_sigma_loops._feed_playbook_g (shared implementation)
    from scripts.close_sigma_loops import _feed_playbook_g
    fed_n = _feed_playbook_g(db, run_reviews, verdicts_by_race, target_date)

    wins = sum(1 for r in run_reviews if r["outcome"] == "WIN")
    summary = {
        "status":  "fed" if fed_n > 0 else "already_fed",
        "date":    target_date,
        "fed":     fed_n,
        "reviews": len(run_reviews),
        "wins":    wins,
        "message": (
            f"Playbook G ingested {fed_n} races from sigma run {target_date}. "
            f"Doctrine state updated."
        ) if fed_n > 0 else (
            f"Playbook G already fed for {target_date} (dedup). No new mutations written."
        ),
    }
    log.info("Feed summary: %s", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Feed sigma reconciliation outputs into Playbook G doctrine state."
    )
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Target date (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()
    result = feed(args.date)
    print(json.dumps(result, indent=2))
