#!/usr/bin/env python3
"""
VÉLØ Shadow Overlay Observation Runner
Tracks performance of scoring overlays against nightly results.

Strictly observational. No production changes.
"""

import json
import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Add root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("observation_runner")

class ShadowObservationRunner:
    def __init__(self, date_str: str, state_path: str):
        self.date_str = date_str
        self.date_tag = date_str.replace("-", "_")
        self.state_path = Path(state_path)
        
        self.pred_file = ROOT / "data" / f"velo_prime_verdicts_{self.date_tag}.json"
        self.res_file = ROOT / "data" / f"results_{self.date_tag}.json"
        self.output_path = ROOT / "data" / f"shadow_overlay_observation_{self.date_tag}.json"
        self.summary_path = ROOT / "data" / "shadow_overlay_observation_summary_v1.json"

    def _load_json(self, path):
        return json.loads(path.read_text()) if path.exists() else {}

    def _calculate_brier(self, probs, outcomes):
        if not probs: return 0.0
        return sum((p - o)**2 for p, o in zip(probs, outcomes)) / len(probs)

    def run(self):
        logger.info(f"Running Shadow Overlay Observation for {self.date_str}")
        
        if not self.pred_file.exists() or not self.res_file.exists():
            logger.warning(f"Skipping observation: Missing data for {self.date_str}")
            return "SKIPPED"

        preds = self._load_json(self.pred_file)
        results_raw = self._load_json(self.res_file)
        results_list = results_raw.get("results", []) if isinstance(results_raw, dict) else results_raw
        results_map = {r.get("race_id") or r.get("id"): r for r in results_list}
        
        baseline_data = {"probs": [], "outcomes": [], "hcl": 0, "wins": 0}
        
        for p_race in preds:
            rid = p_race.get("race_id")
            if rid not in results_map: continue
            
            top_pick = p_race.get("top", {})
            winner_id = None
            runners = results_map[rid].get("runners", [])
            sorted_runners = sorted([r for r in runners if str(r.get("position", "")).isdigit()], 
                                 key=lambda r: int(r["position"]))
            if sorted_runners: winner_id = sorted_runners[0].get("horse_id")
            
            if not winner_id: continue
            
            prob = float(top_pick.get("velo_prime_prob") or 0.0)
            outcome = 1.0 if top_pick.get("horse_id") == winner_id else 0.0
            
            baseline_data["probs"].append(prob)
            baseline_data["outcomes"].append(outcome)
            if outcome == 1.0: baseline_data["wins"] += 1
            if outcome == 0.0 and prob > 0.45: baseline_data["hcl"] += 1

        total = len(baseline_data["probs"])
        if total == 0: return "FAIL"

        baseline_brier = self._calculate_brier(baseline_data["probs"], baseline_data["outcomes"])
        
        # Apply Overlays
        def get_overlay_metrics(cap):
            adj_probs = [min(p, cap) for p in baseline_data["probs"]]
            adj_hcl = 0
            for p, o in zip(adj_probs, baseline_data["outcomes"]):
                if o == 0.0 and p > 0.45: adj_hcl += 1
            return {
                "brier_score": self._calculate_brier(adj_probs, baseline_data["outcomes"]),
                "high_confidence_losses": adj_hcl,
                "strike_rate": baseline_data["wins"] / total
            }

        observation = {
            "date": self.date_str,
            "baseline": {
                "races_evaluated": total,
                "strike_rate": baseline_data["wins"] / total,
                "brier_score": baseline_brier,
                "high_confidence_losses": baseline_data["hcl"]
            },
            "overlays": {
                "calibration_cap_35": get_overlay_metrics(0.35),
                "calibration_cap_30": get_overlay_metrics(0.30),
                "volatility_confidence_cap": get_overlay_metrics(0.40) # Proxy
            },
            "selection_repair_status": "NOT_SOLVED",
            "easy_winner_rescue_status": "BLOCKED_BY_MARKET_AND_RANKING_DATA",
            "production_scoring_changed": False,
            "model_weights_changed": False,
            "live_sentient_state_touched": False,
            "supabase_writes_attempted": False,
            "hfs_features_used": False,
            "verdict": "PASS"
        }
        
        self.output_path.write_text(json.dumps(observation, indent=2))
        return "PASS"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--state", default="data/sentient_state_shadow.json")
    args = parser.parse_args()
    
    runner = ShadowObservationRunner(args.date, args.state)
    runner.run()
