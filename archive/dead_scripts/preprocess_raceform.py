#!/usr/bin/env python3
"""
Preprocess Raceform Data

Converts raw raceform.csv columns to match VÉLØ schema.

Column mappings:
- pos → pos_int (convert to int, handle PU/F/etc)
- btn → btn_int (convert to float)
- or → or_int (convert to float)
- rpr → rpr_int (convert to float)
- ts → ts_int (convert to float)
- wgt → lbs (convert weight format to lbs)
- sp → sp_decimal (convert odds format)

Usage:
    python scripts/preprocess_raceform.py --input data/train_sample.csv --output data/train_sample_clean.csv
"""

import pandas as pd
import argparse
from pathlib import Path
import re


def parse_position(pos):
    """Convert position to integer, handling non-finishers."""
    if pd.isna(pos):
        return None
    
    pos_str = str(pos).strip().upper()
    
    # Non-finishers
    if pos_str in ['PU', 'F', 'U', 'BD', 'RO', 'SU', 'UR', 'RR', 'DSQ', 'CO']:
        return 99  # Assign large number for non-finishers
    
    # Extract numeric part
    match = re.match(r'(\d+)', pos_str)
    if match:
        return int(match.group(1))
    
    return None


def parse_beaten_distance(btn):
    """Convert beaten distance to float."""
    if pd.isna(btn):
        return None
    
    btn_str = str(btn).strip()
    
    # Handle special cases
    if btn_str in ['-', '']:
        return 0.0
    
    try:
        return float(btn_str)
    except:
        return None


def parse_weight(wgt):
    """Convert weight format to lbs."""
    if pd.isna(wgt):
        return None
    
    wgt_str = str(wgt).strip()
    
    # Format: "11-6" means 11 stone 6 pounds = 11*14 + 6 = 160 lbs
    match = re.match(r'(\d+)-(\d+)', wgt_str)
    if match:
        stone = int(match.group(1))
        pounds = int(match.group(2))
        return stone * 14 + pounds
    
    # Try direct conversion
    try:
        return float(wgt_str)
    except:
        return None


def parse_odds(sp):
    """Convert odds format to decimal."""
    if pd.isna(sp):
        return None
    
    sp_str = str(sp).strip().upper()
    
    # Remove 'F' suffix (favorite marker)
    sp_str = sp_str.replace('F', '')
    
    # Handle special cases
    if sp_str in ['', '-', 'EVENS', 'EVS']:
        return 2.0
    
    # Fractional odds: "5/2" → 2.5 + 1 = 3.5
    match = re.match(r'(\d+)/(\d+)', sp_str)
    if match:
        num = float(match.group(1))
        den = float(match.group(2))
        return (num / den) + 1.0
    
    # Direct decimal
    try:
        return float(sp_str)
    except:
        return None


def parse_distance(dist):
    """Convert distance format like '2m3½f' to yards."""
    if pd.isna(dist):
        return 2000  # Default
    
    dist_str = str(dist).strip()
    
    # Try direct numeric conversion first
    try:
        return int(float(dist_str))
    except:
        pass
    
    # Parse format like "2m3½f" (2 miles 3.5 furlongs)
    # 1 mile = 1760 yards, 1 furlong = 220 yards
    total_yards = 0
    
    # Extract miles
    miles_match = re.search(r'(\d+)m', dist_str)
    if miles_match:
        total_yards += int(miles_match.group(1)) * 1760
    
    # Extract furlongs (handle ½ as 0.5)
    furlongs_match = re.search(r'(\d+)([½¼¾])?f', dist_str)
    if furlongs_match:
        furlongs = int(furlongs_match.group(1))
        fraction = furlongs_match.group(2)
        if fraction == '½':
            furlongs += 0.5
        elif fraction == '¼':
            furlongs += 0.25
        elif fraction == '¾':
            furlongs += 0.75
        total_yards += int(furlongs * 220)
    
    return total_yards if total_yards > 0 else 2000


def parse_class(cls):
    """Extract numeric class from string like 'Class 4'."""
    if pd.isna(cls):
        return 4  # Default to class 4
    
    cls_str = str(cls).strip()
    
    # Extract number from "Class X" format
    match = re.search(r'(\d+)', cls_str)
    if match:
        return int(match.group(1))
    
    return 4  # Default


def preprocess_raceform(input_path, output_path):
    """Preprocess raceform data to match schema."""
    print(f"Loading {input_path}...")
    df = pd.read_csv(input_path, low_memory=False)
    print(f"Loaded {len(df):,} rows")
    
    print("\nPreprocessing columns...")
    
    # Class
    print("  - Parsing class")
    df['class'] = df['class'].apply(parse_class).astype(int)
    
    # Distance
    print("  - Parsing dist")
    df['dist'] = df['dist'].apply(parse_distance).astype(int)
    
    # Age
    print("  - Converting age")
    df['age'] = pd.to_numeric(df['age'], errors='coerce').fillna(5).astype(int)
    
    # Position
    print("  - Converting pos → pos_int")
    df['pos_int'] = df['pos'].apply(parse_position)
    
    # Beaten distance
    print("  - Converting btn → btn_int")
    df['btn_int'] = df['btn'].apply(parse_beaten_distance)
    
    # Ratings
    print("  - Converting or → or_int")
    df['or_int'] = pd.to_numeric(df['or'], errors='coerce')
    
    print("  - Converting rpr → rpr_int")
    df['rpr_int'] = pd.to_numeric(df['rpr'], errors='coerce')
    
    print("  - Converting ts → ts_int")
    df['ts_int'] = pd.to_numeric(df['ts'], errors='coerce')
    
    # Weight
    print("  - Converting wgt → lbs")
    df['lbs'] = df['wgt'].apply(parse_weight)
    
    # Odds
    print("  - Converting sp → sp_decimal")
    df['sp_decimal'] = df['sp'].apply(parse_odds)
    
    # Filter out rows with no position
    print("\nFiltering invalid rows...")
    before = len(df)
    df = df[df['pos_int'].notna()].copy()
    after = len(df)
    print(f"  Removed {before - after:,} rows with invalid positions")
    
    # Basic stats
    print("\nData summary:")
    print(f"  Total rows: {len(df):,}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Unique horses: {df['horse'].nunique():,}")
    print(f"  Unique trainers: {df['trainer'].nunique():,}")
    print(f"  Win rate: {(df['pos_int'] == 1).mean():.1%}")
    
    # Save
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")
    print(f"   Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description='Preprocess raceform data')
    parser.add_argument('--input', type=str, required=True, help='Input CSV path')
    parser.add_argument('--output', type=str, required=True, help='Output CSV path')
    
    args = parser.parse_args()
    
    preprocess_raceform(args.input, args.output)


if __name__ == '__main__':
    main()

