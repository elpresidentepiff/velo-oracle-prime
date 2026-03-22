"""
backfill_miss_evidence.py
Populates miss_category, miss_evidence, learning_ready in velo_post_race_reviews
for known B-tier misses from a given date's sigma report.

Usage:
    python scripts/backfill_miss_evidence.py --date 2026-03-22

Requires: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import argparse
import json
import os
from datetime import date

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ── Miss definitions for 2026-03-22 sigma report ──────────────────────────────
# Derived from fusion audit view + runner_results.
# miss_category options:
#   market_decoy_followed | outsider_hedge_omitted | fusion_suppression
#   genuine_blind_spot | data_gap | other

MISS_RECORDS = [
    {
        "race_id": "rac_11906518",
        "miss_category": "market_decoy_followed",
        "miss_evidence": {
            "winner": "Beset",
            "winner_sp": 3.75,
            "winner_ensemble_rank": 2,
            "top_pick": "Shaool",
            "top_pick_velo_prime_prob": 0.3068,
            "top_pick_place_prob": 0.8741,
            "top_pick_market_deception_score": 0.1365,
            "winner_market_deception_score": 0.0056,
            "fusion_flag": "deception_on_pick_not_winner",
            "root_cause": "market_deception_score fired on top pick (0.1365) but has zero ensemble weight — winner was ranked 2nd, clean deception score",
            "fix_direction": "give market_deception_score bounded negative weight in velo_prime_prob fusion",
        },
        "learning_ready": True,
    },
    {
        "race_id": "rac_11906596",
        "miss_category": "market_decoy_followed",
        "miss_evidence": {
            "winner": "Krabat",
            "winner_sp": 7.0,
            "winner_ensemble_rank": 3,
            "top_pick": "Mount Frisco",
            "top_pick_velo_prime_prob": 0.2584,
            "top_pick_place_prob": 0.6327,
            "top_pick_market_deception_score": 0.0382,
            "winner_market_deception_score": 0.0115,
            "winner_sqpe_v17_prob": 0.1027,
            "fusion_flag": "deception_on_pick_not_winner",
            "root_cause": "deception signal on top pick (0.0382 vs 0.0115 winner) — Krabat had 2nd-best sqpe but place_prob gap pushed it to 3rd",
            "fix_direction": "market_deception_score weight + place_prob dominance cap in ensemble",
        },
        "learning_ready": True,
    },
    {
        "race_id": "rac_11875305",
        "miss_category": "genuine_blind_spot",
        "miss_evidence": {
            "winner": "National Question",
            "winner_sp": 8.5,
            "winner_ensemble_rank": 6,
            "top_pick": "Ruler Legend",
            "top_pick_velo_prime_prob": 0.1948,
            "top_pick_place_prob": 0.5515,
            "winner_place_prob": 0.0465,
            "winner_longshot_prob": 0.0014,
            "winner_sqpe_v17_prob": 0.0334,
            "fusion_flag": "deception_on_pick_not_winner",
            "root_cause": "winner had no meaningful specialist signal — place, longshot, sqpe all low. Deception flag technically fires but winner was genuinely undetectable from available features",
            "fix_direction": "not a fusion fix — feature coverage gap. Investigate what drove National Question's win (jockey booking? track bias? weight drop?)",
        },
        "learning_ready": False,  # data gap — root cause not yet confirmed
    },
    # data_gap misses — winner was NOT in the scored racecard (confirmed 2026-03-22)
    # runner counts in full_analysis match races.runners_count, but winner horse_id
    # absent from full_analysis. Classification revised from outsider_hedge_omitted.
    # T1.3 check required: is winner's horse_id in Racing API racecard? In runners table?
    {
        "race_id": "rac_11875344",
        "miss_category": "data_gap",
        "miss_evidence": {
            "winner_sp": 15.0,
            "top_pick_position": 5,
            "runners_in_full_analysis": 8,
            "runners_in_races_table": 8,
            "winner_in_full_analysis": False,
            "root_cause": "winner horse absent from scored racecard — counts match so not a count mismatch. Possible late addition, reserve runner, or API racecard gap. Not a model or fusion failure.",
            "t1_3_checks": [
                "confirm winner horse_id in Racing API racecard for this race",
                "confirm winner horse_id in Supabase runners table",
                "confirm why Service B did not score this horse",
            ],
        },
        "learning_ready": False,
    },
    {
        "race_id": "rac_11906492",
        "miss_category": "data_gap",
        "miss_evidence": {
            "winner_sp": 26.0,
            "top_pick_position": 6,
            "runners_in_full_analysis": 12,
            "runners_in_races_table": 12,
            "winner_in_full_analysis": False,
            "root_cause": "winner horse absent from scored racecard — same pattern as rac_11875344. Not a model or fusion failure.",
            "t1_3_checks": [
                "confirm winner horse_id in Racing API racecard for this race",
                "confirm winner horse_id in Supabase runners table",
                "confirm why Service B did not score this horse",
            ],
        },
        "learning_ready": False,
    },
    {
        "race_id": "rac_11875279",
        "miss_category": "data_gap",
        "miss_evidence": {
            "winner_sp": 11.0,
            "top_pick_position": 4,
            "runners_in_full_analysis": 10,
            "runners_in_races_table": 10,
            "winner_in_full_analysis": False,
            "dead_heat": True,
            "dead_heat_detail": "Two horses at position=1 in runner_results: hrs_23537759 (Two Brothers @11.0) and hrs_40494076 (Ryebridge @3.0). Both is_winner=TRUE. Sigma reported winner@11.0SP (higher-priced half). Sigma reconciliation logic does not handle dead heats — picks first is_winner row.",
            "root_cause": "horse set divergence between runners table and full_analysis — counts match (10=10) but winner horses absent from scored racecard. Structural ingestion sequencing bug: Service B scored an earlier racecard fetch; runners table populated later with updated field. Late declaration or reserve entry not present at scoring time.",
            "t1_3_checks": [
                "confirm winner horse_id in Racing API racecard for this race",
                "confirm when runners table row was written vs Service B scoring time",
                "fix sigma reconciliation to handle dead heats",
                "fix Service B to re-fetch racecard closer to off time or after declarations close",
            ],
        },
        "learning_ready": False,
    },
    {
        "race_id": "rac_11906622",
        "miss_category": "data_gap",
        "miss_evidence": {
            "winner_sp": 4.5,
            "note": "non_runner_or_untracked — winner at 4.5SP not in velo_verdicts. Possible NR after scoring or result join failure. T1.3 check required.",
        },
        "learning_ready": False,
    },
]


def backfill(target_date: str, dry_run: bool = False):
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print(f"Backfilling {len(MISS_RECORDS)} miss records for {target_date}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    for rec in MISS_RECORDS:
        race_id = rec["race_id"]

        # Find the matching velo_post_race_reviews row
        result = (
            client.table("velo_post_race_reviews")
            .select("id, race_id, miss_category")
            .eq("race_id", race_id)
            .execute()
        )

        if not result.data:
            print(f"  SKIP {race_id} — no review row exists yet")
            continue

        row = result.data[0]

        if row.get("miss_category"):
            print(f"  SKIP {race_id} — already categorised: {row['miss_category']}")
            continue

        if dry_run:
            print(f"  DRY  {race_id} → {rec['miss_category']} (learning_ready={rec['learning_ready']})")
            continue

        update = (
            client.table("velo_post_race_reviews")
            .update({
                "miss_category": rec["miss_category"],
                "miss_evidence": rec["miss_evidence"],
                "learning_ready": rec["learning_ready"],
            })
            .eq("race_id", race_id)
            .execute()
        )

        print(f"  OK   {race_id} → {rec['miss_category']} (learning_ready={rec['learning_ready']})")

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=str(date.today()))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    backfill(args.date, args.dry_run)
