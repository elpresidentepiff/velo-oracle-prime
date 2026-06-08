import pandas as pd
import numpy as np
from pathlib import Path
import json

def research_thresholds():
    p = Path("data/new_build/v1_v3_analysis_set.parquet")
    if not p.exists():
        print(f"Error: {p} not found")
        return
        
    df = pd.read_parquet(p)
    print(f"Loaded {len(df):,} analysis rows.")
    
    # 1. Basic Stats
    win_rate = df['won'].mean()
    frame_rate = df['framed'].mean()
    print(f"Global Base: Win={win_rate:.1%}, Frame={frame_rate:.1%}")
    
    # 2. V1 Prob Segmentation
    # Calculate ranks per race_id
    df['v1_rank'] = df.groupby('race_id')['v1_prob'].rank(ascending=False, method='min')
    top1s = df[df['v1_rank'] == 1].copy()
    
    print(f"\nTop 1 Selection Baseline (V1):")
    print(f"  n={len(top1s):,}")
    print(f"  SR: {top1s['won'].mean():.1%}")
    print(f"  Frame: {top1s['framed'].mean():.1%}")

    # 3. Decision Policy Candidate: WIN_TRUST
    # Criteria: Top 1 + VP >= 0.30 + High Passport Coverage (career_runs >= 5)
    win_trust = top1s[
        (top1s['v1_prob'] >= 0.30) & 
        (top1s['pp_career_runs'] >= 5)
    ]
    print(f"\nLane: WIN_TRUST (VP>=0.30, Runs>=5)")
    print(f"  n={len(win_trust):,} ({len(win_trust)/len(top1s):.1%})")
    print(f"  SR: {win_trust['won'].mean():.1%}")
    print(f"  Frame: {win_trust['framed'].mean():.1%}")
    
    # 4. Decision Policy Candidate: FRAME_TRUST
    # Criteria: Top 1 + VP [0.20 - 0.30] + High Velocity (place_rate_last3 >= 0.66)
    frame_trust = top1s[
        (top1s['v1_prob'] >= 0.20) & (top1s['v1_prob'] < 0.30) &
        (top1s['place_rate_last3'] >= 0.66)
    ]
    print(f"\nLane: FRAME_TRUST (VP 20-30, PlaceRateLast3>=0.66)")
    print(f"  n={len(frame_trust):,} ({len(frame_trust)/len(top1s):.1%})")
    print(f"  SR: {frame_trust['won'].mean():.1%}")
    print(f"  Frame: {frame_trust['framed'].mean():.1%}")

    # 5. Decision Policy Candidate: SUPPRESS
    # Criteria: Top 1 + VP < 0.25 + Low Passport (career_runs < 3)
    suppress = top1s[
        (top1s['v1_prob'] < 0.25) & 
        (top1s['pp_career_runs'] < 3)
    ]
    print(f"\nLane: SUPPRESS (VP<0.25, Runs<3)")
    print(f"  n={len(suppress):,} ({len(suppress)/len(top1s):.1%})")
    print(f"  SR: {suppress['won'].mean():.1%}")
    print(f"  Frame: {suppress['framed'].mean():.1%}")

    # 6. Decision Policy Candidate: LOW_DATA
    # Criteria: career_runs == 0
    low_data = top1s[top1s['pp_career_runs'] == 0]
    print(f"\nLane: LOW_DATA (Career Runs = 0)")
    print(f"  n={len(low_data):,}")
    print(f"  SR: {low_data['won'].mean():.1%}")
    
    # 7. Final Output for Policy Doc
    policy = {
        "WIN_TRUST": {"vp_min": 0.30, "runs_min": 5, "target_sr": 0.40},
        "FRAME_TRUST": {"vp_min": 0.20, "place_rate_last3_min": 0.66, "target_frame": 0.75},
        "SUPPRESS": {"vp_max": 0.25, "runs_max": 2}
    }
    Path("data/new_build/reports/policy_v1_threshold_research.json").write_text(json.dumps(policy, indent=2))

if __name__ == "__main__":
    research_thresholds()
