import pandas as pd
import numpy as np
from pathlib import Path

def rigorous_leakage_audit():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    
    print("Loading datasets for rigorous audit...")
    # Load the base training sets (the 'target' dates)
    dfs = []
    for s in ['train', 'val', 'test']:
        df = pd.read_parquet(TRAIN_DIR / f"core_v0_or_{s}.parquet")
        df['split'] = s
        dfs.append(df)
    
    targets = pd.concat(dfs, ignore_index=True)
    targets['date'] = pd.to_datetime(targets['date'])
    targets['horse_norm'] = targets['horse'].str.lower().str.strip()
    
    # Load the V3 candidates generated in the previous step
    v3_dfs = []
    for s in ['train', 'val', 'test']:
        v3_dfs.append(pd.read_parquet(TRAIN_DIR / f"v3_velocity_candidates_{s}.parquet"))
    
    v3_all = pd.concat(v3_dfs, ignore_index=True)
    
    # Merge targets with their V3 features
    audit_df = targets.merge(v3_all, on=['race_id', 'horse'], how='inner')
    
    # Load the historical truth (the 'source' for the features)
    history = pd.read_parquet(ROOT / "data" / "raceform_clean.parquet", columns=['horse', 'date', 'pos'])
    history['date'] = pd.to_datetime(history['date'])
    history['horse_norm'] = history['horse'].str.lower().str.strip()
    
    # Derive won and framed
    # pos is a large_string, can be '1', '2', '3', 'NR', etc.
    def _is_won(p):
        try: return str(p).strip() == '1'
        except: return False
    def _is_framed(p):
        try: 
            s = str(p).strip()
            return s in ('1', '2', '3')
        except: return False
        
    history['won'] = history['pos'].apply(_is_won)
    history['framed'] = history['pos'].apply(_is_framed)
    
    print("Auditing 10,000 random samples for temporal violations...")
    
    # Pick a random sample to verify 'prior_run_date < target_date'
    sample = audit_df.sample(10000, random_state=42)
    
    violations = 0
    for idx, row in sample.iterrows():
        target_date = row['date']
        horse = row['horse_norm']
        
        # In a leak-free system, the features for this horse at this date 
        # must be computable using ONLY runs from history where date < target_date
        
        horse_history = history[history['horse_norm'] == horse].sort_values('date')
        prior_runs = horse_history[horse_history['date'] < target_date]
        
        # Recompute manually
        expected_win_rate_3 = np.nan
        if len(prior_runs) >= 1:
            recent_3 = prior_runs.tail(3)
            expected_win_rate_3 = recent_3['won'].astype(float).mean()
            
        # Verify win_rate_last3
        actual = row['win_rate_last3']
        
        if pd.isna(actual) and pd.isna(expected_win_rate_3):
            continue
            
        if not np.isclose(float(actual), float(expected_win_rate_3), atol=1e-5):
            violations += 1
            print(f"VIOLATION: {horse} at {target_date}. Actual: {actual}, Expected: {expected_win_rate_3}")
            # Print history for debugging if first violation
            if violations == 1:
                print("\nHorse History:")
                print(horse_history[['date', 'won']].to_string(index=False))
            if violations > 5: break
            
    if violations == 0:
        print("\nVERIFIED: prior_run_date < target_date holds across 10,000 samples.")
        print("LEAKAGE AUDIT: PASS")
    else:
        print(f"\nLEAKAGE AUDIT: FAIL ({violations} violations found)")

if __name__ == "__main__":
    rigorous_leakage_audit()
