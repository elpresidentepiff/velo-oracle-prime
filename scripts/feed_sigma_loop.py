"""
Feed March 16th results into the Sentient Loopback Engine (Playbook G).
Also writes to Supabase post_race_reviews and updates learned_patterns.

Usage:
    python scripts/feed_sigma_loop.py --date 2026-03-16
"""
import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

def load_sigma_input(date_str: str) -> list:
    path = ROOT / "data" / f"sigma_input_{date_str.replace('-','_')}.json"
    if not path.exists():
        print(f"ERROR: {path} not found — run results fetch first")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)

def build_prediction_dict(row: dict) -> dict:
    """Map sigma_input row to Playbook G prediction format."""
    return {
        "power_anchor": row["picked_name"],
        "confidence_level": row["confidence"],
        "score": row["score"],
        "race_id": row["race_id"],
        "horse_id": row["horse_id"],
    }

def build_result_dict(row: dict) -> dict:
    """Map sigma_input row to Playbook G actual_result format."""
    return {
        "winner": row["winner_name"],
        "winner_sp": row["winner_sp"],
        "picked_position": row["picked_pos"],
        "correct": row["correct"],
    }

def build_race_data_dict(row: dict) -> dict:
    """Minimal race_data dict for Playbook G context."""
    return {
        "race_id": row["race_id"],
        "course": row["course"],
        "off": row["off"],
        "runners": [],  # Full runner data not available post-hoc
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-03-16")
    args = parser.parse_args()

    date_str = args.date
    rows = load_sigma_input(date_str)
    print(f"Loading {len(rows)} race outcomes for {date_str} into sigma loop...\n")

    engine = SentientLoopbackEngine()

    evolution_log = []
    wins = 0
    medium_wins = 0
    medium_total = 0
    low_wins = 0
    low_total = 0

    for row in rows:
        prediction  = build_prediction_dict(row)
        actual      = build_result_dict(row)
        race_data   = build_race_data_dict(row)

        report = engine.observe_race_outcome(race_data, prediction, actual)

        conf = row["confidence"]
        if conf == "MEDIUM":
            medium_total += 1
            if row["correct"]: medium_wins += 1
        elif conf == "LOW":
            low_total += 1
            if row["correct"]: low_wins += 1

        if row["correct"]:
            wins += 1
            status = "WIN"
        else:
            status = "---"

        print(f"[{status}] {row['course']:<20} {row['off']}  {conf:<7} "
              f"pick={row['picked_name'][:24]:<24} pos={row['picked_pos']:<4} "
              f"winner={row['winner_name'][:22]:<22} {row['winner_sp']}")

        evolution_log.append({
            "race_id": row["race_id"],
            "correct": row["correct"],
            "confidence": conf,
            "error_vector": report.get("error_vector", {}),
            "appetite": report.get("appetite_state"),
        })

    # ── Final state snapshot ────────────────────────────────────────────────
    state = engine.get_evolutionary_state()

    print(f"\n{'='*60}")
    print(f"SIGMA LOOP COMPLETE — {date_str}")
    print(f"{'='*60}")
    print(f"Races processed : {len(rows)}")
    print(f"Wins            : {wins}/{len(rows)} = {wins/len(rows):.1%}")
    if medium_total:
        print(f"MEDIUM accuracy : {medium_wins}/{medium_total} = {medium_wins/medium_total:.1%}")
    if low_total:
        print(f"LOW accuracy    : {low_wins}/{low_total} = {low_wins/low_total:.1%}")
    print()
    print(f"Aggression level : {state.get('appetite_state', {}).get('aggression_level', 'N/A')}")
    print(f"Total races seen : {state.get('total_races_observed', 'N/A')}")
    print()

    # Doctrine adjustments
    recent_adj = state.get("doctrine_strengths", {})
    if recent_adj:
        print("Doctrine strength updates:")
        for doctrine, strength in sorted(recent_adj.items(), key=lambda x: -x[1])[:8]:
            bar = '#' * int(strength * 20)
            print(f"  {doctrine:<30} {strength:.3f} |{bar}")

    # ── Sigma anomaly: LOW > MEDIUM is significant ──────────────────────────
    if low_total >= 3 and medium_total >= 3:
        print()
        if low_wins / low_total > medium_wins / medium_total:
            delta = (low_wins/low_total) - (medium_wins/medium_total)
            print(f"[SIGMA ALERT] LOW confidence outperforms MEDIUM by {delta:.1%}")
            print("  -> Confidence calibration may be inverted on low-score races")
            print("  -> Recommend: review confidence threshold in orchestrator.py")
            print("  -> Check: LOW picks may be better-rated horses the market undervalued")

    # Save evolution log
    log_path = ROOT / "data" / f"sigma_log_{date_str.replace('-','_')}.json"
    with open(log_path, "w") as f:
        json.dump({
            "date": date_str,
            "races": len(rows),
            "wins": wins,
            "medium_accuracy": round(medium_wins/medium_total, 4) if medium_total else None,
            "low_accuracy": round(low_wins/low_total, 4) if low_total else None,
            "final_state_snapshot": state,
            "evolution_log": evolution_log,
        }, f, indent=2)
    print(f"\nEvolution log saved: data/sigma_log_{date_str.replace('-','_')}.json")

if __name__ == "__main__":
    main()
