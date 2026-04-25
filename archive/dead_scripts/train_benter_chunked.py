"""
VÉLØ v10.1 - Memory-Efficient Benter Training
Process data in chunks to avoid memory issues

Strategy:
1. Sample 100k rows from training period for grid search
2. Find optimal α, β on sample
3. Validate on separate holdout sample
4. Save weights
"""

import pandas as pd
import numpy as np
from sklearn.metrics import log_loss
import sys
import os
from datetime import datetime
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.settings import settings
from src.core import log
import logging

log.setup_logging("config/logging.json")
logger = logging.getLogger("velo.train")


def parse_odds(sp_str):
    """Parse SP to decimal"""
    if pd.isna(sp_str) or sp_str == '–':
        return None
    sp_str = str(sp_str).strip().replace('F', '').strip()
    if sp_str.lower() == 'evens':
        return 2.0
    if '/' in sp_str:
        try:
            parts = sp_str.split('/')
            return (float(parts[0]) / float(parts[1])) + 1.0
        except:
            return None
    try:
        return float(sp_str)
    except:
        return None


def parse_rating(rating_str):
    """Parse rating"""
    if pd.isna(rating_str) or rating_str == '–':
        return None
    try:
        return int(rating_str)
    except:
        return None


def load_sample(filepath, start_date, end_date, sample_size=100000):
    """Load random sample from date range"""
    logger.info(f"Loading {sample_size} row sample from {start_date} to {end_date}...")
    
    # Count total rows in range (quick scan)
    logger.info("Scanning file...")
    row_count = 0
    target_rows = []
    
    for i, chunk in enumerate(pd.read_csv(filepath, chunksize=50000, low_memory=False)):
        chunk['date'] = pd.to_datetime(chunk['date'])
        chunk_in_range = chunk[(chunk['date'] >= start_date) & (chunk['date'] <= end_date)]
        
        if len(chunk_in_range) > 0:
            # Store chunk indices
            target_rows.extend(chunk_in_range.index.tolist())
            row_count += len(chunk_in_range)
        
        if i % 10 == 0:
            logger.info(f"Scanned {(i+1)*50000} rows, found {row_count} in range...")
    
    logger.info(f"Found {row_count} rows in date range")
    
    # Sample indices
    if row_count > sample_size:
        sample_indices = np.random.choice(target_rows, sample_size, replace=False)
        logger.info(f"Sampling {sample_size} rows...")
    else:
        sample_indices = target_rows
        logger.info(f"Using all {row_count} rows (less than sample size)")
    
    # Load sampled rows
    logger.info("Loading sampled data...")
    df = pd.read_csv(filepath, low_memory=False)
    df = df.loc[sample_indices].copy()
    
    # Parse
    df['date'] = pd.to_datetime(df['date'])
    df['sp_decimal'] = df['sp'].apply(parse_odds)
    df['or_int'] = df['or'].apply(parse_rating)
    df['rpr_int'] = df['rpr'].apply(parse_rating)
    df['ts_int'] = df['ts'].apply(parse_rating)
    df['pos_int'] = df['pos'].apply(lambda x: int(float(x)) if pd.notna(x) and str(x).replace('.','').isdigit() else None)
    df['is_winner'] = (df['pos_int'] == 1).astype(int)
    
    # Filter
    df = df[df['sp_decimal'].notna()]
    df = df[(df['or_int'].notna()) | (df['rpr_int'].notna()) | (df['ts_int'].notna())]
    df = df[df['pos_int'].notna()]
    
    logger.info(f"After filtering: {len(df)} rows, {df['race_id'].nunique()} races")
    
    # Public probability
    df['p_public'] = 1.0 / df['sp_decimal']
    df['p_public_norm'] = df.groupby(['date', 'course', 'race_id'])['p_public'].transform(
        lambda x: x / x.sum()
    )
    
    return df


def calculate_fundamental(row):
    """Calc fundamental from ratings"""
    ratings = []
    if pd.notna(row['or_int']):
        ratings.append(row['or_int'])
    if pd.notna(row['rpr_int']):
        ratings.append(row['rpr_int'])
    if pd.notna(row['ts_int']):
        ratings.append(row['ts_int'])
    return np.mean(ratings) if ratings else None


def normalize_fundamental(df):
    """Convert ratings to probabilities"""
    logger.info("Calculating fundamental probabilities...")
    
    df['rating_avg'] = df.apply(calculate_fundamental, axis=1)
    df = df[df['rating_avg'].notna()].copy()
    
    def softmax_race(group):
        ratings = group['rating_avg'].values
        exp_ratings = np.exp(ratings / 20.0)
        return pd.Series(exp_ratings / exp_ratings.sum(), index=group.index)
    
    df['p_fundamental'] = df.groupby(['date', 'course', 'race_id']).apply(softmax_race).reset_index(level=[0,1,2], drop=True)
    
    return df


