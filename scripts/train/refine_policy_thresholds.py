import pandas as pd
import numpy as np
from pathlib import Path
import json

def refine_thresholds():
    p = Path("data/new_build/v1_v3_analysis_set.parquet")
    df = pd.read_parquet(p)
    df['v1_rank'] = df.groupby('race_id')['v1_prob'].rank(ascending=False, method='min')
    top1s = df[df['v1_rank'] == 1].copy()
    
    print("--- Refining FRAME_TRUST ---")
    
    scenarios = [
        ("VP 20-30, Place3=0.66", top1s[(top1s['v1_prob'] >= 0.20) & (top1s['v1_prob'] < 0.30) & (top1s['place_rate_last3'] >= 0.66)]),
        ("VP 20-30, Place3=1.0", top1s[(top1s['v1_prob'] >= 0.20) & (top1s['v1_prob'] < 0.30) & (top1s['place_rate_last3'] >= 1.0)]),
        ("VP 25-30, Place3=0.66", top1s[(top1s['v1_prob'] >= 0.25) & (top1s['v1_prob'] < 0.30) & (top1s['place_rate_last3'] >= 0.66)]),
        ("VP 25-30, Place3=1.0", top1s[(top1s['v1_prob'] >= 0.25) & (top1s['v1_prob'] < 0.30) & (top1s['place_rate_last3'] >= 1.0)]),
    ]
    
    for label, res in scenarios:
        print(f"{label}: n={len(res)}, SR={res['won'].mean():.1%}, Frame={res['framed'].mean():.1%}")

    print("\n--- Refining WIN_TRUST ---")
    scenarios_win = [
        ("VP>=30, Runs>=5", top1s[(top1s['v1_prob'] >= 0.30) & (top1s['pp_career_runs'] >= 5)]),
        ("VP>=35, Runs>=5", top1s[(top1s['v1_prob'] >= 0.35) & (top1s['pp_career_runs'] >= 5)]),
        ("VP>=30, Runs>=10", top1s[(top1s['v1_prob'] >= 0.30) & (top1s['pp_career_runs'] >= 10)]),
    ]
    for label, res in scenarios_win:
        print(f"{label}: n={len(res)}, SR={res['won'].mean():.1%}, Frame={res['framed'].mean():.1%}")

if __name__ == "__main__":
    refine_thresholds()
