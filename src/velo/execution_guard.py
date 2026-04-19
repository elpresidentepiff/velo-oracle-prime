import logging
from typing import Dict, Optional

logger = logging.getLogger("ExecutionGuard")

class ExecutionGuard:
    """
    Surgical Execution Blocker for VÉLØ Oracle Prime.
    Enforces the Kill Lane and protects the Fortress.
    """
    def __init__(self):
        self.tight_tracks = ["Chester", "Lingfield", "Wolverhampton", "Kempton"]

    def evaluate_execution(self, verdict: Dict) -> Dict:
        """
        Determines the final execution lane for a verdict.
        Returns: { 'lane': str, 'blocked': bool, 'reason': str }
        """
        tier = verdict.get("decision_tier", "X")
        conf = verdict.get("confidence_level", "NORMAL")
        sp = float(verdict.get("actual_winner_sp", 0) or 0) # Use market price in live
        prob_gap = float(verdict.get("prob_gap", 0) or 0)
        track = verdict.get("track", "")
        
        # ── 1. KILL LANE: AMPOUTATION ──────────────────────────────────────────
        if tier in ["C", "D"]:
            return {"lane": "KILL", "blocked": True, "reason": f"Tier {tier} rot amputation."}
        
        if sp >= 12.0:
            # Shift to VISION lane for longshots, but block from standard WIN-betting
            return {"lane": "VISION", "blocked": True, "reason": "SP > 12.0: Move to longshot monitoring."}
        
        if prob_gap < 0.05:
            return {"lane": "KILL", "blocked": True, "reason": f"Weak margin (gap: {prob_gap:.3f})."}

        # ── 2. GEOMETRY/SUBSTRATE HANDBRAKE ───────────────────────────────────
        draw = verdict.get("top_horse_draw")
        if track in self.tight_tracks and draw and int(draw) > 8:
            return {"lane": "KILL", "blocked": True, "reason": f"Wide draw ({draw}) on tight track ({track})."}

        # ── 3. FORTRESS LANE: AUTHORIZATION ──────────────────────────────────
        if tier == "A" and conf == "HIGH" and sp < 5.0 and prob_gap >= 0.08:
            return {"lane": "FORTRESS", "blocked": False, "reason": "GOLD STANDARD"}

        # ── 4. FRAME LANE (SHADOW UNTIL BSP) ──────────────────────────────────
        if 5.0 <= sp < 12.0:
            return {"lane": "FRAME", "blocked": True, "reason": "SHADOW: Awaiting BSP price discovery."}

        return {"lane": "VISION", "blocked": True, "reason": "Non-premium vision."}

if __name__ == "__main__":
    print("ExecutionGuard Ready.")
