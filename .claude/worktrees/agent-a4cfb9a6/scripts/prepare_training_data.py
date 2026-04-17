#!/usr/bin/env python3
"""
Prepare Training Data - Sample from raceform.csv

Creates a manageable subset for training while preserving temporal structure.

Usage:
    python scripts/prepare_training_data.py --rows 15000 --output data/train_sample.csv
"""

import pandas as pd
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Sample training data from raceform.csv')
    parser.add_argument('--input', type=str, default='/home/ubuntu/upload/raceform.csv',
                        help='Path to full raceform.csv')
    parser.add_argument('--output', type=str, default='/home/ubuntu/velo-oracle/data/train_sample.csv',
                        help='Path to output sample file')
    parser.add_argument('--rows', type=int, default=15000,
                        help='Number of rows to sample')
    parser.add_argument('--strategy', type=str, default='recent',
                        choices=['recent', 'random', 'chronological'],
                        help='Sampling strategy')
    
    args = parser.parse_args()
    
    print(f"Loading data from {args.input}...")
    print(f"Target: {args.rows:,} rows")
    
    # Read in chunks to avoid memory issues
    chunk_size = 50000
    chunks = []
    total_rows = 0
    
    for chunk in pd.read_csv(args.input, chunksize=chunk_size, low_memory=False):
        chunks.append(chunk)
        total_rows += len(chunk)
        print(f"  Loaded {total_rows:,} rows...", end='\r')
        
        # Stop if we have enough data
        if total_rows >= args.rows * 2:  # Load 2x to allow for sampling
            break
    
    print(f"\nLoaded {total_rows:,} rows total")
    
    # Combine chunks
    df = pd.concat(chunks, ignore_index=True)
    print(f"Combined shape: {df.shape}")
    
    # Convert date
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Sample based on strategy
    if args.strategy == 'recent':
        print(f"Sampling {args.rows:,} most recent rows...")
        df = df.sort_values('date', ascending=False).head(args.rows)
    elif args.strategy == 'chronological':
        print(f"Sampling first {args.rows:,} chronological rows...")
        df = df.sort_values('date').head(args.rows)
    else:  # random
        print(f"Sampling {args.rows:,} random rows...")
        df = df.sample(n=min(args.rows, len(df)), random_state=42)
    
    # Sort by date for training
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"Sample shape: {df.shape}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")
    print(f"   Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == '__main__':
    main()

