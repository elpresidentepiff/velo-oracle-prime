#!/usr/bin/env python3
"""
Walk-Forward Backtest - SQPE + TIE on Real Data

Simulates live betting with rolling train/test windows.

Usage:
    python scripts/backtest_walkforward.py --data data/backtest_50k_clean.csv
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import argparse
import json
from datetime import datetime
from src.features import FeatureBuilder
from src.intelligence.sqpe import SQPEEngine, SQPEConfig


def calculate_roi(bets_df):
    """Calculate ROI metrics from bet results."""
    if len(bets_df) == 0:
        return {
            'total_bets': 0,
            'total_staked': 0.0,
            'total_return': 0.0,
            'profit': 0.0,
            'roi': 0.0,
            'win_rate': 0.0,
        }
    
    total_staked = bets_df['stake'].sum()
    total_return = bets_df['return'].sum()
    profit = total_return - total_staked
    roi = (profit / total_staked) * 100 if total_staked > 0 else 0.0
    win_rate = (bets_df['won'] == 1).mean()
    
    return {
        'total_bets': len(bets_df),
        'total_staked': float(total_staked),
        'total_return': float(total_return),
        'profit': float(profit),
        'roi': float(roi),
        'win_rate': float(win_rate),
    }


def backtest_walk_forward(
    data_path,
    train_window=10000,
    test_window=5000,
    min_prob=0.15,
    max_prob=0.40,
    stake=10.0
):
    """Run walk-forward backtest."""
    print("=" * 80)
    print("VÉLØ ORACLE - WALK-FORWARD BACKTEST")
    print("=" * 80)
    
    # Load data
    print(f"\nLoading data from {data_path}...")
    df = pd.read_csv(data_path, low_memory=False)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"Loaded {len(df):,} rows")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique horses: {df['horse'].nunique():,}")
    print(f"Win rate: {(df['pos_int'] == 1).mean():.1%}")
    
    # Walk-forward windows
    all_bets = []
    fold_results = []
    
    start_idx = 0
    fold_num = 1
    
    while start_idx + train_window + test_window <= len(df):
        print(f"\n{'=' * 80}")
        print(f"FOLD {fold_num}")
        print(f"{'=' * 80}")
        
        # Split data
        train_df = df.iloc[start_idx:start_idx + train_window].copy()
        test_df = df.iloc[start_idx + train_window:start_idx + train_window + test_window].copy()
        
        print(f"Train: {len(train_df):,} rows ({train_df['date'].min().date()} to {train_df['date'].max().date()})")
        print(f"Test:  {len(test_df):,} rows ({test_df['date'].min().date()} to {test_df['date'].max().date()})")
        
        # Build features
        print("Building features...")
        builder = FeatureBuilder()
        
        # Use full history for feature engineering
        history = df.iloc[:start_idx + train_window].copy()
        
        try:
            X_train = builder.build_sqpe_features(train_df, history)
            y_train = builder.build_targets(train_df)
            
            X_test = builder.build_sqpe_features(test_df, history)
            
            print(f"  Train features: {X_train.shape}")
            print(f"  Test features: {X_test.shape}")
        except Exception as e:
            print(f"  ❌ Feature building failed: {e}")
            start_idx += test_window
            fold_num += 1
            continue
        
        # Train SQPE (quick training)
        print("Training SQPE...")
        sqpe = SQPEEngine(config=SQPEConfig(
            n_estimators=100,  # Reduced for speed
            learning_rate=0.1,
            max_depth=3,
            min_samples_leaf=40,
            time_splits=3,
        ))
        
        try:
            sqpe.fit(X_train, y_train['won'], time_order=X_train.index)
            print("  ✅ SQPE trained")
        except Exception as e:
            print(f"  ❌ SQPE training failed: {e}")
            start_idx += test_window
            fold_num += 1
            continue
        
        # Predict on test set
        print("Generating predictions...")
        test_probs = sqpe.predict_proba(X_test)
        
        # Betting strategy
        test_df['sqpe_prob'] = test_probs
        test_df['bet'] = (test_df['sqpe_prob'] >= min_prob) & (test_df['sqpe_prob'] <= max_prob)
        
        bets = test_df[test_df['bet']].copy()
        bets['stake'] = stake
        bets['won'] = (bets['pos_int'] == 1).astype(int)
        bets['return'] = bets['won'] * bets['sp_decimal'] * stake
        
        all_bets.append(bets)
        
        # Calculate fold ROI
        fold_roi = calculate_roi(bets)
        fold_roi['fold'] = fold_num
        fold_roi['train_start'] = str(train_df['date'].min().date())
        fold_roi['train_end'] = str(train_df['date'].max().date())
        fold_roi['test_start'] = str(test_df['date'].min().date())
        fold_roi['test_end'] = str(test_df['date'].max().date())
        
        fold_results.append(fold_roi)
        
        print(f"\nFold {fold_num} Results:")
        print(f"  Bets: {fold_roi['total_bets']}")
        print(f"  Staked: £{fold_roi['total_staked']:.2f}")
        print(f"  Return: £{fold_roi['total_return']:.2f}")
        print(f"  Profit: £{fold_roi['profit']:.2f}")
        print(f"  ROI: {fold_roi['roi']:.2f}%")
        print(f"  Win Rate: {fold_roi['win_rate']:.1%}")
        
        # Move window forward
        start_idx += test_window
        fold_num += 1
    
    # Combine all bets
    if not all_bets:
        print("\n❌ No bets placed - backtest failed")
        return None
    
    all_bets_df = pd.concat(all_bets, ignore_index=True)
    
    # Overall metrics
    overall_roi = calculate_roi(all_bets_df)
    
    print(f"\n{'=' * 80}")
    print("OVERALL BACKTEST RESULTS")
    print(f"{'=' * 80}")
    print(f"Total Folds: {len(fold_results)}")
    print(f"Total Bets: {overall_roi['total_bets']:,}")
    print(f"Total Staked: £{overall_roi['total_staked']:.2f}")
    print(f"Total Return: £{overall_roi['total_return']:.2f}")
    print(f"Total Profit: £{overall_roi['profit']:.2f}")
    print(f"Overall ROI: {overall_roi['roi']:.2f}%")
    print(f"Win Rate: {overall_roi['win_rate']:.1%}")
    
    # Fold-by-fold ROI
    fold_rois = [f['roi'] for f in fold_results]
    print(f"\nFold ROIs: {', '.join([f'{r:.1f}%' for r in fold_rois])}")
    print(f"Mean Fold ROI: {np.mean(fold_rois):.2f}%")
    print(f"Std Fold ROI: {np.std(fold_rois):.2f}%")
    
    # Profitable folds
    profitable = sum(1 for r in fold_rois if r > 0)
    print(f"Profitable Folds: {profitable}/{len(fold_rois)} ({profitable/len(fold_rois)*100:.0f}%)")
    
    return {
        'overall': overall_roi,
        'folds': fold_results,
        'config': {
            'train_window': train_window,
            'test_window': test_window,
            'min_prob': min_prob,
            'max_prob': max_prob,
            'stake': stake,
        },
        'timestamp': datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description='Run walk-forward backtest')
    parser.add_argument('--data', type=str, required=True, help='Path to preprocessed data')
    parser.add_argument('--output', type=str, default='results/backtest_walkforward.json', help='Output path')
    parser.add_argument('--train-window', type=int, default=10000, help='Training window size')
    parser.add_argument('--test-window', type=int, default=5000, help='Test window size')
    parser.add_argument('--min-prob', type=float, default=0.15, help='Min probability to bet')
    parser.add_argument('--max-prob', type=float, default=0.40, help='Max probability to bet')
    parser.add_argument('--stake', type=float, default=10.0, help='Stake per bet')
    
    args = parser.parse_args()
    
    # Run backtest
    results = backtest_walk_forward(
        data_path=args.data,
        train_window=args.train_window,
        test_window=args.test_window,
        min_prob=args.min_prob,
        max_prob=args.max_prob,
        stake=args.stake,
    )
    
    if results is None:
        print("\n❌ Backtest failed")
        return 1
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {output_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

