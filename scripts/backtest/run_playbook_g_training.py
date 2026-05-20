#!/usr/bin/env python3
"""
run_playbook_g_training.py

Feed 20,677 active HFS rows through the Sentient Loopback Engine (Playbook G).
Groups rows by race_id, constructs race_data/prediction/actual_result from HFS fields,
calls observe_race_outcome() for each race with a closed result.

Usage:
    python scripts/run_playbook_g_training.py [--dry-run] [--limit N]

Outputs:
    data/sentient_state.json                 — trained state (local)
    learned_patterns (Supabase)              — SENTIENT_STATE_BACKUP row
    data/playbook_g_training_report.md       — summary report
"""

import os
import sys
import time
import json
import argparse
import requests
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "historical_feature_store"
EXCLUDED_FLAG = "EXCLUDED_DATA_DARK"
REPORT_PATH = Path("data/playbook_g_training_report.md")


def hdrs():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_active_hfs() -> list[dict]:
    rows = []
    offset = 0
    select = (
        "race_id,horse_id,race_date,mpi,chaos_bloom,"
        "winner_flag,placed_flag,finish_position,sp_dec,field_size,"
        "reconstruction_version"
    )
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/{TABLE}"
            f"?reconstruction_version=neq.{EXCLUDED_FLAG}"
            f"&mpi=not.is.null"
            f"&winner_flag=not.is.null"
            f"&select={select}&offset={offset}&limit=1000"
        )
        r = requests.get(url, headers=hdrs(), timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
        time.sleep(0.05)
    return rows


def build_race_groups(rows: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for r in rows:
        if r.get("race_id"):
            groups[r["race_id"]].append(r)
    return groups


def build_training_inputs(runners: list[dict]) -> tuple[dict, dict, dict] | None:
    """
    Build (race_data, prediction, actual_result) from a group of HFS runners.
    Returns None if the race has no winner flag.
    """
    winners = [r for r in runners if r.get("winner_flag") is True]
    if not winners:
        return None

    winner = winners[0]

    # Sort by sp_dec to find favourite (lowest SP)
    sp_runners = [r for r in runners if r.get("sp_dec") is not None]
    favourite = min(sp_runners, key=lambda r: float(r["sp_dec"])) if sp_runners else None

    # Power anchor = runner with highest mpi (our predicted winner)
    mpi_runners = [r for r in runners if r.get("mpi") is not None]
    power_anchor = max(mpi_runners, key=lambda r: float(r["mpi"])) if mpi_runners else runners[0]

    race_mpi = float(power_anchor["mpi"]) if power_anchor.get("mpi") else 0.0
    race_chaos = max((float(r["chaos_bloom"]) for r in runners if r.get("chaos_bloom") is not None), default=0.3)

    favourite_won = (
        favourite is not None
        and winner["horse_id"] == favourite["horse_id"]
    )

    # narrative_disruption: high mpi + fav didn't win → disruption
    narrative_disruption = race_mpi if not favourite_won else race_mpi * 0.3

    race_data = {
        "race_id": runners[0]["race_id"],
        "race_date": runners[0].get("race_date"),
        "mpi": race_mpi,
        "chaos_bloom": race_chaos,
        "story_anchor": str(favourite["horse_id"]) if favourite else "",
        "power_anchor": str(power_anchor["horse_id"]),
        "threat_cluster": [str(r["horse_id"]) for r in runners if r["horse_id"] != (favourite["horse_id"] if favourite else None)],
        "narrative_disruption": narrative_disruption,
        "fav_trip_blocked": not favourite_won and race_chaos > 0.55,
        "runners": [
            {"name": str(r["horse_id"]), "horse": str(r["horse_id"]), "run_style": ""}
            for r in runners
        ],
        "integrity_score": 100 - int(race_mpi * 50),
    }

    prediction = {
        "power_anchor": str(power_anchor["horse_id"]),
        "confidence": race_mpi,
        "doctrines_fired": _infer_doctrines(race_mpi, race_chaos, narrative_disruption),
    }

    actual_result = {
        "winner": str(winner["horse_id"]),
        "sp": float(winner["sp_dec"]) if winner.get("sp_dec") else 5.0,
        "favourite_won": favourite_won,
        "winner_profile": {
            "running_style": "",
            "draw": None,
            "was_hidden_improver": False,
            "late_money": False,
        },
    }

    return race_data, prediction, actual_result


def _infer_doctrines(mpi: float, chaos: float, narrative: float) -> list[str]:
    fired = []
    if mpi > 0.55:
        fired.append("SHADOW_TRACKING")
    if chaos > 0.50:
        fired.append("CHAOS_BLEED")
    if narrative > 0.60:
        fired.append("LAY_THE_STORY")
    if mpi > 0.40:
        fired.append("ENGINE_SUPREMACY")
    return fired


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Build inputs but don't call observe_race_outcome()")
    parser.add_argument("--limit", type=int, default=0, help="Max races to train on (0=all)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    print("=" * 68)
    print("PLAYBOOK G — SENTIENT LOOPBACK TRAINING")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE TRAINING'}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 68)

    # ── Load Sentient Engine ──────────────────────────────────────────────
    from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
    engine = SentientLoopbackEngine()
    initial_races = engine.state.get("total_races_observed", 0)
    print(f"\nEngine loaded. Prior observations: {initial_races:,}")

    # ── Fetch HFS data ────────────────────────────────────────────────────
    print("\n[1/4] Fetching active HFS rows (mpi non-null, winner_flag non-null)...")
    rows = fetch_active_hfs()
    print(f"  Fetched: {len(rows):,} rows")

    # ── Group by race ─────────────────────────────────────────────────────
    print("[2/4] Grouping by race_id...")
    groups = build_race_groups(rows)
    print(f"  Races found: {len(groups):,}")

    # ── Build training inputs ─────────────────────────────────────────────
    print("[3/4] Building training inputs...")
    trainable = []
    skipped_no_winner = 0
    for race_id, runners in groups.items():
        result = build_training_inputs(runners)
        if result is None:
            skipped_no_winner += 1
            continue
        trainable.append(result)

    print(f"  Trainable races: {len(trainable):,}")
    print(f"  Skipped (no winner): {skipped_no_winner:,}")

    if args.limit and args.limit > 0:
        trainable = trainable[:args.limit]
        print(f"  Limited to: {len(trainable):,} (--limit {args.limit})")

    if args.dry_run:
        print("\n[4/4] DRY RUN — sample inputs (first 3):")
        for race_data, prediction, actual_result in trainable[:3]:
            print(f"\n  race_id={race_data['race_id']} date={race_data['race_date']}")
            print(f"    mpi={race_data['mpi']:.4f}  chaos={race_data['chaos_bloom']:.4f}")
            print(f"    power_anchor={prediction['power_anchor']}  confidence={prediction['confidence']:.4f}")
            print(f"    actual_winner={actual_result['winner']}  sp={actual_result['sp']}  fav_won={actual_result['favourite_won']}")
            print(f"    doctrines_fired={prediction['doctrines_fired']}")
        print("\nRun without --dry-run to execute training.")
        return

    # ── Run training ──────────────────────────────────────────────────────
    print("[4/4] Running observe_race_outcome() loop...")
    n_correct = 0
    n_total = 0
    n_fav_won = 0
    doctrine_fires = defaultdict(int)
    t_start = time.time()

    for i, (race_data, prediction, actual_result) in enumerate(trainable, 1):
        result = engine.observe_race_outcome(race_data, prediction, actual_result)
        if result["error_vector"]["prediction_correct"] == 1.0:
            n_correct += 1
        if actual_result["favourite_won"]:
            n_fav_won += 1
        for d in prediction.get("doctrines_fired", []):
            doctrine_fires[d] += 1
        n_total += 1

        if i % 500 == 0:
            elapsed = time.time() - t_start
            sr = n_correct / n_total
            print(f"  [{i:,}/{len(trainable):,}]  SR={sr:.3f}  elapsed={elapsed:.1f}s")

    elapsed = time.time() - t_start

    # ── Final state ───────────────────────────────────────────────────────
    evo = engine.get_evolutionary_state()
    final_races = engine.state.get("total_races_observed", 0)
    train_sr = n_correct / max(n_total, 1)
    fav_sr = n_fav_won / max(n_total, 1)

    print(f"\n{'=' * 68}")
    print("TRAINING COMPLETE")
    print(f"  Races trained:         {n_total:,}")
    print(f"  Power anchor SR:       {train_sr:.3f}  ({n_correct:,}/{n_total:,})")
    print(f"  Favourite win rate:    {fav_sr:.3f}  ({n_fav_won:,}/{n_total:,})")
    print(f"  Training time:         {elapsed:.1f}s")
    print(f"  Total races observed:  {final_races:,} (was {initial_races:,})")
    print(f"\nAppetite state:")
    for k, v in evo["appetite_state"].items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
    print(f"\nDoctrine strengths:")
    for k, v in sorted(evo["doctrine_strengths"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v:.4f}")
    print(f"\nMarket lies detected:  {engine.state['house_behaviour_map']['market_lies_detected']:,}")
    print(f"Safe bets imploded:    {engine.state['house_behaviour_map']['safe_bets_imploded']:,}")
    print(f"Favourites protected:  {engine.state['house_behaviour_map']['favourites_protected']:,}")
    print(f"Favourites abandoned:  {engine.state['house_behaviour_map']['favourites_abandoned']:,}")
    print(f"Emotion laws (pain):   {len(engine.state['emotion_laws']['pain_rules']):,}")
    print(f"Emotion laws (triumph):{len(engine.state['emotion_laws']['triumph_rules']):,}")
    print(f"Emotion laws (anger):  {len(engine.state['emotion_laws']['anger_rules']):,}")
    print(f"{'=' * 68}")

    # ── Write report ──────────────────────────────────────────────────────
    REPORT_PATH.parent.mkdir(exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(f"# Playbook G Training Report\n\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()}Z\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| Races trained | {n_total:,} |\n")
        f.write(f"| Power anchor SR | {train_sr:.3f} |\n")
        f.write(f"| Favourite win rate | {fav_sr:.3f} |\n")
        f.write(f"| Training time | {elapsed:.1f}s |\n")
        f.write(f"| Total races observed | {final_races:,} |\n\n")
        f.write(f"## Appetite State\n\n")
        for k, v in evo["appetite_state"].items():
            if isinstance(v, float):
                f.write(f"- {k}: {v:.4f}\n")
        f.write(f"\n## Doctrine Strengths\n\n")
        for k, v in sorted(evo["doctrine_strengths"].items(), key=lambda x: -x[1]):
            f.write(f"- {k}: {v:.4f}\n")
        f.write(f"\n## Behaviour Echo Chamber\n\n")
        for k, v in engine.state["house_behaviour_map"].items():
            if isinstance(v, int):
                f.write(f"- {k}: {v:,}\n")
        f.write(f"\n## Emotion Laws\n\n")
        for emotion, rules in engine.state["emotion_laws"].items():
            f.write(f"- {emotion}: {len(rules):,} rules\n")

    print(f"\nReport written: {REPORT_PATH}")
    print(f"State saved: data/sentient_state.json")
    print(f"Cloud backup: learned_patterns / SENTIENT_STATE_BACKUP")


if __name__ == "__main__":
    main()
