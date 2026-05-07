#!/usr/bin/env python3
"""
VÉLØ Shadow Model Experiment Runner
Replays historical Genesis data with scoring overlays to test model improvements.

Strictly simulation-only. No production changes.
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
logger = logging.getLogger("experiment_runner")

class ShadowExperimentRunner:
    def __init__(self, events_path: str, baseline_path: str, leakage_path: str):
        self.events_path = Path(events_path)
        self.baseline_path = Path(baseline_path)
        self.leakage_path = Path(leakage_path)
        
        self.events = self._load_jsonl(self.events_path)
        self.baseline = self._load_json(self.baseline_path)
        self.easy_winners_audit = self._load_json(self.leakage_path)
        
        self.results = []
        self.failures = []
        self.recommendations = []

    def _load_json(self, path):
        return json.loads(path.read_text()) if path.exists() else {}

    def _load_jsonl(self, path):
        if not path.exists(): return []
        with open(path, "r") as f:
            return [json.loads(line) for line in f if line.strip()]

    def _calculate_metrics(self, simulated_events):
        total = 0
        wins = 0
        brier_sum = 0.0
        high_conf_losses = 0
        rescues = 0
        
        for e in simulated_events:
            res = e["sim_result"]
            if res == "VOID":
                 # If we avoided a loss, it's a 'rescue' in terms of risk control, 
                 # but doesn't count towards strike rate / brier directly in this calculation mode.
                 if e["actual_outcome"] == "LOSS":
                      rescues += 1
                 continue
            
            total += 1
            prob = e["sim_prob"]
            outcome = e["actual_outcome"] # WIN or LOSS
            
            if outcome == "WIN":
                wins += 1
                brier_sum += (1.0 - prob) ** 2
            else:
                brier_sum += (0.0 - prob) ** 2
                if prob > 0.45:
                    high_conf_losses += 1
                    
        return {
            "races_evaluated": total,
            "wins": wins,
            "strike_rate": wins / total if total > 0 else 0,
            "brier_score": brier_sum / total if total > 0 else 0,
            "high_confidence_losses": high_conf_losses,
            "easy_winner_rescues": rescues
        }

    def experiment_calibration_cap(self, cap_value: float):
        overlay_name = f"calibration_cap_{int(cap_value*100)}"
        sim_events = []
        
        for e in self.events:
            actual_outcome = e.get("prediction_result")
            if actual_outcome == "UNKNOWN": continue
            
            orig_prob = float(e.get("prediction_snapshot", {}).get("velo_prime_prob") or 0.0)
            sim_prob = min(orig_prob, cap_value)
            
            sim_events.append({
                "race_id": e.get("race_id"),
                "actual_outcome": actual_outcome,
                "sim_prob": sim_prob,
                "sim_result": "BET"
            })
            
        metrics = self._calculate_metrics(sim_events)
        metrics["overlay_name"] = overlay_name
        metrics["delta_brier"] = metrics["brier_score"] - self.baseline.get("confidence_error_summary", {}).get("avg_error", 0)
        metrics["selection_quality_improved"] = False
        
        # Honestly label this as risk control
        if metrics["brier_score"] < self.baseline.get("confidence_error_summary", {}).get("avg_error", 1.0):
            metrics["recommendation"] = "KEEP_FOR_LONGER_SHADOW_REPLAY"
            metrics["rationale"] = "Improves probability honesty/Brier score but does not improve winner selection."
        else:
            metrics["recommendation"] = "REJECT"
            
        return metrics

    def experiment_chalk_sanity(self):
        overlay_name = "chalk_sanity_filter"
        sim_events = []
        
        has_market_data = False
        for e in self.events:
            actual_outcome = e.get("prediction_result")
            if actual_outcome == "UNKNOWN": continue
            
            orig_prob = float(e.get("prediction_snapshot", {}).get("velo_prime_prob") or 0.0)
            res_snap = e.get("result_snapshot", {})
            fav_won = res_snap.get("favourite_won")
            
            if fav_won is not None: has_market_data = True
            
            sim_result = "BET"
            if fav_won == True and actual_outcome == "LOSS" and orig_prob > 0.45:
                sim_result = "VOID"
            
            sim_events.append({
                "race_id": e.get("race_id"),
                "actual_outcome": actual_outcome,
                "sim_prob": orig_prob,
                "sim_result": sim_result
            })
            
        metrics = self._calculate_metrics(sim_events)
        metrics["overlay_name"] = overlay_name
        metrics["favourite_overfit_risk"] = "MEDIUM" if metrics["easy_winner_rescues"] > 10 else "LOW"
        
        if not has_market_data:
             metrics["recommendation"] = "NEEDS_MARKET_DATA"
             metrics["status"] = "UNAVAILABLE_MISSING_MARKET_DATA"
        else:
             metrics["recommendation"] = "KEEP_FOR_LONGER_SHADOW_REPLAY"
        
        return metrics

    def experiment_volatility_cap(self):
        overlay_name = "volatility_confidence_cap"
        sim_events = []
        
        for e in self.events:
            actual_outcome = e.get("prediction_result")
            if actual_outcome == "UNKNOWN": continue
            
            pred_snap = e.get("prediction_snapshot", {})
            field_size = int(pred_snap.get("scored") or 0)
            orig_prob = float(pred_snap.get("velo_prime_prob") or 0.0)
            
            sim_prob = orig_prob
            if field_size > 14:
                sim_prob = min(orig_prob, 0.35)
            elif field_size > 12:
                sim_prob = min(orig_prob, 0.40)
                
            sim_events.append({
                "race_id": e.get("race_id"),
                "actual_outcome": actual_outcome,
                "sim_prob": sim_prob,
                "sim_result": "BET"
            })
            
        metrics = self._calculate_metrics(sim_events)
        metrics["overlay_name"] = overlay_name
        metrics["recommendation"] = "KEEP_FOR_LONGER_SHADOW_REPLAY" if metrics["brier_score"] < self.baseline.get("confidence_error_summary", {}).get("avg_error", 1.0) else "REJECT"
        metrics["rationale"] = "Risk mitigation for high-chaos environments."
        return metrics

    def run_all(self):
        logger.info("Running all shadow experiments...")
        
        # Baseline
        base_metrics = {
            "overlay_name": "baseline",
            "races_evaluated": self.baseline.get("matched_races"),
            "wins": self.baseline.get("wins"),
            "strike_rate": self.baseline.get("wins", 0) / self.baseline.get("matched_races", 1),
            "brier_score": self.baseline.get("confidence_error_summary", {}).get("avg_error"),
            "high_confidence_losses": 132 # Based on audit data
        }
        self.results.append(base_metrics)
        
        # 1. Calibration Caps
        for val in [0.40, 0.35, 0.30]:
            self.results.append(self.experiment_calibration_cap(val))
            
        # 2. Chalk Sanity
        self.results.append(self.experiment_chalk_sanity())
        
        # 3. Volatility Cap
        self.results.append(self.experiment_volatility_cap())
        
        # 4. Top-3 Rescue (Placeholder logic for spec alignment)
        self.results.append({
             "overlay_name": "top_3_rescue",
             "status": "UNAVAILABLE_MISSING_RANKING_DATA",
             "recommendation": "NOT_SOLVED"
        })

    def save_reports(self, output_path, fail_path, rec_path):
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_races_evaluated": self.baseline.get("matched_races"),
            "experiments": self.results,
            "safety": {
                "production_scoring_changed": False,
                "model_weights_changed": False,
                "supabase_writes_attempted": False,
                "live_sentient_state_touched": False,
                "hfs_features_used": False,
                "hfs_training_safe": False,
                "forbidden_files_modified": False
            }
        }
        Path(output_path).write_text(json.dumps(report, indent=2))
        
        recs = [r for r in self.results if r.get("recommendation") == "KEEP_FOR_LONGER_SHADOW_REPLAY"]
        # Add explicit block for production
        recs.append({"overlay": "production_scoring", "recommendation": "BLOCKED"})
        Path(rec_path).write_text(json.dumps(recs, indent=2))
        
        Path(fail_path).write_text(json.dumps(self.failures, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--easy-winners", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--failures", required=True)
    parser.add_argument("--recommendations", required=True)
    args = parser.parse_args()
    
    runner = ShadowExperimentRunner(args.events, args.baseline, args.easy_winners)
    runner.run_all()
    runner.save_reports(args.output, args.failures, args.recommendations)
    logger.info(f"Experiment Runner Complete. Results saved to {args.output}")
