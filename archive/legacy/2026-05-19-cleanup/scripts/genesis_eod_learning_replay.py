#!/usr/bin/env python3
"""
VÉLØ Genesis EOD Learning Replay
Makes VÉLØ learn from its entire life history in SHADOW MODE.

Strictly outcome-only. No HFS features used.
"""

import json
import os
import sys
import glob
import logging
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add root to path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
from scripts.playbook_g_shadow_adapter import PlaybookGShadowAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("genesis_replay")

class GenesisEODReplay:
    def __init__(self, pred_pattern: str, res_pattern: str, state_path: str, events_path: str, report_path: str, failures_path: str):
        self.pred_pattern = pred_pattern
        self.res_pattern = res_pattern
        self.state_path = Path(state_path)
        self.events_path = Path(events_path)
        self.report_path = Path(report_path)
        self.failures_path = Path(failures_path)
        self.live_state_path = ROOT / "data" / "sentient_state.json"
        
        self.failures = []
        self.stats = {
            "prediction_files_found": 0,
            "result_files_found": 0,
            "total_predictions_found": 0,
            "total_results_found": 0,
            "matched_races": 0,
            "events_created": 0,
            "events_learning_allowed_true": 0,
            "wins": 0,
            "losses": 0,
            "void_or_unknown": 0,
            "loss_count_by_type": Counter(),
            "confidence_error_sum": 0.0,
            "confidence_error_count": 0,
            "earliest_date": "9999-99-99",
            "latest_date": "0000-00-00"
        }

    def _get_file_hash(self, path: Path):
        if not path.exists(): return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _discover_and_load(self):
        pred_files = sorted(glob.glob(str(ROOT / self.pred_pattern)))
        res_files = sorted(glob.glob(str(ROOT / self.res_pattern)))
        
        self.stats["prediction_files_found"] = len(pred_files)
        self.stats["result_files_found"] = len(res_files)
        
        preds_all = []
        results_map = {}
        
        for pf in pred_files:
            try:
                # Derive date from filename: data/velo_prime_verdicts_2026_03_17.json
                filename = os.path.basename(pf)
                date_from_file = None
                if "verdicts_" in filename:
                    parts = filename.split("verdicts_")[-1].split(".json")[0].replace("_", "-")
                    date_from_file = parts # YYYY-MM-DD
                
                data = json.loads(Path(pf).read_text())
                for race in data:
                    race_data = race.copy()
                    if "date" not in race_data and date_from_file:
                        race_data["date"] = date_from_file
                    preds_all.append({"data": race_data, "source": pf})
                    self.stats["total_predictions_found"] += 1
            except Exception as e:
                logger.error(f"Error loading {pf}: {e}")

        for rf in res_files:
            try:
                data = json.loads(Path(rf).read_text())
                res_list = data.get("results", []) if isinstance(data, dict) else data
                for race in res_list:
                    rid = race.get("race_id") or race.get("id")
                    if rid:
                        results_map[rid] = {"data": race, "source": rf}
                        self.stats["total_results_found"] += 1
            except Exception as e:
                logger.error(f"Error loading {rf}: {e}")
                
        return preds_all, results_map

    def _classify_loss(self, prediction: dict, result: dict) -> str:
        if not prediction or not result: return "DATA_ERROR"
        
        # Determine winner
        runners = result.get("runners", [])
        winner_id = None
        sorted_runners = sorted([r for r in runners if str(r.get("position", "")).isdigit()], 
                             key=lambda r: int(r["position"]))
        if sorted_runners:
            winner_id = sorted_runners[0].get("horse_id")
            
        top_pick = prediction.get("top", {})
        if not top_pick: return "DATA_ERROR"
        
        outcome = "WIN" if top_pick.get("horse_id") == winner_id else "LOSS"
        if outcome == "WIN": return "NONE"
        
        prob = float(top_pick.get("velo_prime_prob") or 0)
        fav_won = result.get("favourite_won", False)
        
        if prob > 0.35: return "CALIBRATION_ERROR"
        if fav_won and prob < 0.2: return "MARKET_LIED"
        return "WRONG_HORSE"

    def run(self):
        logger.info("Starting Genesis EOD Learning Replay")
        
        # Clear audit at start of full session
        audit_path = ROOT / "data" / "playbook_g_shadow_adapter_audit_v1.json"
        if audit_path.exists(): audit_path.unlink()

        live_hash_before = self._get_file_hash(self.live_state_path)
        shadow_hash_before = self._get_file_hash(self.state_path)
        
        preds_all, results_map = self._discover_and_load()
        
        if self.events_path.exists(): self.events_path.unlink()
        
        for p_item in preds_all:
            p_race = p_item["data"]
            rid = p_race.get("race_id")
            date = p_race.get("date")
            
            if not rid:
                self.failures.append({"type": "BAD_RACE_ID", "prediction_source": p_item["source"]})
                continue
                
            if date:
                self.stats["earliest_date"] = min(self.stats["earliest_date"], date)
                self.stats["latest_date"] = max(self.stats["latest_date"], date)

            if rid not in results_map:
                self.failures.append({"type": "MISSING_RESULT", "race_id": rid, "date": date})
                continue
            
            res_item = results_map[rid]
            r_race = res_item["data"]
            self.stats["matched_races"] += 1
            
            top_pick = p_race.get("top", {})
            winner_id = None
            runners = r_race.get("runners", [])
            sorted_runners = sorted([r for r in runners if str(r.get("position", "")).isdigit()], 
                                 key=lambda r: int(r["position"]))
            if sorted_runners: winner_id = sorted_runners[0].get("horse_id")

            outcome = "UNKNOWN"
            if top_pick and winner_id:
                outcome = "WIN" if top_pick.get("horse_id") == winner_id else "LOSS"
            
            loss_type = self._classify_loss(p_race, r_race)
            
            # Outcome-Only Event Schema
            event = {
                "event_type": "result_confirmed",
                "learning_mode": "OUTCOME_ONLY_EOD_REPLAY",
                "learning_allowed": True,
                "learning_permission_reason": "OUTCOME_ONLY_NO_HFS_FEATURES",
                "hfs_training_safe": False,
                "hfs_features_used": False,
                "sentient_state_target": str(self.state_path),
                "idempotency_key": f"{rid}:{date}",
                "race_id": rid,
                "event_date": date,
                "prediction_snapshot": top_pick,
                "result_snapshot": {
                    "winner_id": winner_id,
                    "favourite_won": r_race.get("favourite_won")
                },
                "market_snapshot": {},
                "prediction_result": outcome,
                "loss_type": loss_type,
                "confidence_error": abs(float(top_pick.get("velo_prime_prob") or 0.0) - (1.0 if outcome == "WIN" else 0.0)),
                "source_prediction": p_item["source"],
                "source_result": res_item["source"]
            }
            
            # Safety Gate: if someone accidentally put HFS features here
            if "strictly_ordered_vector" in top_pick or "feature_json" in p_race:
                event["learning_allowed"] = False
                event["failure_reason"] = "UNSAFE_HFS_FIELD_PRESENT"
                self.failures.append({"type": "UNSAFE_HFS_FIELD_PRESENT", "race_id": rid})
            
            with open(self.events_path, "a") as f:
                f.write(json.dumps(event) + "\n")
            
            self.stats["events_created"] += 1
            if event["learning_allowed"]:
                self.stats["events_learning_allowed_true"] += 1
                if outcome == "WIN": self.stats["wins"] += 1
                elif outcome == "LOSS": self.stats["losses"] += 1
                else: self.stats["void_or_unknown"] += 1
                self.stats["loss_count_by_type"][loss_type] += 1
                self.stats["confidence_error_sum"] += event["confidence_error"]
                self.stats["confidence_error_count"] += 1

        # Run shadow adapter
        adapter = PlaybookGShadowAdapter(str(self.events_path), str(self.state_path), str(audit_path))
        adapter.run()
        audit_1 = json.loads(audit_path.read_text())
        updates_1 = audit_1["engine_updates_applied"]
        
        # Second run for idempotency
        adapter.run()
        audit_2 = json.loads(audit_path.read_text())
        updates_2 = audit_2["engine_updates_applied"]
        duplicates_skipped = audit_2["events_skipped_duplicate"]

        live_hash_after = self._get_file_hash(self.live_state_path)
        shadow_hash_after = self._get_file_hash(self.state_path)

        # Final Report
        report = {
            "earliest_prediction_date": self.stats["earliest_date"],
            "latest_prediction_date": self.stats["latest_date"],
            "prediction_files_found": self.stats["prediction_files_found"],
            "result_files_found": self.stats["result_files_found"],
            "total_predictions_found": self.stats["total_predictions_found"],
            "total_results_found": self.stats["total_results_found"],
            "matched_races": self.stats["matched_races"],
            "events_created": self.stats["events_created"],
            "events_learning_allowed_true": self.stats["events_learning_allowed_true"],
            "hfs_features_used": False,
            "engine_updates_applied_first_run": updates_1,
            "engine_updates_applied_duplicate_run": updates_2,
            "duplicates_skipped_second_run": duplicates_skipped,
            "wins": self.stats["wins"],
            "losses": self.stats["losses"],
            "void_or_unknown": self.stats["void_or_unknown"],
            "loss_count_by_type": dict(self.stats["loss_count_by_type"]),
            "confidence_error_summary": {
                "avg_error": self.stats["confidence_error_sum"] / self.stats["confidence_error_count"] if self.stats["confidence_error_count"] > 0 else 0
            },
            "live_sentient_state_hash_before": live_hash_before,
            "live_sentient_state_hash_after": live_hash_after,
            "live_sentient_state_unchanged": live_hash_before == live_hash_after,
            "shadow_state_hash_before": shadow_hash_before,
            "shadow_state_hash_after": shadow_hash_after,
            "shadow_state_changed": shadow_hash_before != shadow_hash_after,
            "supabase_writes_attempted": False,
            "supabase_backup_attempted": False,
            "hfs_read_attempted": False,
            "verdict": "PASS" if updates_1 > 0 and updates_2 == 0 and live_hash_before == live_hash_after else "FAIL"
        }
        
        self.report_path.write_text(json.dumps(report, indent=2))
        self.failures_path.write_text(json.dumps(self.failures, indent=2))
        logger.info(f"Genesis Replay Complete. Updates applied: {updates_1}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--failures", required=True)
    args = parser.parse_args()
    
    replay = GenesisEODReplay(args.predictions, args.results, args.state, args.events, args.report, args.failures)
    replay.run()
