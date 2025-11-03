"""
VÉLØ v10.1 - Backtest Script
=============================

Backtest model on last 90 days out-of-sample.
Document failure modes without flinching.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import json

from src.training import FeatureStore, LabelCreator, ModelMetrics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_model(version: str = 'v1.0.0'):
    """Load trained model."""
    model_path = Path(f"/home/ubuntu/velo-oracle/out/models/{version}/model.pkl")
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    logger.info(f"Loaded model {version}")
    return model_data


def load_backtest_data(db_path: str, start_date: str, end_date: str):
    """Load backtest data from database."""
    logger.info(f"Loading backtest data: {start_date} to {end_date}")
    
    conn = sqlite3.connect(db_path)
    
    query = f"""
        SELECT * FROM racing_data 
        WHERE date >= '{start_date}'
        AND date <= '{end_date}'
        AND pos NOT IN ('PU', 'F', 'U', 'BD', 'RO', 'SU', 'UR')
        AND sp IS NOT NULL
        AND sp != ''
        LIMIT 100000
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    logger.info(f"Loaded {len(df):,} records")
    return df


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


def preprocess_data(df):
    """Preprocess backtest data."""
    logger.info("Preprocessing backtest data...")
    
    df['odds'] = df['sp'].apply(parse_sp_to_decimal)
    df['finish_position'] = pd.to_numeric(df['pos'], errors='coerce')
    
    df = df[df['odds'].notna() & df['finish_position'].notna()]
    df = df[df['odds'] >= 1.01]
    df = df[df['finish_position'] >= 1]
    
    df['field_size'] = df.groupby('race_id')['horse'].transform('count')
    
    logger.info(f"After preprocessing: {len(df):,} valid records")
    return df


def simulate_betting(predictions_df, strategy='top20', stake_per_bet=1.0):
    """
    Simulate betting strategy.
    
    Args:
        predictions_df: DataFrame with predictions and actual results
        strategy: 'top10', 'top20', 'top30', or 'all'
        stake_per_bet: Fixed stake per bet
    
    Returns:
        Dict with betting results
    """
    logger.info(f"Simulating {strategy} betting strategy...")
    
    # Select bets based on strategy
    if strategy == 'top10':
        threshold = predictions_df['win_prob'].quantile(0.90)
    elif strategy == 'top20':
        threshold = predictions_df['win_prob'].quantile(0.80)
    elif strategy == 'top30':
        threshold = predictions_df['win_prob'].quantile(0.70)
    else:  # all
        threshold = 0
    
    bets = predictions_df[predictions_df['win_prob'] >= threshold].copy()
    
    if len(bets) == 0:
        logger.warning("No bets selected!")
        return {'total_bets': 0}
    
    # Calculate returns
    bets['stake'] = stake_per_bet
    bets['won'] = (bets['finish_position'] == 1).astype(int)
    bets['return'] = bets['won'] * bets['odds'] * bets['stake']
    bets['profit'] = bets['return'] - bets['stake']
    
    # Aggregate results
    total_bets = len(bets)
    total_staked = bets['stake'].sum()
    total_return = bets['return'].sum()
    total_profit = bets['profit'].sum()
    wins = bets['won'].sum()
    win_rate = wins / total_bets if total_bets > 0 else 0
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
    
    # Drawdown
    bets = bets.sort_values('date')
    bets['cumulative_profit'] = bets['profit'].cumsum()
    bets['running_max'] = bets['cumulative_profit'].cummax()
    bets['drawdown'] = bets['running_max'] - bets['cumulative_profit']
    max_drawdown = bets['drawdown'].max()
    
    results = {
        'total_bets': total_bets,
        'total_staked': total_staked,
        'total_return': total_return,
        'total_profit': total_profit,
        'wins': wins,
        'win_rate': win_rate * 100,
        'roi': roi,
        'max_drawdown': max_drawdown,
        'avg_odds': bets['odds'].mean(),
        'bets_df': bets
    }
    
    return results


def analyze_failure_modes(bets_df):
    """Analyze where the model fails hardest."""
    logger.info("Analyzing failure modes...")
    
    losses = bets_df[bets_df['won'] == 0].copy()
    
    if len(losses) == 0:
        return {}
    
    # Worst losses by odds range
    losses['odds_band'] = pd.cut(losses['odds'], bins=[0, 3, 5, 10, 20, 100], 
                                   labels=['<3', '3-5', '5-10', '10-20', '20+'])
    
    failure_by_odds = losses.groupby('odds_band').agg({
        'profit': ['count', 'sum', 'mean']
    }).round(2)
    
    # Worst courses
    failure_by_course = losses.groupby('course').agg({
        'profit': ['count', 'sum']
    }).sort_values(('profit', 'sum')).head(10)
    
    # Worst race types
    failure_by_type = losses.groupby('type').agg({
        'profit': ['count', 'sum', 'mean']
    }).round(2)
    
    return {
        'by_odds': failure_by_odds,
        'by_course': failure_by_course,
        'by_type': failure_by_type
    }


