"""
VÉLØ v10.1 - Label Creation
============================

Target variable creation for Benter model training.
Computes: win, place, IV (Impact Value), A/E (Actual vs Expected).

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LabelCreator:
    """
    Creates target labels for ML training.
    
    Labels computed:
    - win: Binary (1 if won, 0 otherwise)
    - place: Binary (1 if placed, 0 otherwise)
    - finish_position: Actual finish position
    - iv: Impact Value (normalized performance metric)
    - ae: Actual vs Expected ratio
    """
    
    def __init__(self, place_positions: int = 3):
        """
        Initialize label creator.
        
        Args:
            place_positions: Number of positions that count as "place" (default 3)
        """
        self.place_positions = place_positions
        logger.info(f"LabelCreator initialized (place_positions={place_positions})")
    
    def create_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create all labels for a dataset.
        
        Args:
            df: DataFrame with columns:
                - race_id
                - horse_id
                - finish_position (actual result)
                - odds (market odds)
                - field_size (number of runners)
        
        Returns:
            DataFrame with label columns added
        """
        logger.info(f"Creating labels for {len(df)} runners...")
        
        labels = df.copy()
        
        # Win label
        labels['win'] = (labels['finish_position'] == 1).astype(int)
        
        # Place label
        labels['place'] = (labels['finish_position'] <= self.place_positions).astype(int)
        
        # Top 4 label (for EW analysis)
        labels['top4'] = (labels['finish_position'] <= 4).astype(int)
        
        # Impact Value (IV)
        labels = self._compute_impact_value(labels)
        
        # Actual vs Expected (A/E)
        labels = self._compute_actual_vs_expected(labels)
        
        # Beaten favorite (for fade analysis)
        labels = self._compute_beaten_favorite(labels)
        
        logger.info(f"Label creation complete. Win rate: {labels['win'].mean():.2%}")
        
        return labels
    
    def _compute_impact_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Impact Value (IV).
        
        IV measures performance relative to field size and odds.
        Formula: IV = (field_size - finish_position + 1) / field_size
        
        Args:
            df: DataFrame with finish_position and field_size
        
        Returns:
            DataFrame with 'iv' column added
        """
        logger.debug("Computing Impact Value...")
        
        if 'field_size' not in df.columns:
            # Compute field size from race_id grouping
            df['field_size'] = df.groupby('race_id')['horse_id'].transform('count')
        
        # IV formula: normalized position (1.0 for winner, 0.0 for last)
        df['iv'] = (df['field_size'] - df['finish_position'] + 1) / df['field_size']
        
        # Handle non-finishers (DNF, PU, etc.) - assign IV = 0
        df.loc[df['finish_position'] > df['field_size'], 'iv'] = 0.0
        
        return df
    
    def _compute_actual_vs_expected(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Actual vs Expected (A/E) ratio.
        
        A/E compares actual win rate to implied probability from odds.
        A/E > 1.0 means outperforming market expectations.
        
        Args:
            df: DataFrame with win label and odds
        
        Returns:
            DataFrame with 'ae' column added
        """
        logger.debug("Computing Actual vs Expected...")
        
        if 'odds' not in df.columns:
            logger.warning("Odds not available, setting A/E to NaN")
            df['ae'] = np.nan
            return df
        
        # Expected probability from odds
        df['expected_prob'] = 1.0 / df['odds']
        
        # Actual probability (1 if won, 0 if lost)
        df['actual_prob'] = df['win'].astype(float)
        
        # A/E ratio (avoid division by zero)
        df['ae'] = np.where(
            df['expected_prob'] > 0,
            df['actual_prob'] / df['expected_prob'],
            np.nan
        )
        
        return df
    
    def _compute_beaten_favorite(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify beaten favorites for fade analysis.
        
        Args:
            df: DataFrame with odds and finish_position
        
        Returns:
            DataFrame with 'is_favorite' and 'beaten_favorite' columns
        """
        logger.debug("Computing beaten favorite flags...")
        
        if 'odds' not in df.columns:
            df['is_favorite'] = 0
            df['beaten_favorite'] = 0
            return df
        
        # Identify favorite (lowest odds in race)
        df['is_favorite'] = (
            df.groupby('race_id')['odds']
            .transform(lambda x: x == x.min())
            .astype(int)
        )
        
        # Beaten favorite (favorite that didn't win)
        df['beaten_favorite'] = (
            (df['is_favorite'] == 1) & (df['win'] == 0)
        ).astype(int)
        
        return df
    
    def compute_roi(self, df: pd.DataFrame, stake: float = 1.0) -> Dict[str, float]:
        """
        Compute ROI metrics for a set of predictions.
        
        Args:
            df: DataFrame with win label, odds, and optional 'predicted' column
            stake: Stake per bet (default 1.0)
        
        Returns:
            Dictionary with ROI metrics
        """
        logger.info("Computing ROI metrics...")
        
        if 'odds' not in df.columns or 'win' not in df.columns:
            logger.error("Cannot compute ROI: missing odds or win labels")
            return {}
        
        # Total bets
        num_bets = len(df)
        
        # Total staked
        total_staked = num_bets * stake
        
        # Total returns (stake * odds for winners)
        total_returns = (df['win'] * df['odds'] * stake).sum()
        
        # Profit/Loss
        profit = total_returns - total_staked
        
        # ROI
        roi = (profit / total_staked) * 100 if total_staked > 0 else 0.0
        
        # Win rate
        win_rate = df['win'].mean()
        
        # Place rate (if place column exists)
        place_rate = df['place'].mean() if 'place' in df.columns else 0.0
        
        # A/E ratio (if ae column exists)
        ae_ratio = df['ae'].mean() if 'ae' in df.columns else 0.0
        
        metrics = {
            'num_bets': num_bets,
            'total_staked': total_staked,
            'total_returns': total_returns,
            'profit': profit,
            'roi_pct': roi,
            'win_rate': win_rate,
            'place_rate': place_rate,
            'ae_ratio': ae_ratio
        }
        
        logger.info(f"ROI: {roi:.2f}% | Win Rate: {win_rate:.2%} | A/E: {ae_ratio:.3f}")
        
        return metrics
    
    def compute_roi_by_odds_band(
        self, 
        df: pd.DataFrame, 
        bands: List[Tuple[float, float]] = None
    ) -> pd.DataFrame:
        """
        Compute ROI by odds bands.
        
        Args:
            df: DataFrame with labels and odds
            bands: List of (min_odds, max_odds) tuples
        
        Returns:
            DataFrame with ROI by odds band
        """
        if bands is None:
            # Default bands: 3-5, 5-8, 8-12, 12-20, 20+
            bands = [(3, 5), (5, 8), (8, 12), (12, 20), (20, 100)]
        
        results = []
        
        for min_odds, max_odds in bands:
            band_df = df[(df['odds'] >= min_odds) & (df['odds'] < max_odds)]
            
            if len(band_df) == 0:
                continue
            
            metrics = self.compute_roi(band_df)
            metrics['odds_band'] = f"{min_odds}-{max_odds}"
            results.append(metrics)
        
        return pd.DataFrame(results)


if __name__ == "__main__":
    # Test label creator
    logging.basicConfig(level=logging.INFO)
    
    # Create sample data
    sample_data = pd.DataFrame({
        'race_id': ['R1'] * 10 + ['R2'] * 8,
        'horse_id': [f'H{i}' for i in range(18)],
        'finish_position': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1, 2, 3, 4, 5, 6, 7, 8],
        'odds': [5.0, 3.5, 8.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0,
                 2.5, 4.0, 6.0, 10.0, 15.0, 20.0, 25.0, 35.0]
    })
    
    creator = LabelCreator(place_positions=3)
    labels = creator.create_labels(sample_data)
    
    print(f"\nLabels shape: {labels.shape}")
    print(f"\nWin rate: {labels['win'].mean():.2%}")
    print(f"Place rate: {labels['place'].mean():.2%}")
    print(f"Mean A/E: {labels['ae'].mean():.3f}")
    
    print(f"\nSample labels:\n{labels[['horse_id', 'finish_position', 'win', 'place', 'iv', 'ae']].head(10)}")
    
    # ROI analysis
    roi_metrics = creator.compute_roi(labels)
    print(f"\nROI Metrics:\n{roi_metrics}")
    
    # ROI by odds band
    roi_by_band = creator.compute_roi_by_odds_band(labels)
    print(f"\nROI by Odds Band:\n{roi_by_band}")
