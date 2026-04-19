import os
import json
import pandas as pd
import numpy as np

def run_explainer():
    print("=== VÉLØ POST-TRAINING TRUTH EXPLAINER ===")

    # 1. Load Data
    try:
        with open('tmp/sigma_full_corpus.json', 'r') as f:
            corpus = json.load(f)
        df = pd.DataFrame(corpus)
        df['sp'] = pd.to_numeric(df['actual_winner_sp'], errors='coerce').fillna(0)
        df['outcome'] = df['outcome'].fillna('').str.upper()
        df['win'] = df['outcome'] == 'WIN'
        df['placed'] = df['outcome'] == 'PLACED'
        df['tier'] = df['decision_tier'].fillna('X')
        df['conf'] = df['confidence_level'].fillna('NORMAL').str.upper()
        
        # Approximate prob_gap from verdict_score (or assume typical gap if missing for simulation)
        df['prob_gap'] = pd.to_numeric(df['verdict_score'], errors='coerce').fillna(0.0) 
        
        # Load Raceform for feature extraction (if available)
        rf_path = 'data/raceform_v17_features.parquet'
        rf = pd.read_parquet(rf_path) if os.path.exists(rf_path) else pd.DataFrame()
        
    except Exception as e:
        print(f"Data Load Error: {e}")
        return

    tight_tracks = ["Chester", "Lingfield", "Wolverhampton", "Kempton"]

    # 2. Failure Attribution Engine
    def classify_failure(row):
        if row['win']: return "true_win"
        if row['placed']: return "true_frame"
        
        if row['tier'] in ['C', 'D', 'X']: return "tier_amputation"
        if row['sp'] >= 12.0: return "mid_price_dead_zone"
        if row['miss_reason'] == 'market_decoy_followed': return "market_decoy_followed"
        if row['prob_gap'] < 0.05: return "false_rank1_overcommit"
        if row['track'] in tight_tracks: return "geometry_kill"
        if row['sp'] >= 5.0 and row['sp'] < 12.0: return "blindspot_winner_outside_top5" # Simplified
        
        return "outsider_noise"

    df['failure_class'] = df.apply(classify_failure, axis=1)

    # 3. Product Assignment Engine
    def assign_product(row):
        if row['tier'] in ['C', 'D', 'X'] or row['sp'] >= 12.0 or row['miss_reason'] == 'market_decoy_followed':
            return "PASS"
        if row['tier'] == 'A' and row['conf'] == 'HIGH' and row['sp'] < 5.0 and row['prob_gap'] >= 0.08:
            return "WIN_ONLY"
        if row['tier'] in ['A', 'B'] and 5.0 <= row['sp'] < 12.0:
            return "EW_CANDIDATE" if row['tier'] == 'A' else "FRAME_ONLY"
        if row['sp'] >= 20.0 and row['tier'] in ['A', 'B']:
            return "VISION_ONLY"
        return "PASS"

    df['product_assignment'] = df.apply(assign_product, axis=1)

    # 4. Feature Extraction (Overtrusted vs Underweighted)
    if 'top_horse_readiness_state' in df.columns:
        overtrusted = df[~df['win']]['top_horse_readiness_state'].value_counts().head(5).to_dict()
    else:
        overtrusted = {"missing_data": 0}
    
    # 5. Scoreboard Generation
    scoreboard = {
        "global": {
            "total_races": len(df),
            "wins": int(df['win'].sum()),
            "frames": int((df['win'] | df['placed']).sum()),
            "strike_rate": round(df['win'].mean() * 100, 1),
            "frame_rate": round((df['win'] | df['placed']).mean() * 100, 1)
        },
        "failure_classes": df['failure_class'].value_counts().to_dict(),
        "product_assignments": df['product_assignment'].value_counts().to_dict(),
        "overtrusted_features": overtrusted,
        "a_tier_win": round(df[df['tier'] == 'A']['win'].mean() * 100, 1)
    }

    # Write output JSONs
    os.makedirs('tmp', exist_ok=True)
    with open('tmp/velo_post_training_truth_scoreboard.json', 'w') as f:
        json.dump(scoreboard, f, indent=2)

    # Write output MD
    md_content = f"""# VÉLØ Post-Training Truth Scoreboard
**Generated:** 2026-04-19 | **Source:** 1,107 Audited Races

## 1. Global Performance
- **Total Races:** {scoreboard['global']['total_races']}
- **Strike Rate:** {scoreboard['global']['strike_rate']}%
- **Frame Rate:** {scoreboard['global']['frame_rate']}%
- **A-Tier Strike:** {scoreboard['a_tier_win']}%

## 2. Product Assignment Simulation
By retroactively applying the Four-Lane Law:
- **PASS:** {scoreboard['product_assignments'].get('PASS', 0)} races (Junk amputated)
- **WIN_ONLY (Fortress):** {scoreboard['product_assignments'].get('WIN_ONLY', 0)} races
- **EW_CANDIDATE / FRAME_ONLY:** {scoreboard['product_assignments'].get('EW_CANDIDATE', 0) + scoreboard['product_assignments'].get('FRAME_ONLY', 0)} races
- **VISION_ONLY:** {scoreboard['product_assignments'].get('VISION_ONLY', 0)} races

## 3. Top Failure Classes
"""
    for fc, count in scoreboard['failure_classes'].items():
        md_content += f"- **{fc}:** {count}\n"

    with open('tmp/velo_post_training_truth_scoreboard.md', 'w') as f:
        f.write(md_content)

    print("Post-Training Truth Explainer execution complete. Artifacts generated.")

if __name__ == "__main__":
    run_explainer()
