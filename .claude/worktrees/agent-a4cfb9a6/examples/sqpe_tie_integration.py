"""
SQPE + TIE Integration Example

Demonstrates how to combine SQPE (win probability) with TIE (trainer intent)
to generate adjusted probabilities for betting decisions.

This is the core dual-signal convergence logic that powers VÉLØ Oracle.

Author: VÉLØ Oracle Team
"""

from pathlib import Path
import pandas as pd
import numpy as np

from src.intelligence.sqpe import SQPEEngine, SQPEConfig
from src.intelligence.tie import TrainerIntentEngine, TIEConfig


def train_sqpe_tie_models(
    training_data: pd.DataFrame,
    sqpe_features: list[str],
    tie_features: list[str],
    output_dir: Path,
) -> tuple[SQPEEngine, TrainerIntentEngine]:
    """
    Train both SQPE and TIE models on historical data.
    
    Args:
        training_data: Historical race data with features and labels
        sqpe_features: List of feature column names for SQPE
        tie_features: List of feature column names for TIE
        output_dir: Directory to save trained models
    
    Returns:
        (trained_sqpe, trained_tie)
    """
    # Prepare SQPE training data
    X_sqpe = training_data[sqpe_features]
    y_sqpe = training_data['won']  # Binary: 1 = winner, 0 = loser
    
    # Train SQPE
    sqpe_config = SQPEConfig(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=3,
        time_splits=5,
    )
    sqpe = SQPEEngine(config=sqpe_config)
    sqpe.fit(X_sqpe, y_sqpe, time_order=training_data.index)
    
    print(f"SQPE trained. CV metrics: {sqpe.cv_metrics}")
    
    # Save SQPE
    sqpe.save(output_dir / "sqpe_v1")
    
    # Build trainer stats for TIE
    trainer_stats = TrainerIntentEngine.build_trainer_stats(
        training_data,
        date_col="race_date",
        trainer_col="trainer",
        won_col="won",
    )
    
    # Build TIE features
    X_tie = TrainerIntentEngine.build_runner_features(
        training_data,
        trainer_stats,
        trainer_col="trainer",
        days_since_run_col="days_since_run",
        class_change_col="class_delta",
        jockey_change_col="jockey_change_rank",
    )
    
    # Label high-intent cases (example logic - customize based on your strategy)
    # High intent = class drop + freshened + trainer profitable in niche
    y_intent = (
        (training_data['class_delta'] < -1) &  # Significant class drop
        (training_data['days_since_run'].between(14, 28)) &  # Optimal rest
        (training_data['trainer_win_rate'] > 0.15)  # Above-average trainer
    ).astype(int)
    
    # Train TIE
    tie_config = TIEConfig(
        min_trainer_runs=50,
        lookback_days=90,
        regularization_c=0.5,
    )
    tie = TrainerIntentEngine(config=tie_config)
    tie.fit(X_tie, y_intent)
    
    print(f"TIE trained successfully")
    
    return sqpe, tie


def generate_adjusted_probabilities(
    live_runners: pd.DataFrame,
    sqpe: SQPEEngine,
    tie: TrainerIntentEngine,
    trainer_stats: pd.DataFrame,
    sqpe_features: list[str],
    alpha: float = 0.25,
) -> pd.DataFrame:
    """
    Generate SQPE probabilities adjusted by TIE intent scores.
    
    This is the core dual-signal convergence logic.
    
    Args:
        live_runners: Current race card data
        sqpe: Trained SQPE engine
        tie: Trained TIE engine
        trainer_stats: Pre-computed trainer statistics
        sqpe_features: Feature columns for SQPE
        alpha: Intent adjustment strength (0-1)
    
    Returns:
        DataFrame with columns: runner_id, p_sqpe, tie_score, p_adjusted
    """
    # Get SQPE probabilities
    X_sqpe = live_runners[sqpe_features]
    p_sqpe = sqpe.predict_proba(X_sqpe)
    
    # Build TIE features
    X_tie = TrainerIntentEngine.build_runner_features(
        live_runners,
        trainer_stats,
        trainer_col="trainer",
        days_since_run_col="days_since_run",
        class_change_col="class_delta",
        jockey_change_col="jockey_change_rank",
    )
    
    # Get TIE intent scores
    tie_scores = tie.predict_intent_score(X_tie)
    
    # Adjust SQPE probabilities with TIE intent
    # Formula: p_adj = p_sqpe * (1 + alpha * (tie_score - 0.5) * 2)
    # This centers adjustment around 1.0:
    #   - tie_score = 1.0 → multiplier = 1 + alpha
    #   - tie_score = 0.5 → multiplier = 1.0 (no change)
    #   - tie_score = 0.0 → multiplier = 1 - alpha
    
    adjustment = 1.0 + alpha * (tie_scores - 0.5) * 2.0
    p_adjusted = p_sqpe * adjustment
    
    # Re-normalize within race (optional - ensures probabilities sum to 1)
    p_adjusted = p_adjusted / p_adjusted.sum()
    
    # Build result DataFrame
    results = pd.DataFrame({
        'runner_id': live_runners.index,
        'horse': live_runners['horse'],
        'p_sqpe': p_sqpe,
        'tie_score': tie_scores,
        'adjustment_factor': adjustment,
        'p_adjusted': p_adjusted,
        'edge_vs_market': p_adjusted - (1.0 / live_runners['sp_decimal']),
    })
    
    return results.sort_values('p_adjusted', ascending=False)


def identify_betting_opportunities(
    adjusted_probs: pd.DataFrame,
    min_edge: float = 0.05,
    min_tie_score: float = 0.6,
) -> pd.DataFrame:
    """
    Filter to high-confidence betting opportunities.
    
    Args:
        adjusted_probs: Output from generate_adjusted_probabilities()
        min_edge: Minimum edge vs market (e.g., 0.05 = 5%)
        min_tie_score: Minimum trainer intent score
    
    Returns:
        Filtered DataFrame with betting opportunities
    """
    opportunities = adjusted_probs[
        (adjusted_probs['edge_vs_market'] > min_edge) &
        (adjusted_probs['tie_score'] > min_tie_score)
    ]
    
    return opportunities


# Example usage
if __name__ == "__main__":
    # This is a skeleton - you'd load real data here
    print("SQPE + TIE Integration Example")
    print("=" * 50)
    print()
    print("Key Concepts:")
    print("1. SQPE generates base win probabilities (cold statistical spine)")
    print("2. TIE detects trainer intent patterns (behavioral edge)")
    print("3. Combine: p_adjusted = p_sqpe * (1 + alpha * (tie_score - 0.5) * 2)")
    print("4. Filter for positive edge vs market + high intent")
    print()
    print("This is the dual-signal convergence that powers VÉLØ Oracle.")

