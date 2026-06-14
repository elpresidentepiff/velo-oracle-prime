import pandas as pd
import numpy as np
from pathlib import Path
import json
from tqdm import tqdm

def build_rolling_jtcd():
    print("Loading source datasets...")
    hist_path = Path("data/new_build/training/core_v0_historical_dataset.parquet")
    v17_path = Path("data/raceform_v17_features.parquet")
    
    df = pd.read_parquet(hist_path)
    # Filter only needed columns to save memory
    df = df[['race_id', 'date', 'course', 'horse', 'jockey', 'trainer', 'dist_f', 'going_code', 'won', 'pos_num']]
    df['date'] = pd.to_datetime(df['date'])
    df['won'] = df['won'].fillna(0).astype(int)
    df['place'] = (df['pos_num'].fillna(100) <= 3).astype(int)
    
    print(f"Loaded {len(df):,} rows from historical dataset.")
    
    # Load class_num from v17
    print("Loading class_num from v17...")
    v17_df = pd.read_parquet(v17_path, columns=['race_id', 'horse', 'class_num'])
    # Drop duplicates in v17 just in case
    v17_df = v17_df.drop_duplicates(subset=['race_id', 'horse'])
    df = df.merge(v17_df, on=['race_id', 'horse'], how='left')
    print("Class info joined.")
    
    # Pre-process bands
    print("Pre-processing feature bands...")
    
    # Distance bands
    def get_dist_band(dist_f):
        if pd.isna(dist_f): return "unknown"
        if dist_f < 5.5: return "5f"
        if dist_f < 6.5: return "6f"
        if dist_f < 7.5: return "7f"
        if dist_f < 8.5: return "8f"
        if dist_f < 10.5: return "9-10f"
        if dist_f < 12.5: return "11-12f"
        if dist_f < 14.5: return "13-14f"
        if dist_f < 17.5: return "15-17f"
        return "18f+"
    
    df['dist_band'] = df['dist_f'].apply(get_dist_band)
    
    # Going bands
    def get_going_band(going_code):
        if pd.isna(going_code): return "unknown"
        gc = str(going_code).lower()
        if '1' in gc or 'firm' in gc: return "Firm"
        if '2' in gc or 'good' in gc and 'soft' not in gc: return "Good"
        if '3' in gc or 'good to soft' in gc or 'yielding' in gc: return "GoodToSoft"
        if '4' in gc or 'soft' in gc: return "Soft"
        if '5' in gc or 'heavy' in gc: return "Heavy"
        if 'aw' in gc or 'all-weather' in gc: return "AW"
        return "unknown"
        
    df['going_band'] = df['going_code'].apply(get_going_band)
    
    # Class bands
    def get_class_band(class_num):
        if pd.isna(class_num): return "unknown"
        try:
            cn = int(float(class_num))
            if cn <= 2: return "G1-G2"
            if cn == 3: return "G3"
            if cn <= 5: return "Listed-Class1"
            if cn == 6: return "Class2"
            if cn == 7: return "Class3"
            return "Lower"
        except:
            return "unknown"
        
    df['class_band'] = df['class_num'].apply(get_class_band)
    
    # Define combo keys
    combos = {
        'tj': ['trainer', 'jockey'],
        'tc': ['trainer', 'course'],
        'td': ['trainer', 'dist_band'],
        'jc': ['jockey', 'course'],
        'jd': ['jockey', 'dist_band'],
        'tg': ['trainer', 'going_band'],
        'jg': ['jockey', 'going_band'],
        'th': ['trainer', 'class_band'],
        'tf': ['trainer']
    }
    
    windows = {
        'w14': '14D',
        'w30': '30D',
        'w90': '90D',
        'w365': '365D',
        'wltd': None
    }
    
    # Sort main df for potential alignment, but safer to join
    df = df.sort_values('date')
    
    print("Building rolling features...")
    
    # We will collect all feature dataframes and join at once
    feature_dfs = []

    for prefix, keys in combos.items():
        print(f"  Processing combo: {prefix} ({keys})")
        
        # Create a clean string key
        if len(keys) > 1:
            # Handle nulls explicitly before join
            temp_df = df[keys].fillna("null")
            df['temp_key'] = temp_df[keys[0]].astype(str) + "_" + temp_df[keys[1]].astype(str)
        else:
            df['temp_key'] = df[keys[0]].fillna("null").astype(str)
            
        # Group by key and date to get daily totals
        daily = df.groupby(['temp_key', 'date']).agg(
            daily_runs=('won', 'count'),
            daily_wins=('won', 'sum'),
            daily_places=('place', 'sum')
        ).reset_index()
        
        daily = daily.sort_values(['temp_key', 'date'])
        
        # Process windows on the 'daily' aggregated frame
        daily_feat_cols = []
        for w_name, w_offset in windows.items():
            print(f"    Window: {w_name}")
            
            if w_offset:
                # Time-based rolling
                daily_indexed = daily.set_index('date')
                group_roll = daily_indexed.groupby('temp_key')
                
                # sum of column in window ending at current date (inclusive)
                runs_sum = group_roll['daily_runs'].rolling(w_offset).sum().reset_index(0, drop=True)
                wins_sum = group_roll['daily_wins'].rolling(w_offset).sum().reset_index(0, drop=True)
                places_sum = group_roll['daily_places'].rolling(w_offset).sum().reset_index(0, drop=True)
                
                # Align sums back to daily
                # rolling() returns Series with original index (date)
                # But if there are duplicates in the index (which daily has because of temp_key), 
                # we need to be careful. reset_index(0, drop=True) removes temp_key from index.
                # The length should match len(daily).
                
                prior_runs = runs_sum.values - daily['daily_runs'].values
                prior_wins = wins_sum.values - daily['daily_wins'].values
                prior_places = places_sum.values - daily['daily_places'].values
            else:
                # LTD window
                group_roll = daily.groupby('temp_key')
                prior_runs = group_roll['daily_runs'].cumsum() - daily['daily_runs']
                prior_wins = group_roll['daily_wins'].cumsum() - daily['daily_wins']
                prior_places = group_roll['daily_places'].cumsum() - daily['daily_places']
                
            # Bayesian adjusted win rate: (wins + 2.0) / (runs + 20)
            # 2.0 comes from 0.10 * 20
            prior_runs_safe = np.maximum(prior_runs, 0)
            prior_wins_safe = np.maximum(prior_wins, 0)
            prior_places_safe = np.maximum(prior_places, 0)

            win_rate = np.where(prior_runs_safe > 0, prior_wins_safe / prior_runs_safe, 0.0)
            place_rate = np.where(prior_runs_safe > 0, prior_places_safe / prior_runs_safe, 0.0)
            adj_sr = (prior_wins_safe + 2.0) / (prior_runs_safe + 20)
            confidence = prior_runs_safe / (prior_runs_safe + 20)
            jtc_signal = adj_sr * confidence
            has_sample = (prior_runs_safe >= 5).astype(int)
            
            daily[f'{prefix}_runs_{w_name}'] = prior_runs_safe
            daily[f'{prefix}_wins_{w_name}'] = prior_wins_safe
            daily[f'{prefix}_places_{w_name}'] = prior_places_safe
            daily[f'{prefix}_win_rate_{w_name}'] = win_rate
            daily[f'{prefix}_place_rate_{w_name}'] = place_rate
            daily[f'{prefix}_adj_sr_{w_name}'] = adj_sr
            daily[f'{prefix}_confidence_{w_name}'] = confidence
            daily[f'{prefix}_jtc_signal_{w_name}'] = jtc_signal
            daily[f'{prefix}_has_sample_{w_name}'] = has_sample
            
            daily_feat_cols.extend([
                f'{prefix}_runs_{w_name}', f'{prefix}_wins_{w_name}', f'{prefix}_places_{w_name}',
                f'{prefix}_win_rate_{w_name}', f'{prefix}_place_rate_{w_name}',
                f'{prefix}_adj_sr_{w_name}', f'{prefix}_confidence_{w_name}',
                f'{prefix}_jtc_signal_{w_name}', f'{prefix}_has_sample_{w_name}'
            ])

        # Join these features to a temporary copy of the main df
        # This keeps the memory usage under control
        joined_feats = df[['temp_key', 'date']].merge(
            daily[['temp_key', 'date'] + daily_feat_cols],
            on=['temp_key', 'date'],
            how='left'
        ).drop(columns=['temp_key', 'date'])
        
        # Null out rows where any original key was null
        mask = df[keys].isnull().any(axis=1)
        joined_feats.loc[mask] = np.nan
        
        feature_dfs.append(joined_feats)

    print("Finalizing output dataset...")
    # Combine all feature dataframes
    out_df = pd.concat([df[['race_id', 'horse', 'date']].rename(columns={'date': 'as_of_date'})] + feature_dfs, axis=1)
    
    # Save output
    out_path = Path("data/new_build/sidecars/rolling_jtcd_v1.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)
    print(f"Saved {len(out_df):,} rows to {out_path}")
    
    # Generate Report
    print("Generating report...")
    report_dir = Path("data/new_build/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "row_count": len(out_df),
        "date_range": [str(out_df['as_of_date'].min()), str(out_df['as_of_date'].max())],
        "keys": {}
    }
    
    for prefix in combos.keys():
        sample_col = f"{prefix}_has_sample_w365"
        if sample_col in out_df.columns:
            ltd_runs = out_df[f"{prefix}_runs_wltd"]
            coverage = float(ltd_runs.gt(0).mean())
            sample_rate = float(out_df[sample_col].fillna(0).mean())
            stats["keys"][prefix] = {
                "ltd_coverage": coverage,
                "w365_has_sample_rate": sample_rate
            }
            
    with open(report_dir / "rolling_jtcd_v1_latest.json", 'w') as f:
        json.dump(stats, f, indent=2)
        
    with open(report_dir / "rolling_jtcd_v1_latest.md", 'w') as f:
        f.write("# Rolling JTC-D V1 Build Report\n\n")
        f.write(f"- **Rows Built:** {stats['row_count']:,}\n")
        f.write(f"- **Date Range:** {stats['date_range'][0]} to {stats['date_range'][1]}\n\n")
        f.write("## Coverage per Key (w365)\n")
        f.write("| Key | LTD Coverage | w365 Has Sample (n>=5) |\n")
        f.write("|-----|--------------|------------------------|\n")
        for k, v in stats["keys"].items():
            f.write(f"| {k} | {v['ltd_coverage']:.2%} | {v['w365_has_sample_rate']:.2%} |\n")

    print("Task 2 complete.")

if __name__ == "__main__":
    build_rolling_jtcd()