def main():
    """Main backtest script."""
    logger.info("="*60)
    logger.info("VÉLØ v10.1 - BACKTEST")
    logger.info("="*60)
    
    # Paths
    project_dir = Path("/home/ubuntu/velo-oracle")
    db_path = project_dir / "velo_racing.db"
    
    # Load model
    model_data = load_model('v1.0.0')
    fund_model = model_data['fundamental_model']
    market_model = model_data.get('market_model')
    scaler = model_data.get('scaler')
    alpha = model_data['alpha']
    beta = model_data['beta']
    
    # Load backtest data (last 90 days from validation end)
    end_date = '2024-09-29'
    start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
    
    df = load_backtest_data(str(db_path), start_date, end_date)
    df = preprocess_data(df)
    
    # Feature engineering
    feature_store = FeatureStore(cache_dir="out/features")
    label_creator = LabelCreator(place_positions=3)
    
    logger.info("Computing features...")
    features_df = feature_store.compute_features(df)
    labels_df = label_creator.create_labels(features_df)
    
    # Make predictions
    logger.info("Making predictions...")
    feature_cols = model_data['feature_names']
    X = labels_df[feature_cols].fillna(0).values
    
    # Scale features if scaler exists
    if scaler is not None:
        X = scaler.transform(X)
    
    # Get fundamental predictions
    fund_probs = fund_model.predict_proba(X)[:, 1]
    
    # Get market probabilities
    market_probs = 1.0 / labels_df['odds'].values
    
    # Combine with alpha/beta (Benter's two-model approach)
    final_probs = alpha * fund_probs + beta * market_probs
    
    # Add predictions to dataframe
    labels_df['win_prob'] = final_probs
    labels_df['date'] = pd.to_datetime(labels_df['date'])
    
    # Simulate betting strategies
    logger.info("\n" + "="*60)
    logger.info("BACKTEST RESULTS")
    logger.info("="*60)
    
    strategies = ['top10', 'top20', 'top30', 'all']
    all_results = {}
    
    for strategy in strategies:
        results = simulate_betting(labels_df, strategy=strategy, stake_per_bet=1.0)
        all_results[strategy] = results
        
        if results['total_bets'] > 0:
            print(f"\n📊 {strategy.upper()} Strategy:")
            print(f"  Total Bets:    {results['total_bets']:,}")
            print(f"  Wins:          {results['wins']}")
            print(f"  Win Rate:      {results['win_rate']:.2f}%")
            print(f"  Total Staked:  £{results['total_staked']:.2f}")
            print(f"  Total Return:  £{results['total_return']:.2f}")
            print(f"  Profit/Loss:   £{results['total_profit']:.2f}")
            print(f"  ROI:           {results['roi']:.2f}%")
            print(f"  Max Drawdown:  £{results['max_drawdown']:.2f}")
            print(f"  Avg Odds:      {results['avg_odds']:.2f}")
    
    # Analyze failure modes for top20 strategy
    if all_results['top20']['total_bets'] > 0:
        logger.info("\n" + "="*60)
        logger.info("FAILURE MODE ANALYSIS (TOP20)")
        logger.info("="*60)
        
        failure_modes = analyze_failure_modes(all_results['top20']['bets_df'])
        
        if 'by_odds' in failure_modes and not failure_modes['by_odds'].empty:
            print("\n📉 Losses by Odds Band:")
            print(failure_modes['by_odds'])
        
        if 'by_type' in failure_modes and not failure_modes['by_type'].empty:
            print("\n📉 Losses by Race Type:")
            print(failure_modes['by_type'])
    
    # Save backtest report
    report_path = project_dir / "out/reports/backtest_v1.0.0.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'version': 'v1.0.0',
        'backtest_period': f"{start_date} to {end_date}",
        'total_races': len(labels_df['race_id'].unique()),
        'total_runners': len(labels_df),
        'strategies': {
            strategy: {
                'total_bets': results['total_bets'],
                'wins': results.get('wins', 0),
                'win_rate': results.get('win_rate', 0),
                'roi': results.get('roi', 0),
                'profit': results.get('total_profit', 0),
                'max_drawdown': results.get('max_drawdown', 0)
            }
            for strategy, results in all_results.items()
        }
    }
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"\n📄 Report saved: {report_path}")
    logger.info("\n" + "="*60)
    logger.info("BACKTEST COMPLETE")
    logger.info("="*60)


if __name__ == "__main__":
    main()
