"""
Apply New Build Decision Policy V1 to predictions.
Categorizes runners into tactical lanes based on V1 prob, passport, and velocity.
"""
import pandas as pd
import numpy as np

def apply_policy_v1(row: dict) -> dict:
    # Anchor VP from Lane B (Challenger V1)
    vp = float(row.get("lane_b_prob") or row.get("v1_prob") or 0)
    
    # Context from Passport
    pp = row.get("passport_summary") or {}
    pp_live = row.get("passport_live_features") or {}
    
    runs = int(pp.get("career_runs") or 0)
    
    # Velocity Sidecar
    place3 = float(pp_live.get("pp_place_rate_last3") or 0)
    
    rank = int(row.get("lane_b_rank") or row.get("champion_rank") or 0)
    
    lane = "NO_EDGE"
    reasons = []
    
    # Only categorize top-ranked runners for trust lanes
    if rank == 1:
        if vp >= 0.30 and runs >= 5:
            lane = "WIN_TRUST"
            reasons.append("HIGH_VP_PROVEN_HISTORY")
        elif vp >= 0.25 and place3 >= 0.66:
            lane = "FRAME_TRUST"
            reasons.append("STRONG_RECENCY_CONFLUENCE")
        elif vp < 0.25 and runs < 3:
            lane = "SUPPRESS"
            reasons.append("LOW_DATA_WEAK_SIGNAL")
        elif runs == 0:
            lane = "LOW_DATA"
            reasons.append("FIRST_TIME_OUT_OR_UNCAPTURED")
    else:
        # Lower ranks: mostly NO_EDGE or SUPPRESS if extremely low data
        if runs == 0:
            lane = "LOW_DATA"
            reasons.append("RANK_LOW_DATA")

    return {
        "nb_decision_lane": lane,
        "nb_policy_reasons": reasons
    }
if __name__ == "__main__":
    # Test sample 1: WIN_TRUST
    test_row = {
        "lane_b_prob": 0.32,
        "champion_rank": 1,
        "passport_summary": {"career_runs": 10},
        "passport_live_features": {"pp_place_rate_last3": 0.33}
    }
    print(f"Sample (WIN_TRUST expected): {apply_policy_v1(test_row)}")

    # Test sample 2: FRAME_TRUST
    test_row_2 = {
        "lane_b_prob": 0.26,
        "champion_rank": 1,
        "passport_summary": {"career_runs": 4},
        "passport_live_features": {"pp_place_rate_last3": 0.67}
    }
    print(f"Sample 2 (FRAME_TRUST expected): {apply_policy_v1(test_row_2)}")

