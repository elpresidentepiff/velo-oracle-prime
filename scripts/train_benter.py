"""
VÉLØ v10.1 - Benter Model Training
Optimize α and β weights using historical data

This script:
1. Loads historical race data from CSV
2. Calculates fundamental and public probabilities
3. Performs grid search to find optimal α, β
4. Minimizes log loss on training data
5. Validates on holdout set
6. Saves trained model weights
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss
import sys
import os
from datetime import datetime
import json
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.settings import settings
from src.core import log
import logging

# Setup logging
log.setup_logging("config/logging.json")
logger = logging.getLogger("velo.train")


def parse_odds(sp_str):
    """Parse starting price to decimal odds"""
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
    """Parse rating to integer"""
    if pd.isna(rating_str) or rating_str == '–':
        return None
    try:
        return int(rating_str)
    except:
        return None


def load_and_prepare_data(filepath, start_date=None, end_date=None, sample_size=None):
    """
    Load race data from CSV and prepare for training
    
    Args:
        filepath: Path to raceform.csv
        start_date: Start date filter (YYYY-MM-DD)
        end_date: End date filter (YYYY-MM-DD)
        sample_size: Number of rows to sample (for testing)
    
    Returns:
        DataFrame with cleaned data
    """
    logger.info(f"Loading data from {filepath}...")
    
    # Load data
    if sample_size:
        logger.info(f"Sampling {sample_size} rows for testing...")
        df = pd.read_csv(filepath, nrows=sample_size, low_memory=False)
    else:
        df = pd.read_csv(filepath, low_memory=False)
    
    logger.info(f"Loaded {len(df)} rows")
    
    # Parse dates
    df['date'] = pd.to_datetime(df['date'])
    
    # Filter by date range
    if start_date:
        df = df[df['date'] >= start_date]
        logger.info(f"Filtered to >= {start_date}: {len(df)} rows")
    
    if end_date:
        df = df[df['date'] <= end_date]
        logger.info(f"Filtered to <= {end_date}: {len(df)} rows")
    
    # Parse odds and ratings
    logger.info("Parsing odds and ratings...")
    df['sp_decimal'] = df['sp'].apply(parse_odds)
    df['or_int'] = df['or'].apply(parse_rating)
    df['rpr_int'] = df['rpr'].apply(parse_rating)
    df['ts_int'] = df['ts'].apply(parse_rating)
    
    # Parse position
    df['pos_int'] = df['pos'].apply(lambda x: int(float(x)) if pd.notna(x) and str(x).replace('.','').isdigit() else None)
    df['is_winner'] = (df['pos_int'] == 1).astype(int)
    
    # Filter: must have odds and at least one rating
    df = df[df['sp_decimal'].notna()]
    df = df[(df['or_int'].notna()) | (df['rpr_int'].notna()) | (df['ts_int'].notna())]
    df = df[df['pos_int'].notna()]
    
    logger.info(f"After filtering: {len(df)} rows")
    
    # Calculate public probability (market-implied)
    df['p_public'] = 1.0 / df['sp_decimal']
    
    # Normalize public probabilities by race (handle overround)
    logger.info("Normalizing public probabilities...")
    df['p_public_norm'] = df.groupby(['date', 'course', 'race_id'])['p_public'].transform(
        lambda x: x / x.sum()
    )
    
    return df


def calculate_fundamental_probability(row):
    """
    Calculate fundamental probability from ratings
    
    Uses average of available ratings (OR, RPR, TS)
    Higher rating = higher probability
    """
    ratings = []
    if pd.notna(row['or_int']):
        ratings.append(row['or_int'])
    if pd.notna(row['rpr_int']):
        ratings.append(row['rpr_int'])
    if pd.notna(row['ts_int']):
        ratings.append(row['ts_int'])
    
    if not ratings:
        return None
    
    # Average rating
    avg_rating = np.mean(ratings)
    
    # Store for normalization
    return avg_rating


def normalize_fundamental_probabilities(df):
    """
    Convert ratings to probabilities and normalize by race
    
    Uses softmax-like transformation
    """
    logger.info("Calculating fundamental probabilities...")
    
    # Calculate raw ratings
    df['rating_avg'] = df.apply(calculate_fundamental_probability, axis=1)
    
    # Filter out rows without ratings
    df = df[df['rating_avg'].notna()].copy()
    
    # Convert ratings to probabilities using softmax within each race
    def softmax_race(group):
        ratings = group['rating_avg'].values
        # Scale ratings (higher is better)
        exp_ratings = np.exp(ratings / 20.0)  # Temperature = 20
        probs = exp_ratings / exp_ratings.sum()
        return pd.Series(probs, index=group.index)
    
    df['p_fundamental'] = df.groupby(['date', 'course', 'race_id']).apply(softmax_race).reset_index(level=[0,1,2], drop=True)
    
    logger.info(f"Fundamental probabilities calculated for {len(df)} rows")
    
    return df


def combine_probabilities(df, alpha, beta):
    """
    Combine fundamental and public probabilities using Benter's formula
    
    p_model = α * p_fundamental + β * p_public
    
    Then normalize to sum to 1 within each race
    """
    # Combine
    df['p_model_raw'] = alpha * df['p_fundamental'] + beta * df['p_public_norm']
    
    # Normalize by race
    df['p_model'] = df.groupby(['date', 'course', 'race_id'])['p_model_raw'].transform(
        lambda x: x / x.sum()
    )
    
    return df


def evaluate_model(df, alpha, beta):
    """
    Evaluate model performance using log loss
    
    Lower log loss = better calibration
    """
    # Combine probabilities
    df_eval = combine_probabilities(df.copy(), alpha, beta)
    
    # Calculate log loss
    # Clip probabilities to avoid log(0)
    p_model_clipped = np.clip(df_eval['p_model'].values, 1e-15, 1 - 1e-15)
    
    loss = log_loss(df_eval['is_winner'].values, p_model_clipped)
    
    return loss


def grid_search(df, alpha_range, beta_range):
    """
    Grid search to find optimal α and β
    
    Args:
        df: Training data
        alpha_range: List of α values to try
        beta_range: List of β values to try
    
    Returns:
        best_alpha, best_beta, best_loss, results_df
    """
    logger.info(f"Starting grid search: {len(alpha_range)} alphas × {len(beta_range)} betas = {len(alpha_range) * len(beta_range)} combinations")
    
    results = []
    best_loss = float('inf')
    best_alpha = None
    best_beta = None
    
    total = len(alpha_range) * len(beta_range)
    count = 0
    
    for alpha in alpha_range:
        for beta in beta_range:
            count += 1
            
            # Evaluate
            loss = evaluate_model(df, alpha, beta)
            
            results.append({
                'alpha': alpha,
                'beta': beta,
                'log_loss': loss
            })
            
            if loss < best_loss:
                best_loss = loss
                best_alpha = alpha
                best_beta = beta
                logger.info(f"[{count}/{total}] New best: α={alpha:.2f}, β={beta:.2f}, loss={loss:.6f}")
            elif count % 10 == 0:
                logger.info(f"[{count}/{total}] α={alpha:.2f}, β={beta:.2f}, loss={loss:.6f}")
    
    results_df = pd.DataFrame(results)
    
    logger.info(f"✅ Grid search complete!")
    logger.info(f"Best: α={best_alpha:.2f}, β={best_beta:.2f}, loss={best_loss:.6f}")
    
    return best_alpha, best_beta, best_loss, results_df


def main():
    parser = argparse.ArgumentParser(description='Train Benter model')
    parser.add_argument('--filepath', default='/home/ubuntu/upload/raceform.csv', help='Path to raceform.csv')
    parser.add_argument('--train-start', default='2015-01-01', help='Training start date')
    parser.add_argument('--train-end', default='2023-12-31', help='Training end date')
    parser.add_argument('--val-start', default='2024-01-01', help='Validation start date')
    parser.add_argument('--val-end', default='2024-12-31', help='Validation end date')
    parser.add_argument('--sample', type=int, help='Sample size for testing (optional)')
    parser.add_argument('--alpha-min', type=float, default=0.5, help='Min alpha')
    parser.add_argument('--alpha-max', type=float, default=1.5, help='Max alpha')
    parser.add_argument('--alpha-step', type=float, default=0.1, help='Alpha step')
    parser.add_argument('--beta-min', type=float, default=0.5, help='Min beta')
    parser.add_argument('--beta-max', type=float, default=1.5, help='Max beta')
    parser.add_argument('--beta-step', type=float, default=0.1, help='Beta step')
    parser.add_argument('--output', default='models/benter_weights.json', help='Output file for weights')
    
    args = parser.parse_args()
    
    with log.EventLogger("train_benter", filepath=args.filepath):
        # Load training data
        logger.info("=== LOADING TRAINING DATA ===")
        train_df = load_and_prepare_data(
            args.filepath,
            start_date=args.train_start,
            end_date=args.train_end,
            sample_size=args.sample
        )
        
        # Calculate fundamental probabilities
        train_df = normalize_fundamental_probabilities(train_df)
        
        logger.info(f"Training data: {len(train_df)} rows, {train_df['race_id'].nunique()} races")
        
        # Grid search
        logger.info("=== GRID SEARCH ===")
        alpha_range = np.arange(args.alpha_min, args.alpha_max + args.alpha_step, args.alpha_step)
        beta_range = np.arange(args.beta_min, args.beta_max + args.alpha_step, args.beta_step)
        
        best_alpha, best_beta, best_loss, results_df = grid_search(train_df, alpha_range, beta_range)
        
        # Validate on holdout set
        logger.info("=== VALIDATION ===")
        val_df = load_and_prepare_data(
            args.filepath,
            start_date=args.val_start,
            end_date=args.val_end
        )
        val_df = normalize_fundamental_probabilities(val_df)
        
        val_loss = evaluate_model(val_df, best_alpha, best_beta)
        
        logger.info(f"Validation data: {len(val_df)} rows, {val_df['race_id'].nunique()} races")
        logger.info(f"Validation loss: {val_loss:.6f}")
        
        # Save results
        logger.info("=== SAVING RESULTS ===")
        
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
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
        
        logger.info(f"✅ Weights saved to {args.output}")
        
        # Save grid search results
        results_csv = args.output.replace('.json', '_grid_search.csv')
        results_df.to_csv(results_csv, index=False)
        logger.info(f"✅ Grid search results saved to {results_csv}")
        
        # Print summary
        print("\n" + "="*60)
        print("🎉 TRAINING COMPLETE")
        print("="*60)
        print(f"Best α: {best_alpha:.2f}")
        print(f"Best β: {best_beta:.2f}")
        print(f"Training loss: {best_loss:.6f}")
        print(f"Validation loss: {val_loss:.6f}")
        print(f"Weights saved to: {args.output}")
        print("="*60)


if __name__ == "__main__":
    main()

