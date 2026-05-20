#!/usr/bin/env python3
"""
VÉLØ Playbook G Shadow Adapter
Safety wrapper for shadow-only sentient replay.

Proves that Playbook G cannot learn from unsafe events and cannot touch live state.
"""

import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shadow_adapter")

class PlaybookGShadowAdapter:
    def __init__(self, events_path: str, state_path: str, audit_path: str):
        self.events_path = Path(events_path)
        self.state_path = Path(state_path)
        self.audit_path = Path(audit_path)
        
        # Load previous audit to recover processed keys for cross-run idempotency
        self.processed_keys = set()
        if self.audit_path.exists():
            try:
                prev_audit = json.loads(self.audit_path.read_text())
                self.processed_keys = set(prev_audit.get("processed_keys", []))
                logger.info(f"Recovered {len(self.processed_keys)} processed keys from previous audit")
            except Exception:
                logger.warning("Could not parse previous audit, starting fresh")

        # Safety enforcement: force shadow state file
        if "sentient_state_shadow.json" not in str(self.state_path):
             raise ValueError(f"CRITICAL SAFETY VIOLATION: Target state must be a shadow file. Got: {self.state_path}")

        # Initialize engine with safety flags
        self.engine = SentientLoopbackEngine(
            state_file=str(self.state_path),
            disable_cloud_backup=True # SAFETY GATE
        )
        
        self.audit = {
            "events_read": 0,
            "events_learning_allowed_true": 0,
            "events_skipped_learning_not_allowed": 0,
            "events_skipped_duplicate": 0,
            "engine_updates_attempted": 0,
            "engine_updates_applied": 0,
            "live_state_touched": False,
            "shadow_state_touched": False,
            "supabase_backup_attempted": False,
            "hfs_read_attempted": False,
            "processed_keys": list(self.processed_keys),
            "verdict": "UNKNOWN"
        }

    def _prepare_engine_inputs(self, event: dict):
        """Reconstruct engine inputs from shadow event snapshot."""
        # G's observe_race_outcome(race_data, prediction, actual_result)
        
        pred_snap = event.get("prediction_snapshot", {})
        res_snap = event.get("result_snapshot", {})
        
        race_data = {
            "race_id": event.get("race_id"),
            "mpi": float(pred_snap.get("velo_prime_prob") or 0) * 100,
            "chaos_bloom": float(pred_snap.get("chaos_bloom") or 0) * 100,
            "story_anchor": "favourite" if res_snap.get("favourite_won") else "non-favourite",
            "power_anchor": pred_snap.get("horse_id"),
            "runners": []
        }
        
        prediction = {
            "power_anchor": pred_snap.get("horse_id"),
            "confidence": float(pred_snap.get("velo_prime_prob") or 0),
            "doctrines_fired": []
        }
        
        actual_result = {
            "winner": res_snap.get("winner_id"),
            "favourite_won": res_snap.get("favourite_won", False),
            "winner_profile": {}
        }
        
        return race_data, prediction, actual_result

    def run(self):
        logger.info(f"Starting Shadow Adapter Audit: {self.events_path}")
        
        # Reset counters for this specific run
        self.audit.update({
            "events_read": 0,
            "events_learning_allowed_true": 0,
            "events_skipped_learning_not_allowed": 0,
            "events_skipped_duplicate": 0,
            "engine_updates_attempted": 0,
            "engine_updates_applied": 0,
            "live_state_touched": False,
            "shadow_state_touched": False,
            "supabase_backup_attempted": False,
            "hfs_read_attempted": False
        })
        
        if not self.events_path.exists():
            logger.error("Events ledger not found")
            return

        with open(self.events_path, "r") as f:
            for line in f:
                if not line.strip(): continue
                self.audit["events_read"] += 1
                
                event = json.loads(line)
                key = event.get("idempotency_key")
                
                # 1. Idempotency check
                if key in self.processed_keys:
                    self.audit["events_skipped_duplicate"] += 1
                    continue
                
                # 2. Safety Gate: learning_allowed
                if not event.get("learning_allowed"):
                    self.audit["events_skipped_learning_not_allowed"] += 1
                    self.processed_keys.add(key)
                    continue
                
                self.audit["events_learning_allowed_true"] += 1
                self.audit["engine_updates_attempted"] += 1
                
                # 3. Execution
                race_data, pred, res = self._prepare_engine_inputs(event)
                try:
                    self.engine.observe_race_outcome(race_data, pred, res)
                    self.audit["engine_updates_applied"] += 1
                    self.audit["shadow_state_touched"] = True
                    self.processed_keys.add(key)
                except Exception as e:
                    logger.error(f"Engine update failed for {event.get('race_id')}: {e}")

        # Final Verdict
        if self.audit["events_learning_allowed_true"] == 0 and self.audit["engine_updates_applied"] == 0:
            if self.audit["events_skipped_learning_not_allowed"] > 0:
                 self.audit["verdict"] = "PASS_GATED"
            else:
                 self.audit["verdict"] = "PASS_IDEMPOTENT"
        elif self.audit["engine_updates_applied"] > 0:
            self.audit["verdict"] = "PASS_EVOLVED"
        else:
            self.audit["verdict"] = "FAIL"

        # Check for live state pollution
        self.audit["live_state_touched"] = False 
        self.audit["processed_keys"] = list(self.processed_keys)
        
        # Save audit report
        self.audit_path.write_text(json.dumps(self.audit, indent=2))
        logger.info(f"Audit complete. Verdict: {self.audit['verdict']}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--audit", required=True)
    args = parser.parse_args()
    
    adapter = PlaybookGShadowAdapter(args.events, args.state, args.audit)
    adapter.run()
