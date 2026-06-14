"""
Apply New Build Decision Policy V1 (Consolidated).
Anchored to Challenger V1 (Lane B) with V3 Velocity sidecar support.
"""
from __future__ import annotations
import pandas as pd
import numpy as np

# ── Thresholds (Calibrated June 2026) ────────────────────────────────────────
WIN_TRUST_VP_MIN = 0.22
WIN_TRUST_PP_MIN = 1.0

FRAME_TRUST_VP_MIN = 0.17
FRAME_TRUST_PLACE_RATE_MIN = 0.50
FRAME_TRUST_PP_PROXY = 2.0

SUPPRESS_VP_MAX = 0.10
SUPPRESS_PP_MAX = 0.0

LOW_DATA_PP_FLOOR = 0.0

def apply_policy_v1(row: dict) -> dict:
    """
    Classify a runner into a tactical decision lane.
    Used by scripts/ops/new_build_two_lane_score.py.
    """
    # 1. Extraction
    vp = float(row.get("lane_b_prob") or row.get("v1_prob") or row.get("champion_probability") or 0.0)
    
    # Passport/Profile Context
    pp_summary = row.get("passport_summary") or {}
    pp_score = row.get("passport_strength_score")
    if pp_score is None:
        # Fallback check for raw PP strength
        pp_score = float(pp_summary.get("passport_strength_score", 1.0)) # Default to 1.0 if found but score missing
        
    pp_found = bool(row.get("passport_found"))
    runs = int(pp_summary.get("career_runs") or 0)
    
    # V3 Velocity Sidecar
    pp_live = row.get("passport_live_features") or {}
    # Prioritize live-computed velocity from passport
    place3 = pp_live.get("pp_place_rate_last3")
    if place3 is None:
        # Fallback to sidecar field if already joined
        place3 = row.get("v3_place_rate_last3")
    
    place3 = float(place3) if place3 is not None else None
    
    # Ranking (Policy primarily focuses on Top Picks)
    rank = int(row.get("lane_b_rank") or row.get("champion_rank") or 99)
    
    # 2. Logic
    lane = "NO_EDGE"
    reasons = []

    # LOW_DATA: No passport or profile too weak to trust
    if not pp_found or (pp_score is not None and pp_score < LOW_DATA_PP_FLOOR):
        lane = "LOW_DATA"
        reasons.append("INSUFFICIENT_PASSPORT_DATA")
        return {"nb_decision_lane": lane, "nb_policy_reasons": reasons}

    # SUPPRESS: Actively ignore low-edge mass
    if vp <= SUPPRESS_VP_MAX:
        lane = "SUPPRESS"
        reasons.append("LOW_PROBABILITY_FADE")
    elif pp_score is not None and pp_score <= SUPPRESS_PP_MAX:
        lane = "SUPPRESS"
        reasons.append("WEAK_PROFILE_SUPPRESSION")
        
    if lane == "SUPPRESS":
        return {"nb_decision_lane": lane, "nb_policy_reasons": reasons}

    # High conviction lanes focus on rank=1
    if rank == 1:
        # WIN_TRUST: High VP + Proven Baseline
        if vp >= WIN_TRUST_VP_MIN:
            pp_ok = pp_score is None or pp_score >= WIN_TRUST_PP_MIN
            if pp_ok:
                lane = "WIN_TRUST"
                reasons.append("HIGH_VP_PROVEN_HISTORY")
                return {"nb_decision_lane": lane, "nb_policy_reasons": reasons}

        # FRAME_TRUST: Recency Velocity or Proxy
        if vp >= FRAME_TRUST_VP_MIN:
            if place3 is not None and place3 >= FRAME_TRUST_PLACE_RATE_MIN:
                lane = "FRAME_TRUST"
                reasons.append("STRONG_RECENCY_VELOCITY")
            elif pp_score is not None and pp_score >= FRAME_TRUST_PP_PROXY:
                lane = "FRAME_TRUST"
                reasons.append("STRONG_PROFILE_FRAME_PROXY")
            
            if lane == "FRAME_TRUST":
                return {"nb_decision_lane": lane, "nb_policy_reasons": reasons}

    return {
        "nb_decision_lane": lane,
        "nb_policy_reasons": reasons
    }

if __name__ == "__main__":
    # Test WIN_TRUST (rank 1, high vp)
    r1 = {"lane_b_prob": 0.25, "lane_b_rank": 1, "passport_found": True, "passport_strength_score": 1.5}
    print(f"R1 (WIN_TRUST): {apply_policy_v1(r1)}")
    
    # Test FRAME_TRUST (rank 1, medium vp, high velocity)
    r2 = {"lane_b_prob": 0.18, "lane_b_rank": 1, "passport_found": True, "passport_live_features": {"pp_place_rate_last3": 0.66}}
    print(f"R2 (FRAME_TRUST): {apply_policy_v1(r2)}")
    
    # Test SUPPRESS (low prob)
    r3 = {"lane_b_prob": 0.08, "lane_b_rank": 1, "passport_found": True}
    print(f"R3 (SUPPRESS): {apply_policy_v1(r3)}")
