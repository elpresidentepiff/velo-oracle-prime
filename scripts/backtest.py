"""
VÉLØ v10.1 - Backtesting Framework
Simulate betting with trained Benter model and calculate performance

This script:
1. Loads trained model weights (α, β)
2. Loads historical race data
3. Calculates model probabilities
4. Identifies overlays (p_model > p_market)
5. Simulates Kelly-sized bets
6. Calculates ROI, Sharpe ratio, drawdown
7. Generates performance report
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime
import json
import argparse
import matplotlib.pyplot as plt

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.settings import settings
from src.core import log
import logging

# Setup logging
log.setup_logging("config/logging.json")
logger = logging.getLogger("velo.backtest")


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


def load_data(filepath, start_date, end_date):
    """Load and prepare race data"""
    logger.info(f"Loading data from {filepath}...")
    
    df = pd.read_csv(filepath, low_memory=False)
    logger.info(f"Loaded {len(df)} rows")
    
    # Parse dates
    df['date'] = pd.to_datetime(df['date'])
    
    # Filter by date range
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    logger.info(f"Filtered to {start_date} - {end_date}: {len(df)} rows")
    
    # Parse odds and ratings
    df['sp_decimal'] = df['sp'].apply(parse_odds)
    df['or_int'] = df['or'].apply(parse_rating)
    df['rpr_int'] = df['rpr'].apply(parse_rating)
    df['ts_int'] = df['ts'].apply(parse_rating)
    
    # Parse position
    df['pos_int'] = df['pos'].apply(lambda x: int(float(x)) if pd.notna(x) and str(x).replace('.','').isdigit() else None)
    df['is_winner'] = (df['pos_int'] == 1).astype(int)
    
    # Filter: must have odds, ratings, and result
    df = df[df['sp_decimal'].notna()]
    df = df[(df['or_int'].notna()) | (df['rpr_int'].notna()) | (df['ts_int'].notna())]
    df = df[df['pos_int'].notna()]
    
    logger.info(f"After filtering: {len(df)} rows, {df['race_id'].nunique()} races")
    
    # Calculate public probability
    df['p_public'] = 1.0 / df['sp_decimal']
    df['p_public_norm'] = df.groupby(['date', 'course', 'race_id'])['p_public'].transform(
        lambda x: x / x.sum()
    )
    
    return df


def calculate_fundamental_probability(row):
    """Calculate fundamental probability from ratings"""
    ratings = []
    if pd.notna(row['or_int']):
        ratings.append(row['or_int'])
    if pd.notna(row['rpr_int']):
        ratings.append(row['rpr_int'])
    if pd.notna(row['ts_int']):
        ratings.append(row['ts_int'])
    
    if not ratings:
        return None
    
    return np.mean(ratings)


def normalize_fundamental_probabilities(df):
    """Convert ratings to probabilities"""
    logger.info("Calculating fundamental probabilities...")
    
    df['rating_avg'] = df.apply(calculate_fundamental_probability, axis=1)
    df = df[df['rating_avg'].notna()].copy()
    
    def softmax_race(group):
        ratings = group['rating_avg'].values
        exp_ratings = np.exp(ratings / 20.0)
        probs = exp_ratings / exp_ratings.sum()
        return pd.Series(probs, index=group.index)
    
    df['p_fundamental'] = df.groupby(['date', 'course', 'race_id']).apply(softmax_race).reset_index(level=[0,1,2], drop=True)
    
    return df


def apply_benter_model(df, alpha, beta):
    """Apply Benter model with given weights"""
    logger.info(f"Applying Benter model (α={alpha:.2f}, β={beta:.2f})...")
    
    # Combine probabilities
    df['p_model_raw'] = alpha * df['p_fundamental'] + beta * df['p_public_norm']
    
    # Normalize by race
    df['p_model'] = df.groupby(['date', 'course', 'race_id'])['p_model_raw'].transform(
        lambda x: x / x.sum()
    )
    
    return df


def identify_overlays(df, min_edge=0.02, min_odds=1.5, max_odds=200.0):
    """
    Identify overlays where p_model > p_market
    
    Args:
        min_edge: Minimum edge (p_model - p_market)
        min_odds: Minimum odds to consider
        max_odds: Maximum odds to consider
    """
    logger.info(f"Identifying overlays (min_edge={min_edge}, odds {min_odds}-{max_odds})...")
    
    # Calculate edge
    df['p_market'] = df['p_public_norm']
    df['edge'] = df['p_model'] - df['p_market']
    
    # Filter overlays
    overlays = df[
        (df['edge'] >= min_edge) &
        (df['sp_decimal'] >= min_odds) &
        (df['sp_decimal'] <= max_odds)
    ].copy()
    
    logger.info(f"Found {len(overlays)} overlays ({len(overlays)/len(df)*100:.1f}% of races)")
    
    return overlays


def calculate_kelly_stake(p_model, odds, fractional_kelly=0.33, bankroll=1.0):
    """
    Calculate Kelly criterion stake
    
    Args:
        p_model: Model probability
        odds: Decimal odds
        fractional_kelly: Fraction of Kelly to use (0.0-1.0)
        bankroll: Current bankroll
    
    Returns:
        Stake amount
    """
    # Full Kelly: f* = (p * odds - 1) / (odds - 1)
    full_kelly = (p_model * odds - 1) / (odds - 1)
    
    # Fractional Kelly
    kelly_fraction = full_kelly * fractional_kelly
    
    # Clip to [0, 1] (never bet more than bankroll, never negative)
    kelly_fraction = np.clip(kelly_fraction, 0.0, 1.0)
    
    # Stake
    stake = kelly_fraction * bankroll
    
    return stake


def simulate_betting(overlays, initial_bankroll=1000.0, fractional_kelly=0.33):
    """
    Simulate betting with Kelly sizing
    
    Args:
        overlays: DataFrame of overlays
        initial_bankroll: Starting bankroll
        fractional_kelly: Fraction of Kelly to use
    
    Returns:
        DataFrame with bet results and bankroll history
    """
    logger.info(f"Simulating betting (initial bankroll={initial_bankroll}, Kelly={fractional_kelly})...")
    
    # Sort by date
    overlays = overlays.sort_values('date').copy()
    
    # Initialize
    bankroll = initial_bankroll
    bankroll_history = [bankroll]
    
    results = []
    
    for idx, row in overlays.iterrows():
        # Calculate stake
        stake = calculate_kelly_stake(
            row['p_model'],
            row['sp_decimal'],
            fractional_kelly,
            bankroll
        )
        
        # Place bet
        if row['is_winner'] == 1:
            # Win
            profit = stake * (row['sp_decimal'] - 1)
            bankroll += profit
            result = 'win'
        else:
            # Loss
            profit = -stake
            bankroll += profit
            result = 'loss'
        
        bankroll_history.append(bankroll)
        
        results.append({
            'date': row['date'],
            'course': row['course'],
            'race_id': row['race_id'],
            'horse': row['horse'],
            'odds': row['sp_decimal'],
            'p_model': row['p_model'],
            'p_market': row['p_market'],
            'edge': row['edge'],
            'stake': stake,
            'profit': profit,
            'bankroll': bankroll,
            'result': result
        })
    
    results_df = pd.DataFrame(results)
    
    logger.info(f"Simulation complete: {len(results)} bets placed")
    logger.info(f"Final bankroll: £{bankroll:.2f} (started with £{initial_bankroll:.2f})")
    
    return results_df, bankroll_history


def calculate_performance_metrics(results_df, bankroll_history, initial_bankroll):
    """Calculate performance metrics"""
    logger.info("Calculating performance metrics...")
    
    # Total bets
    total_bets = len(results_df)
    
    # Wins/losses
    wins = (results_df['result'] == 'win').sum()
    losses = (results_df['result'] == 'loss').sum()
    win_rate = wins / total_bets if total_bets > 0 else 0
    
    # ROI
    total_staked = results_df['stake'].sum()
    total_profit = results_df['profit'].sum()
    roi = (total_profit / total_staked) if total_staked > 0 else 0
    
    # Final bankroll
    final_bankroll = bankroll_history[-1]
    total_return = (final_bankroll - initial_bankroll) / initial_bankroll
    
    # Sharpe ratio (annualized)
    daily_returns = results_df.groupby('date')['profit'].sum()
    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if len(daily_returns) > 1 else 0
    
    # Maximum drawdown
    bankroll_array = np.array(bankroll_history)
    running_max = np.maximum.accumulate(bankroll_array)
    drawdown = (bankroll_array - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Average edge
    avg_edge = results_df['edge'].mean()
    
    # Average odds
    avg_odds = results_df['odds'].mean()
    
    metrics = {
        'total_bets': int(total_bets),
        'wins': int(wins),
        'losses': int(losses),
        'win_rate': float(win_rate),
        'total_staked': float(total_staked),
        'total_profit': float(total_profit),
        'roi': float(roi),
        'initial_bankroll': float(initial_bankroll),
        'final_bankroll': float(final_bankroll),
        'total_return': float(total_return),
        'sharpe_ratio': float(sharpe),
        'max_drawdown': float(max_drawdown),
        'avg_edge': float(avg_edge),
        'avg_odds': float(avg_odds)
    }
    
    return metrics


def plot_results(results_df, bankroll_history, output_dir):
    """Generate performance plots"""
    logger.info("Generating plots...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Bankroll over time
    plt.figure(figsize=(12, 6))
    plt.plot(bankroll_history)
    plt.xlabel('Bet Number')
    plt.ylabel('Bankroll (£)')
    plt.title('Bankroll Over Time')
    plt.grid(True, alpha=0.3)
    plt.savefig(f'{output_dir}/bankroll_history.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    # 2. Cumulative profit
    plt.figure(figsize=(12, 6))
    results_df['cumulative_profit'] = results_df['profit'].cumsum()
    plt.plot(results_df['cumulative_profit'])
    plt.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    plt.xlabel('Bet Number')
    plt.ylabel('Cumulative Profit (£)')
    plt.title('Cumulative Profit Over Time')
    plt.grid(True, alpha=0.3)
    plt.savefig(f'{output_dir}/cumulative_profit.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    # 3. Edge distribution
    plt.figure(figsize=(10, 6))
    plt.hist(results_df['edge'], bins=50, edgecolor='black', alpha=0.7)
    plt.xlabel('Edge (p_model - p_market)')
    plt.ylabel('Frequency')
    plt.title('Distribution of Edges')
    plt.grid(True, alpha=0.3)
    plt.savefig(f'{output_dir}/edge_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Plots saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description='Backtest Benter model')
    parser.add_argument('--filepath', default='/home/ubuntu/upload/raceform.csv', help='Path to raceform.csv')
    parser.add_argument('--weights', default='models/benter_weights.json', help='Path to trained weights')
    parser.add_argument('--start-date', default='2024-01-01', help='Backtest start date')
    parser.add_argument('--end-date', default='2024-12-31', help='Backtest end date')
    parser.add_argument('--min-edge', type=float, default=0.02, help='Minimum edge threshold')
    parser.add_argument('--min-odds', type=float, default=1.5, help='Minimum odds')
    parser.add_argument('--max-odds', type=float, default=200.0, help='Maximum odds')
    parser.add_argument('--bankroll', type=float, default=1000.0, help='Initial bankroll')
    parser.add_argument('--kelly', type=float, default=0.33, help='Fractional Kelly')
    parser.add_argument('--output', default='results/backtest', help='Output directory')
    
    args = parser.parse_args()
    
    with log.EventLogger("backtest", filepath=args.filepath):
        # Load trained weights
        logger.info(f"Loading trained weights from {args.weights}...")
        with open(args.weights, 'r') as f:
            weights = json.load(f)
        
        alpha = weights['alpha']
        beta = weights['beta']
        logger.info(f"Loaded weights: α={alpha:.2f}, β={beta:.2f}")
        
        # Load data
        logger.info("=== LOADING DATA ===")
        df = load_data(args.filepath, args.start_date, args.end_date)
        
        # Calculate probabilities
        df = normalize_fundamental_probabilities(df)
        df = apply_benter_model(df, alpha, beta)
        
        # Identify overlays
        logger.info("=== IDENTIFYING OVERLAYS ===")
        overlays = identify_overlays(df, args.min_edge, args.min_odds, args.max_odds)
        
        if len(overlays) == 0:
            logger.error("No overlays found! Try lowering min_edge or adjusting odds range.")
            return
        
        # Simulate betting
        logger.info("=== SIMULATING BETTING ===")
        results_df, bankroll_history = simulate_betting(overlays, args.bankroll, args.kelly)
        
        # Calculate metrics
        logger.info("=== CALCULATING METRICS ===")
        metrics = calculate_performance_metrics(results_df, bankroll_history, args.bankroll)
        
        # Save results
        logger.info("=== SAVING RESULTS ===")
        os.makedirs(args.output, exist_ok=True)
        
        # Save metrics
        metrics['backtest_period'] = f"{args.start_date} to {args.end_date}"
        metrics['alpha'] = alpha
        metrics['beta'] = beta
        metrics['min_edge'] = args.min_edge
        metrics['fractional_kelly'] = args.kelly
        metrics['generated_at'] = datetime.now().isoformat()
        
        with open(f'{args.output}/metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Save bet results
        results_df.to_csv(f'{args.output}/bets.csv', index=False)
        
        # Generate plots
        plot_results(results_df, bankroll_history, args.output)
        
        # Print summary
        print("\n" + "="*60)
        print("🎉 BACKTEST COMPLETE")
        print("="*60)
        print(f"Period: {args.start_date} to {args.end_date}")
        print(f"Total bets: {metrics['total_bets']}")
        print(f"Win rate: {metrics['win_rate']*100:.1f}%")
        print(f"ROI: {metrics['roi']*100:+.1f}%")
        print(f"Total return: {metrics['total_return']*100:+.1f}%")
        print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Max drawdown: {metrics['max_drawdown']*100:.1f}%")
        print(f"Final bankroll: £{metrics['final_bankroll']:.2f}")
        print(f"\nResults saved to: {args.output}/")
        print("="*60)


if __name__ == "__main__":
    main()

