#!/usr/bin/env python3
"""
Sidecar Elo Tournament
Computes live Elo ratings for sidecar signals based on closed outcomes from Sigma Memory.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
MEMORY_DIR = DATA_DIR / "sigma_memory"
ELO_DIR = DATA_DIR / "sidecar_elo"
ELO_DIR.mkdir(parents=True, exist_ok=True)

LEDGER_PATH = ELO_DIR / "sidecar_elo_ledger.jsonl"
LATEST_JSON = ELO_DIR / "sidecar_elo_latest.json"
LATEST_MD = ELO_DIR / "sidecar_elo_latest.md"

# Elo Constants
STARTING_ELO = 1000
K_CORRECT = 32
K_INCORRECT = -32
K_MISSED = -8

SIDECARS = {
    "improvement_score": {"field": "improvement_score_winner", "threshold": 0.30},
    "market_deception_score": {"field": "mds_winner", "threshold": 0.30},
    "place_prob": {"field": "place_prob_winner", "threshold": 0.50},
    "new_build_agreed": {"field": "new_build_agreed", "threshold": True}, # Boolean
}

def evaluate_sidecar(sidecar_key, config, record):
    """
    Evaluates if a sidecar 'fired' for the WINNER of the race.
    Note: The sigma memory currently records these fields for the WINNER, 
    or the VELO top pick if the winner wasn't scored.
    We only penalize/reward based on the winner's stats in the memory record.
    """
    # Sigma memory captures: improvement_score_winner, mds_winner, place_prob_winner, new_build_agreed
    val = record.get(config["field"])
    
    if val is None:
        return False
        
    if isinstance(config["threshold"], bool):
        return bool(val) == config["threshold"]
    else:
        try:
            return float(val) > config["threshold"]
        except (ValueError, TypeError):
            return False

def run_elo_tournament():
    if not MEMORY_DIR.exists():
        print("Sigma memory directory not found.")
        return

    # Load all memory files
    memory_files = sorted(MEMORY_DIR.glob("sigma_memory_*.jsonl"))
    if not memory_files:
        print("No sigma memory files found.")
        return

    # Initialize stats
    stats = {k: {
        "n_fired": 0, 
        "n_correct": 0, 
        "n_missed": 0, 
        "elo": STARTING_ELO
    } for k in SIDECARS}

    # Load existing ledger to avoid double counting if we want this to be re-runnable from scratch
    # For simplicity and correctness, we will rebuild the stats from the ledger or from memory.
    # The prompt implies running over all files in data/sigma_memory/ and outputting a ledger.
    # To be idempotent, we will read all memory files, recalculate from scratch, and overwrite the ledger.
    
    ledger_records = []
    
    # Read all memory records in chronological order
    all_records = []
    for f in memory_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                all_records.append(json.loads(line))
                
    # Sort by generated_at to simulate chronological tournament
    all_records.sort(key=lambda x: x.get("generated_at", ""))

    print(f"Processing {len(all_records)} historical closed races for Elo tournament...")

    for rec in all_records:
        race_id = rec.get("race_id")
        date_iso = rec.get("date")
        
        # Did VELO pick the winner?
        is_win = rec.get("miss_type") == "NONE"
        
        for skey, config in SIDECARS.items():
            # Did the sidecar highlight the winner?
            fired_on_winner = evaluate_sidecar(skey, config, rec)
            
            elo_change = 0
            event_type = ""
            
            if fired_on_winner:
                # The sidecar flagged the horse that actually won
                stats[skey]["n_fired"] += 1
                stats[skey]["n_correct"] += 1
                elo_change = K_CORRECT
                event_type = "CORRECT_FIRE"
            else:
                # The sidecar did NOT flag the winner.
                # Did it fire on the loser we picked?
                # Memory record doesn't currently explicitly isolate the sidecar value of the LOSING top pick 
                # separately from the winner unless they are the same.
                # But we can assume: if it didn't fire on the winner, it missed the winner.
                stats[skey]["n_missed"] += 1
                elo_change = K_MISSED
                event_type = "MISSED_WINNER"
                
                # If we wanted to penalize INCORRECT fires (firing on a loser), we would need the sidecar values
                # for all runners in the race, or at least the top pick.
                # For now, we apply K_MISSED for not finding the winner.
                # If the user wants K_INCORRECT specifically for firing on the WRONG horse, we approximate:
                # If VELO lost (is_win==False), and the sidecar fired on VELO's top pick (not recorded in memory directly yet,
                # but we can infer if we assume the sidecar follows VELO's top pick, which it doesn't always).
                # For this iteration, we adhere to: +32 correct fire (on winner), -8 no-fire on winner.
                # We will log it as MISSED_WINNER (-8).
                
                # To perfectly capture K_INCORRECT (-32), we'd need to know if the sidecar fired on ANY loser.
                # Since sigma_memory currently only stores w_impr, w_mds (winner's stats), we only know if it fired on the winner.
                # We will apply K_MISSED (-8) for failing to flag the winner.

            stats[skey]["elo"] += elo_change
            
            ledger_records.append({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "race_id": race_id,
                "date": date_iso,
                "sidecar": skey,
                "event": event_type,
                "elo_change": elo_change,
                "new_elo": stats[skey]["elo"]
            })

    # Write Ledger (overwrite to maintain idempotent rebuild)
    with LEDGER_PATH.open("w", encoding="utf-8") as f:
        for lr in ledger_records:
            f.write(json.dumps(lr) + "\n")
            
    # Compile Summary
    summary_list = []
    for skey, s in stats.items():
        total_fires = s["n_fired"]
        sr = s["n_correct"] / total_fires if total_fires > 0 else 0.0
        summary_list.append({
            "sidecar": skey,
            "elo": s["elo"],
            "n_fired": total_fires,
            "n_correct": s["n_correct"],
            "n_missed": s["n_missed"],
            "strike_rate": round(sr, 4)
        })
        
    # Sort by Elo descending
    summary_list.sort(key=lambda x: x["elo"], reverse=True)
    
    # Save JSON
    out_json = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_races_evaluated": len(all_records),
        "rankings": summary_list
    }
    LATEST_JSON.write_text(json.dumps(out_json, indent=2))
    
    # Save Markdown
    md_lines = [
        "# Sidecar Elo Tournament",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Races Evaluated: {len(all_records)}",
        "",
        "| Rank | Sidecar | Elo Rating | Fires | Correct | Missed | Strike Rate |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for i, s in enumerate(summary_list, 1):
        md_lines.append(
            f"| {i} | **{s['sidecar']}** | {s['elo']} | {s['n_fired']} | {s['n_correct']} | {s['n_missed']} | {s['strike_rate']:.1%} |"
        )
        
    LATEST_MD.write_text("\n".join(md_lines))
    
    print(f"\nTournament complete. Leaderboard:")
    for i, s in enumerate(summary_list, 1):
        print(f"  {i}. {s['sidecar']:<25} Elo: {s['elo']:>5}  (SR: {s['strike_rate']:.1%})")
    print(f"\nSaved to {ELO_DIR}")

if __name__ == "__main__":
    run_elo_tournament()
