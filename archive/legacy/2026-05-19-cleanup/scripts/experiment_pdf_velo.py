#!/usr/bin/env python3.11
"""
VÉLØ Offline PDF Experiment
===========================
Feeds PDF-generated JSON racecards directly into the VÉLØ predictive models, 
bypassing the live The Racing API and normalizer.

This demonstrates how the last 6 TS/OR features parsed from PDFs can be 
utilized to build the picture offline.
"""

import os
import sys
import glob
import json
import logging
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import score_race_velo_prime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def _parse_fractional_odds(name, forecast_str):
    """Attempt to find odds for a horse name in the betting forecast string."""
    if not forecast_str:
        return 0.0
    import re
    # forecast_str e.g., "2/7 Runman, 11/2 Vitality, 14/1 Get Outta Here"
    parts = forecast_str.split(',')
    for part in parts:
        if name.lower() in part.lower():
            match = re.search(r'(\d+)/(\d+)', part)
            if match:
                num, den = match.groups()
                return (float(num) / float(den)) + 1.0
            match_evens = re.search(r'Evens', part, re.IGNORECASE)
            if match_evens:
                return 2.0
    return 0.0

def process_pdf_racecard(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    venue = data.get("venue", "UNK")
    date_str = data.get("date", "2026-01-01")
    races = data.get("races", {})
    
    print(f"\n==========================================================")
    print(f" EXPERIMENTING ON {venue} - {date_str} ({len(races)} races)")
    print(f"==========================================================")
    
    for race_time, race_data in races.items():
        race_info = race_data.get("race_info", "")
        forecast = race_data.get("betting_forecast", "")
        
        # Build normalized race dictionary
        norm_race = {
            "race_id": f"pdf_{venue}_{date_str}_{race_time}",
            "course": venue,
            "off_time": f"{date_str}T{race_time.replace('.', ':')}:00Z",
            "distance_f": 8.0, # Defaulting for experiment
            "going": "Good",
            "race_class": "Class 4",
            "runners": []
        }
        
        # Determine average OR and RPR to pass into norm_race (optional, model does it)
        for h in race_data.get("horses", []):
            name = h.get("horse_name")
            odds_dec = _parse_fractional_odds(name, forecast)
            if odds_dec == 0.0:
                odds_dec = 10.0 # fallback
                
            pdf_intel = {
                "plot_conviction": h.get("plot_score", 0.0) or 0.0,
                "or_compression_score": h.get("comp_score", 0.0) or 0.0,
                "ts_master": h.get("ts_master", 0.0) or 0.0,
                "or_delta_to_best_win": h.get("or_delta", 0.0) or 0.0,
            }
            
            runner = {
                "horse_id": f"pdf_hrs_{name.replace(' ', '_')}",
                "horse_name": name,
                "official_rating": h.get("or") or None,
                "rpr": h.get("rpr") or None,
                "ts": h.get("ts_latest") or None,
                "or_missing": h.get("or") is None,
                "rpr_missing": h.get("rpr") is None,
                "ts_missing": h.get("ts_latest") is None,
                "best_odds_decimal": odds_dec,
                "weight_lbs": 126.0, # placeholder
                "draw": 1, # placeholder
                "age": "4", # placeholder
                "pdf_intel": pdf_intel
            }
            norm_race["runners"].append(runner)
            
        if not norm_race["runners"]:
            continue
            
        # Run VELO Prime 
        try:
            predictions = score_race_velo_prime(norm_race, sentient_state=None)
            print(f"\n[Race {race_time}] {race_info}")
            print(f"{'Horse':<20} | {'Prob %':>8} | {'Odds':>6} | {'Plot':>6} | {'TS':>4} | {'Verdict'}")
            print("-" * 70)
            
            for p in predictions[:5]:  # Top 5
                prob = p.get("velo_prime_prob", 0.0) * 100
                odds = p.get("sp_dec", 0.0)
                intel = p.get("pdf_intel", {})
                plot = intel.get("plot_conviction", 0.0)
                ts_m = intel.get("ts_master", 0.0)
                verdict = p.get("verdict_flags", [])
                v_str = ",".join(verdict) if verdict else "-"
                
                name = p.get("horse_name") or p.get("name", str(p.get("horse_id", "UNK")))
                print(f"{name:<20} | {prob:>7.1f}% | {odds:>6.2f} | {plot:>6.2f} | {ts_m:>4.0f} | {v_str}")
        except Exception as e:
            print(f"Error scoring race {race_time}: {e}")

def run_all_experiments():
    # Load all merged racecards
    files = glob.glob(str(ROOT / "data" / "racecard_merged" / "racecard_*.json"))
    
    # We only process the ones from 2026-04-28 as requested for this experiment
    target_files = [f for f in files if "2026-04-28" in f]
    
    if not target_files:
        print("No racecards found for 2026-04-28.")
        return
        
    for f in target_files:
        process_pdf_racecard(f)

if __name__ == "__main__":
    run_all_experiments()