def combine_probs(df, alpha, beta):
    """Combine with Benter formula"""
    df['p_model_raw'] = alpha * df['p_fundamental'] + beta * df['p_public_norm']
    df['p_model'] = df.groupby(['date', 'course', 'race_id'])['p_model_raw'].transform(
        lambda x: x / x.sum()
    )
    return df


def evaluate(df, alpha, beta):
    """Evaluate with log loss"""
    df_eval = combine_probs(df.copy(), alpha, beta)
    p_clipped = np.clip(df_eval['p_model'].values, 1e-15, 1 - 1e-15)
    return log_loss(df_eval['is_winner'].values, p_clipped)


def grid_search(df, alpha_range, beta_range):
    """Grid search"""
    logger.info(f"Grid search: {len(alpha_range)} × {len(beta_range)} = {len(alpha_range) * len(beta_range)} combinations")
    
    results = []
    best_loss = float('inf')
    best_alpha = None
    best_beta = None
    
    total = len(alpha_range) * len(beta_range)
    count = 0
    
    for alpha in alpha_range:
        for beta in beta_range:
            count += 1
            loss = evaluate(df, alpha, beta)
            results.append({'alpha': alpha, 'beta': beta, 'log_loss': loss})
            
            if loss < best_loss:
                best_loss = loss
                best_alpha = alpha
                best_beta = beta
                logger.info(f"[{count}/{total}] New best: α={alpha:.2f}, β={beta:.2f}, loss={loss:.6f}")
            elif count % 10 == 0:
                logger.info(f"[{count}/{total}] α={alpha:.2f}, β={beta:.2f}, loss={loss:.6f}")
    
    logger.info(f"✅ Best: α={best_alpha:.2f}, β={best_beta:.2f}, loss={best_loss:.6f}")
    
    return best_alpha, best_beta, best_loss, pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser(description='Train Benter (memory-efficient)')
    parser.add_argument('--filepath', default='/home/ubuntu/upload/raceform.csv')
    parser.add_argument('--train-start', default='2015-01-01')
    parser.add_argument('--train-end', default='2023-12-31')
    parser.add_argument('--val-start', default='2024-01-01')
    parser.add_argument('--val-end', default='2024-12-31')
    parser.add_argument('--train-sample', type=int, default=100000, help='Training sample size')
    parser.add_argument('--val-sample', type=int, default=50000, help='Validation sample size')
    parser.add_argument('--alpha-min', type=float, default=0.5)
    parser.add_argument('--alpha-max', type=float, default=1.5)
    parser.add_argument('--alpha-step', type=float, default=0.1)
    parser.add_argument('--beta-min', type=float, default=0.5)
    parser.add_argument('--beta-max', type=float, default=1.5)
    parser.add_argument('--beta-step', type=float, default=0.1)
    parser.add_argument('--output', default='models/benter_weights.json')
    
    args = parser.parse_args()
    
    with log.EventLogger("train_benter_chunked", filepath=args.filepath):
        # Load training sample
        logger.info("=== LOADING TRAINING SAMPLE ===")
        train_df = load_sample(args.filepath, args.train_start, args.train_end, args.train_sample)
        train_df = normalize_fundamental(train_df)
        
        # Grid search
        logger.info("=== GRID SEARCH ===")
        alpha_range = np.arange(args.alpha_min, args.alpha_max + args.alpha_step, args.alpha_step)
        beta_range = np.arange(args.beta_min, args.beta_max + args.beta_step, args.beta_step)
        
        best_alpha, best_beta, best_loss, results_df = grid_search(train_df, alpha_range, beta_range)
        
        # Validate
        logger.info("=== VALIDATION ===")
        val_df = load_sample(args.filepath, args.val_start, args.val_end, args.val_sample)
        val_df = normalize_fundamental(val_df)
        val_loss = evaluate(val_df, best_alpha, best_beta)
        
        logger.info(f"Validation loss: {val_loss:.6f}")
        
        # Save
        logger.info("=== SAVING ===")
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
        
        weights = {
            'alpha': float(best_alpha),
            'beta': float(best_beta),
            'train_loss': float(best_loss),
            'val_loss': float(val_loss),
            'train_start': args.train_start,
            'train_end': args.train_end,
            'val_start': args.val_start,
            'val_end': args.val_end,
            'train_rows': len(train_df),
            'val_rows': len(val_df),
            'trained_at': datetime.now().isoformat()
        }
        
        with open(args.output, 'w') as f:
            json.dump(weights, f, indent=2)
        
        results_df.to_csv(args.output.replace('.json', '_grid.csv'), index=False)
        
        print("\n" + "="*60)
        print("🎉 TRAINING COMPLETE")
        print("="*60)
        print(f"Best α: {best_alpha:.2f}")
        print(f"Best β: {best_beta:.2f}")
        print(f"Training loss: {best_loss:.6f}")
        print(f"Validation loss: {val_loss:.6f}")
        print(f"Saved to: {args.output}")
        print("="*60)


if __name__ == "__main__":
    main()

