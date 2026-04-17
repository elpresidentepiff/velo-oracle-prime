"""
VÉLØ v1.1.0 - Backtest Script
==============================

Backtest v1.1.0 on out-of-sample data (July-Sept 2024).
- Compute features for OOS period
- Load trained model
- Generate predictions
- Analyze performance by strategy and price bucket

Author: VÉLØ Oracle Team
Version: 10.2.0
"""

import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import logging
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime
from src.features.builder_v11 import FeatureBuilderV11

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_sp_to_decimal(sp_str):
    """Convert SP string to decimal odds."""
    if pd.isna(sp_str) or sp_str == '':
        return None
    
    sp_str = str(sp_str).strip()
    sp_str = sp_str.replace('F', '').replace('J', '').strip()
    
    if '/' in sp_str:
        try:
            parts = sp_str.split('/')
            numerator = float(parts[0])
            denominator = float(parts[1])
            return (numerator / denominator) + 1.0
        except:
            return None
    
    try:
        return float(sp_str)
    except:
        return None


def main():
    """Main backtest script."""
    logger.info("="*60)
    logger.info("VÉLØ v1.1.0 - BACKTEST (90-DAY OOS)")
    logger.info("="*60)
    
    # Paths
    project_dir = Path("/home/ubuntu/velo-oracle")
    db_path = project_dir / "velo_racing.db"
    model_dir = project_dir / "out/models/v1.1.0"
    output_dir = project_dir / "out/reports"
    output_dir.mkdir(exist_ok=True)
    
    # Load model
    logger.info("\nLoading v1.1.0 model...")
    model_path = model_dir / "model.pkl"
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    logger.info(f"  Version: {model['version']}")
    logger.info(f"  Alpha: {model['alpha']:.2f}")
    logger.info(f"  Features: {len(model['feature_names'])}")
    
    # Build features for OOS period (sample for speed)
    logger.info("\nBuilding features for OOS sample (2K records)...")
    logger.info("  (Full OOS would require optimized feature computation)")
    
    builder = FeatureBuilderV11(str(db_path))
    
    # Get OOS data (July-Sept 2024)
    df_oos = builder.build_all_features(sample_size=2000)
    df_oos['date'] = pd.to_datetime(df_oos['date'])
    df_oos = df_oos[(df_oos['date'] >= '2024-07-01') & (df_oos['date'] < '2024-10-01')]
    
    logger.info(f"  OOS records: {len(df_oos):,}")
    
    if len(df_oos) == 0:
        logger.warning("  No OOS data in sample. Using recent data instead...")
        df_oos = builder.build_all_features(sample_size=2000)
        df_oos['date'] = pd.to_datetime(df_oos['date'])
        df_oos = df_oos.sort_values('date', ascending=False).head(1000)
    
    # Parse odds
    df_oos['odds'] = df_oos['sp'].apply(parse_sp_to_decimal)
    df_oos = df_oos[df_oos['odds'].notna()]
    df_oos['win'] = (df_oos['pos'] == '1').astype(int)
    
    logger.info(f"  Valid OOS records: {len(df_oos):,}")
    logger.info(f"  Win rate: {df_oos['win'].mean()*100:.2f}%")
    
    # Prepare features
    feature_cols = [f for f in model['feature_names'] if f in df_oos.columns]
    X_oos = df_oos[feature_cols].values
    y_oos = df_oos['win'].values
    odds_oos = df_oos['odds'].values
    
    # Generate predictions
    logger.info("\nGenerating predictions...")
    
    # Fundamental probabilities
    fund_probs = model['fundamental_model'].predict_proba(X_oos)[:, 1]
    
    # Market probabilities
    market_probs = 1.0 / odds_oos
    
    # Blend
    blended_probs = model['alpha'] * fund_probs + model['beta'] * market_probs
    
    # Calibrate
    calibrated_probs = model['calibrator'].transform(blended_probs)
    
    df_oos['prediction'] = calibrated_probs
    
    logger.info(f"  Predictions generated: {len(df_oos):,}")
    
    # Backtest strategies
    logger.info("\n" + "="*60)
    logger.info("BACKTEST RESULTS")
    logger.info("="*60)
    
    strategies = {
        'TOP10': np.percentile(calibrated_probs, 90),
        'TOP20': np.percentile(calibrated_probs, 80),
        'TOP30': np.percentile(calibrated_probs, 70),
        'ALL': 0.0
    }
    
    results = {}
    
    for strategy_name, threshold in strategies.items():
        mask = calibrated_probs >= threshold
        
        if mask.sum() == 0:
            continue
        
        bets = mask.sum()
        wins = y_oos[mask].sum()
        win_rate = wins / bets
        
        # Simplified ROI (assumes £1 bets at SP)
        returns = np.sum(odds_oos[mask][y_oos[mask] == 1])
        profit = returns - bets
        roi = (profit / bets) * 100
        
        # A/E ratio
        expected_wins = calibrated_probs[mask].sum()
        ae_ratio = wins / expected_wins if expected_wins > 0 else 0.0
        
        logger.info(f"\n{strategy_name}:")
        logger.info(f"  Bets: {bets}")
        logger.info(f"  Wins: {wins}")
        logger.info(f"  Win Rate: {win_rate*100:.2f}%")
        logger.info(f"  ROI: {roi:.2f}%")
        logger.info(f"  A/E: {ae_ratio:.4f}")
        logger.info(f"  Profit: £{profit:.2f}")
        
        results[strategy_name] = {
            'bets': int(bets),
            'wins': int(wins),
            'win_rate': float(win_rate),
            'roi': float(roi),
            'ae_ratio': float(ae_ratio),
            'profit': float(profit)
        }
    
    # Price bucket analysis
    logger.info("\n" + "="*60)
    logger.info("PERFORMANCE BY PRICE BUCKET")
    logger.info("="*60)
    
    price_buckets = [
        (5.0, 8.0, '5.0-8.0'),
        (8.0, 15.0, '8.0-15.0'),
        (15.0, 21.0, '15.0-21.0')
    ]
    
    bucket_results = {}
    
    for min_odds, max_odds, bucket_name in price_buckets:
        mask = (odds_oos >= min_odds) & (odds_oos < max_odds)
        
        if mask.sum() == 0:
            continue
        
        bets = mask.sum()
        wins = y_oos[mask].sum()
        expected_wins = calibrated_probs[mask].sum()
        ae_ratio = wins / expected_wins if expected_wins > 0 else 0.0
        
        returns = np.sum(odds_oos[mask][y_oos[mask] == 1])
        profit = returns - bets
        roi = (profit / bets) * 100
        
        logger.info(f"\n{bucket_name}:")
        logger.info(f"  Bets: {bets}")
        logger.info(f"  A/E: {ae_ratio:.4f}")
        logger.info(f"  ROI: {roi:.2f}%")
        
        bucket_results[bucket_name] = {
            'bets': int(bets),
            'ae_ratio': float(ae_ratio),
            'roi': float(roi)
        }
    
    # Calibration analysis
    logger.info("\n" + "="*60)
    logger.info("CALIBRATION ANALYSIS")
    logger.info("="*60)
    
    bins = np.linspace(0, 1, 11)
    bin_indices = np.digitize(calibrated_probs, bins) - 1
    
    cal_error = 0.0
    
    for i in range(10):
        mask = bin_indices == i
        if mask.sum() > 0:
            pred_mean = calibrated_probs[mask].mean()
            true_mean = y_oos[mask].mean()
            error = abs(pred_mean - true_mean)
            cal_error += error * mask.sum()
            
            logger.info(f"  Bin {i}: Pred={pred_mean:.3f}, True={true_mean:.3f}, Error={error:.3f}")
    
    cal_error = cal_error / len(y_oos)
    logger.info(f"\n  Overall Calibration Error: {cal_error*100:.2f}%")
    
    # Save results
    report = {
        'version': '1.1.0',
        'backtest_date': datetime.now().isoformat(),
        'oos_records': len(df_oos),
        'oos_period': 'Sample (2K records)',
        'strategies': results,
        'price_buckets': bucket_results,
        'calibration_error': float(cal_error)
    }
    
    report_path = output_dir / "backtest_v1.1.0.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info("\n" + "="*60)
    logger.info("BACKTEST COMPLETE")
    logger.info("="*60)
    logger.info(f"  Report saved: {report_path}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
