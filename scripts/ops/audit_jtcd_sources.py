import pandas as pd
import json
from pathlib import Path
from datetime import datetime

FILES = [
    "data/raceform_clean.parquet",
    "data/raceform_v17_features.parquet",
    "data/new_build/training/core_v0_historical_dataset.parquet",
    "data/new_build/training/core_v0_or_train.parquet"
]

def audit_file(file_path):
    print(f"Auditing {file_path} ...")
    df = pd.read_parquet(file_path)
    
    # Basic info
    row_count = len(df)
    
    # Date handling
    date_col = None
    for col in ['date', 'race_date', 'datetime']:
        if col in df.columns:
            date_col = col
            break
            
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        min_date = df[date_col].min().strftime('%Y-%m-%d')
        max_date = df[date_col].max().strftime('%Y-%m-%d')
    else:
        min_date = max_date = "N/A"

    # Column mapping for required fields
    col_mapping = {
        'date': ['date', 'race_date'],
        'race_id': ['race_id', 'race_instance_uid'],
        'horse': ['horse', 'horse_name', 'horse_uid'],
        'trainer': ['trainer', 'trainer_name', 'trainer_uid'],
        'jockey': ['jockey', 'jockey_name', 'jockey_uid'],
        'course': ['course', 'course_name', 'course_uid'],
        'dist_f': ['dist_f', 'distance_furlongs'],
        'going_code': ['going_code', 'going_type_code'],
        'class': ['class', 'class_num', 'race_class'],
        'won': ['won', 'win_flag', 'position'],
        'field_size': ['field_size', 'runners_count']
    }
    
    presence = {}
    null_rates = {}
    unique_counts = {}
    
    found_cols = {}
    for key, options in col_mapping.items():
        found = False
        for opt in options:
            if opt in df.columns:
                presence[key] = opt
                found_cols[key] = opt
                found = True
                break
        if not found:
            presence[key] = None

    # Calculate null rates for specific keys
    for key in ['trainer', 'jockey', 'course', 'dist_f', 'going_code', 'won']:
        col = found_cols.get(key)
        if col:
            null_rates[key] = float(df[col].isnull().mean())
        else:
            null_rates[key] = 1.0

    # Calculate unique counts
    for key in ['trainer', 'jockey', 'course']:
        col = found_cols.get(key)
        if col:
            unique_counts[key] = int(df[col].nunique())
        else:
            unique_counts[key] = 0

    return {
        "file": file_path,
        "row_count": row_count,
        "date_range": [min_date, max_date],
        "columns": list(df.columns),
        "presence": presence,
        "null_rates": null_rates,
        "unique_counts": unique_counts
    }

def main():
    results = []
    for f in FILES:
        if Path(f).exists():
            results.append(audit_file(f))
        else:
            print(f"Skipping {f}, file not found.")

    # Write JSON
    out_dir = Path("data/new_build/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = out_dir / "rolling_jtcd_source_audit_latest.json"
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Write Markdown
    md_path = out_dir / "rolling_jtcd_source_audit_latest.md"
    with open(md_path, 'w') as f:
        f.write("# Rolling JTC-D Source Audit\n\n")
        for res in results:
            f.write(f"## {res['file']}\n")
            f.write(f"- **Rows:** {res['row_count']:,}\n")
            f.write(f"- **Date Range:** {res['date_range'][0]} to {res['date_range'][1]}\n")
            f.write("- **Presence:**\n")
            for k, v in res['presence'].items():
                f.write(f"  - {k}: {v}\n")
            f.write("- **Null Rates:**\n")
            for k, v in res['null_rates'].items():
                f.write(f"  - {k}: {v:.2%}\n")
            f.write("- **Unique Counts:**\n")
            for k, v in res['unique_counts'].items():
                f.write(f"  - {k}: {v:,}\n")
            f.write("\n")

    print(f"Audit complete. Reports written to {out_dir}")

if __name__ == "__main__":
    main()
