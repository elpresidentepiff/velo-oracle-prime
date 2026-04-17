"""
VÉLØ Oracle - TimeSeriesSplit Backtesting Framework

Implements chronologically-aware backtesting to prevent lookahead bias.
Based on research from sports-betting library and sklearn TimeSeriesSplit.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Results from a single backtest fold."""
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    num_train_races: int
    num_test_races: int
    test_roi: float
    test_profit: float
    test_sharpe: float
    test_max_drawdown: float
    test_win_rate: float
    total_bets: int


class TimeSeriesSplit:
    """
    Time series cross-validation.
    
    Ensures that:
    1. Training data always comes before test data
    2. No data leakage from future to past
    3. Realistic evaluation of model performance
    """
    
    def __init__(self, n_splits: int = 5, test_size: Optional[int] = None):
        """
        Initialize TimeSeriesSplit.
        
        Args:
            n_splits: Number of splits/folds
            test_size: Size of test set (in number of samples). If None, uses 1/n_splits of data.
        """
        self.n_splits = n_splits
        self.test_size = test_size
    
    def split(self, data: pd.DataFrame, date_column: str = 'race_date') -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Generate train/test splits.
        
        Args:
            data: DataFrame with race data
            date_column: Name of the date column
            
        Returns:
            List of (train_df, test_df) tuples
        """
        # Ensure data is sorted by date
        data = data.sort_values(date_column).reset_index(drop=True)
        
        n_samples = len(data)
        
        if self.test_size is None:
            test_size = n_samples // (self.n_splits + 1)
        else:
            test_size = self.test_size
        
        splits = []
        
        for i in range(self.n_splits):
            # Calculate split indices
            test_start_idx = (i + 1) * test_size
            test_end_idx = test_start_idx + test_size
            
            if test_end_idx > n_samples:
                break
            
            # Train on all data before test set
            train_df = data.iloc[:test_start_idx].copy()
            test_df = data.iloc[test_start_idx:test_end_idx].copy()
            
            splits.append((train_df, test_df))
            
            logger.info(f"Fold {i+1}: Train={len(train_df)}, Test={len(test_df)}")
        
        return splits


class PortfolioKellyCriterion:
    """
    Portfolio-based Kelly Criterion.
    
    Optimizes capital allocation across multiple simultaneous betting opportunities.
    More sophisticated than per-bet Kelly.
    """
    
    def __init__(self, kelly_fraction: float = 0.1, max_stake_pct: float = 0.05):
        """
        Initialize Portfolio Kelly Criterion.
        
        Args:
            kelly_fraction: Fraction of Kelly to use (for safety)
            max_stake_pct: Maximum stake as percentage of bankroll per bet
        """
        self.kelly_fraction = kelly_fraction
        self.max_stake_pct = max_stake_pct
    
    def calculate_stakes(
        self,
        opportunities: List[Dict[str, float]],
        bankroll: float
    ) -> List[float]:
        """
        Calculate optimal stakes for a portfolio of betting opportunities.
        
        Args:
            opportunities: List of dicts with 'probability' and 'odds'
            bankroll: Current bankroll
            
        Returns:
            List of optimal stakes
        """
        stakes = []
        
        for opp in opportunities:
            prob = opp['probability']
            odds = opp['odds']
            
            # Kelly formula: f = (p * odds - 1) / (odds - 1)
            kelly_stake = (prob * odds - 1) / (odds - 1)
            
            # Apply Kelly fraction
            stake = kelly_stake * self.kelly_fraction * bankroll
            
            # Apply maximum stake limit
            max_stake = bankroll * self.max_stake_pct
            stake = min(stake, max_stake)
            
            # Ensure non-negative
            stake = max(0, stake)
            
            stakes.append(stake)
        
        # Normalize if total stakes exceed bankroll
        total_stakes = sum(stakes)
        if total_stakes > bankroll * 0.5:  # Don't risk more than 50% of bankroll at once
            scale_factor = (bankroll * 0.5) / total_stakes
            stakes = [s * scale_factor for s in stakes]
        
        return stakes


class TimeSeriesBacktester:
    """
    Complete backtesting framework with TimeSeriesSplit.
    
    Combines:
    - Chronological cross-validation
    - Portfolio Kelly Criterion
    - Performance metrics calculation
    """
    
    def __init__(
        self,
        model,
        kelly_fraction: float = 0.1,
        min_edge: float = 0.05,
        initial_bankroll: float = 1000.0
    ):
        """
        Initialize backtester.
        
        Args:
            model: Model with predict() method
            kelly_fraction: Kelly fraction for bet sizing
            min_edge: Minimum edge required to place bet
            initial_bankroll: Starting bankroll
        """
        self.model = model
        self.kelly_fraction = kelly_fraction
        self.min_edge = min_edge
        self.initial_bankroll = initial_bankroll
        
        self.portfolio_kelly = PortfolioKellyCriterion(kelly_fraction)
    
    def backtest(
        self,
        data: pd.DataFrame,
        n_splits: int = 5,
        date_column: str = 'race_date'
    ) -> List[BacktestResult]:
        """
        Run backtest with TimeSeriesSplit.
        
        Args:
            data: DataFrame with race data
            n_splits: Number of cross-validation splits
            date_column: Name of the date column
            
        Returns:
            List of BacktestResult objects
        """
        logger.info(f"Starting TimeSeriesSplit backtest with {n_splits} folds")
        
        # Create time series splits
        tscv = TimeSeriesSplit(n_splits=n_splits)
        splits = tscv.split(data, date_column)
        
        results = []
        
        for fold_id, (train_df, test_df) in enumerate(splits, 1):
            logger.info(f"Processing fold {fold_id}/{len(splits)}")
            
            # Train model (placeholder - actual training would happen here)
            # self.model.fit(train_df)
            
            # Run backtest on test set
            fold_result = self._backtest_fold(
                fold_id=fold_id,
                train_df=train_df,
                test_df=test_df
            )
            
            results.append(fold_result)
            
            logger.info(f"Fold {fold_id} ROI: {fold_result.test_roi:.3f}")
        
        return results
    
    def _backtest_fold(
        self,
        fold_id: int,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> BacktestResult:
        """Run backtest on a single fold."""
        bankroll = self.initial_bankroll
        total_profit = 0.0
        total_bets = 0
        wins = 0
        equity_curve = [bankroll]
        
        # Group by race
        races = test_df.groupby('race_id')
        
        for race_id, race_data in races:
            # Get predictions for this race
            predictions = self._get_predictions(race_data)
            
            # Filter by minimum edge
            opportunities = []
            for pred in predictions:
                edge = pred['probability'] - (1 / pred['odds'])
                if edge >= self.min_edge:
                    opportunities.append(pred)
            
            if not opportunities:
                continue
            
            # Calculate optimal stakes using Portfolio Kelly
            stakes = self.portfolio_kelly.calculate_stakes(opportunities, bankroll)
            
            # Place bets and calculate results
            race_profit = 0.0
            for opp, stake in zip(opportunities, stakes):
                if stake <= 0:
                    continue
                
                total_bets += 1
                
                # Check if bet won
                actual_result = race_data[race_data['horse_name'] == opp['horse_name']]['result'].iloc[0]
                
                if actual_result == 'win':
                    profit = stake * (opp['odds'] - 1)
                    wins += 1
                else:
                    profit = -stake
                
                race_profit += profit
            
            # Update bankroll
            bankroll += race_profit
            total_profit += race_profit
            equity_curve.append(bankroll)
        
        # Calculate metrics
        roi = (bankroll / self.initial_bankroll) - 1
        win_rate = wins / total_bets if total_bets > 0 else 0.0
        sharpe = self._calculate_sharpe(equity_curve)
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        return BacktestResult(
            fold_id=fold_id,
            train_start=train_df.iloc[0]['race_date'] if len(train_df) > 0 else '',
            train_end=train_df.iloc[-1]['race_date'] if len(train_df) > 0 else '',
            test_start=test_df.iloc[0]['race_date'] if len(test_df) > 0 else '',
            test_end=test_df.iloc[-1]['race_date'] if len(test_df) > 0 else '',
            num_train_races=len(train_df.groupby('race_id')),
            num_test_races=len(test_df.groupby('race_id')),
            test_roi=roi,
            test_profit=total_profit,
            test_sharpe=sharpe,
            test_max_drawdown=max_drawdown,
            test_win_rate=win_rate,
            total_bets=total_bets
        )
    
    def _get_predictions(self, race_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Get model predictions for a race."""
        predictions = []
        
        for _, horse in race_data.iterrows():
            # Get model prediction (placeholder)
            prob = self.model.predict_proba(horse) if hasattr(self.model, 'predict_proba') else 0.1
            
            pred = {
                'horse_name': horse['horse_name'],
                'probability': prob,
                'odds': horse.get('odds', 5.0)
            }
            predictions.append(pred)
        
        return predictions
    
    def _calculate_sharpe(self, equity_curve: List[float]) -> float:
        """Calculate Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
        return sharpe
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown from equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def summarize_results(self, results: List[BacktestResult]) -> pd.DataFrame:
        """Summarize backtest results across all folds."""
        summary_data = []
        
        for result in results:
            summary_data.append({
                'Fold': result.fold_id,
                'Test Period': f"{result.test_start} to {result.test_end}",
                'Test Races': result.num_test_races,
                'Total Bets': result.total_bets,
                'ROI': f"{result.test_roi:.2%}",
                'Profit': f"£{result.test_profit:.2f}",
                'Sharpe': f"{result.test_sharpe:.2f}",
                'Max DD': f"{result.test_max_drawdown:.2%}",
                'Win Rate': f"{result.test_win_rate:.2%}"
            })
        
        df = pd.DataFrame(summary_data)
        
        # Add average row
        avg_roi = np.mean([r.test_roi for r in results])
        avg_sharpe = np.mean([r.test_sharpe for r in results])
        avg_win_rate = np.mean([r.test_win_rate for r in results])
        total_profit = sum([r.test_profit for r in results])
        
        avg_row = {
            'Fold': 'AVERAGE',
            'Test Period': '-',
            'Test Races': '-',
            'Total Bets': sum([r.total_bets for r in results]),
            'ROI': f"{avg_roi:.2%}",
            'Profit': f"£{total_profit:.2f}",
            'Sharpe': f"{avg_sharpe:.2f}",
            'Max DD': '-',
            'Win Rate': f"{avg_win_rate:.2%}"
        }
        
        df = pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)
        
        return df

