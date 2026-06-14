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
    "improvement_score": {"field": "top_pick_improvement_score", "threshold": 0.30},
    "market_deception_score": {"field": "top_pick_mds", "threshold": 0.30},
    "place_prob": {"field": "top_pick_place_prob", "threshold": 0.50},
    "new_build_agreed": {"field": "top_pick_new_build_agreed", "threshold": True}, # Boolean
}

def evaluate_sidecar(sidecar_key, config, record):
    """
    Evaluates if a sidecar 'fired' for the VELO top pick of the race.
    """
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
        "n_missed": 0, # Tracks incorrect fires
        "elo": STARTING_ELO
    } for k in SIDECARS}

    ledger_records = []
    
    all_records = []
    for f in memory_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                all_records.append(json.loads(line))
                
    all_records.sort(key=lambda x: x.get("generated_at", ""))

    print(f"Processing {len(all_records)} historical closed races for Elo tournament...")

    for rec in all_records:
        race_id = rec.get("race_id")
        date_iso = rec.get("date")
        
        # Did VELO pick the winner?
        is_win = rec.get("miss_type") == "NONE"
        
        for skey, config in SIDECARS.items():
            # Did the sidecar highlight the top pick?
            fired_on_top_pick = evaluate_sidecar(skey, config, rec)
            
            elo_change = 0
            event_type = ""
            
            if fired_on_top_pick:
                stats[skey]["n_fired"] += 1
                if is_win:
                    stats[skey]["n_correct"] += 1
                    elo_change = K_CORRECT
                    event_type = "CORRECT_FIRE"
                else:
                    stats[skey]["n_missed"] += 1
                    elo_change = K_INCORRECT
                    event_type = "INCORRECT_FIRE"
            else:
                if is_win:
                    elo_change = K_MISSED
                    event_type = "MISSED_WINNER"
                else:
                    elo_change = 0
                    event_type = "NO_FIRE"

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
