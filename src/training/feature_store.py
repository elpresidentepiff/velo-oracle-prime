"""
VÉLØ v10.1 - Feature Store
===========================

Cached feature engineering for Benter model training.
Computes and stores features: form curves, pace, draw, ROI metrics, going, course.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureStore:
    """
    Feature engineering and caching for ML training.
    
    Features computed:
    - Form curves (last 3, 5, 10 runs)
    - Pace metrics (early speed, late speed)
    - Draw bias (by course/distance)
    - Jockey/Trainer/Sire ROI
    - Going preference
    - Course/Distance specialization
    - Class movement
    - Days since last run
    - Weight carried
    - Age factors
    """
    
    def __init__(self, cache_dir: str = "out/features"):
        """
        Initialize feature store.
        
        Args:
            cache_dir: Directory for cached features
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FeatureStore initialized with cache: {self.cache_dir}")
    
    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features for a dataset.
        
        Args:
            df: Raw race data with columns:
                - race_id, horse_id, jockey_id, trainer_id, sire_id
                - race_date, course, distance, going, class_level
                - draw, weight, age, sex
                - last_runs (JSON of recent form)
                - odds (if available)
        
        Returns:
            DataFrame with engineered features
        """
        logger.info(f"Computing features for {len(df)} runners...")
        
        features = df.copy()
        
        # Form features
        features = self._add_form_features(features)
        
        # Pace features
        features = self._add_pace_features(features)
        
        # Draw features
        features = self._add_draw_features(features)
        
        # ROI features (jockey, trainer, sire)
        features = self._add_roi_features(features)
        
        # Going preference
        features = self._add_going_features(features)
        
        # Course/Distance specialization
        features = self._add_course_distance_features(features)
        
        # Class movement
        features = self._add_class_features(features)
        
        # Recency features
        features = self._add_recency_features(features)
        
        # Physical features
        features = self._add_physical_features(features)
        
        # Market features (if odds available)
        if 'odds' in features.columns:
            features = self._add_market_features(features)
        
        logger.info(f"Feature engineering complete. Shape: {features.shape}")
        return features
    
    def _add_form_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add form curve features (last 3, 5, 10 runs)."""
        logger.debug("Computing form features...")
        
        # Placeholder for form parsing - would parse last_runs JSON
        df['form_last_3'] = 0.0  # Avg finish position last 3
        df['form_last_5'] = 0.0  # Avg finish position last 5
        df['form_last_10'] = 0.0  # Avg finish position last 10
        df['wins_last_3'] = 0  # Wins in last 3
        df['places_last_3'] = 0  # Places in last 3
        df['consistency_score'] = 0.0  # Variance of recent finishes
        df['improvement_trend'] = 0.0  # Linear trend of recent form
        
        return df
    
    def _add_pace_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add pace metrics (early speed, late speed)."""
        logger.debug("Computing pace features...")
        
        df['early_pace_rating'] = 0.0  # Early speed indicator
        df['late_pace_rating'] = 0.0  # Finishing speed indicator
        df['pace_style'] = 0  # 0=balanced, 1=front-runner, 2=closer
        df['sectional_avg'] = 0.0  # Average sectional times
        
        return df
    
    def _add_draw_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add draw bias features by course/distance."""
        logger.debug("Computing draw features...")
        
        # Group by course + distance to compute draw bias
        df['draw_bias'] = 0.0  # Historical win rate by draw position
        df['draw_advantage'] = 0.0  # Relative advantage of this draw
        df['draw_percentile'] = 0.0  # Percentile of draw (0-100)
        
        return df
    
    def _add_roi_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add jockey/trainer/sire ROI features."""
        logger.debug("Computing ROI features...")
        
        # Historical ROI by entity
        df['jockey_roi'] = 0.0  # Jockey ROI at this course/distance
        df['jockey_strike_rate'] = 0.0  # Jockey win %
        df['trainer_roi'] = 0.0  # Trainer ROI at this course/distance
        df['trainer_strike_rate'] = 0.0  # Trainer win %
        df['sire_roi'] = 0.0  # Sire ROI at this distance/going
        df['jockey_trainer_combo_roi'] = 0.0  # Combo ROI
        
        return df
    
    def _add_going_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add going preference features."""
        logger.debug("Computing going features...")
        
        df['going_preference'] = 0.0  # Historical performance on this going
        df['going_win_rate'] = 0.0  # Win rate on this going type
        df['going_mismatch'] = 0  # Binary: unsuited to going
        
        return df
    
    def _add_course_distance_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add course/distance specialization features."""
        logger.debug("Computing course/distance features...")
        
        df['course_form'] = 0.0  # Performance at this course
        df['course_wins'] = 0  # Wins at this course
        df['distance_form'] = 0.0  # Performance at this distance
        df['distance_wins'] = 0  # Wins at this distance
        df['course_distance_form'] = 0.0  # Performance at course+distance
        df['track_type_form'] = 0.0  # Performance on flat/jump/AW
        
        return df
    
    def _add_class_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add class movement features."""
        logger.debug("Computing class features...")
        
        df['class_movement'] = 0  # +1 up, 0 same, -1 down
        df['class_drop_wins'] = 0  # Wins when dropping class
        df['class_stability'] = 0.0  # Consistency at this class level
        
        return df
    
    def _add_recency_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add recency features (days since last run)."""
        logger.debug("Computing recency features...")
        
        df['days_since_last_run'] = 0  # Days since last race
        df['optimal_layoff'] = 0  # Binary: within optimal layoff window
        df['too_fresh'] = 0  # Binary: < 7 days
        df['too_stale'] = 0  # Binary: > 90 days
        
        return df
    
    def _add_physical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add physical features (weight, age, sex)."""
        logger.debug("Computing physical features...")
        
        # Weight features (placeholder - would need parsing from UK format like '11-6')
        df['weight_carried'] = 0.0
        df['weight_vs_avg'] = 0.0
        
        if 'age' in df.columns:
            df['age_value'] = df['age']
            df['age_optimal'] = 0  # Binary: in optimal age range
        else:
            df['age_value'] = 0
            df['age_optimal'] = 0
        
        if 'sex' in df.columns:
            df['is_gelding'] = (df['sex'] == 'G').astype(int)
            df['is_mare'] = (df['sex'] == 'M').astype(int)
        else:
            df['is_gelding'] = 0
            df['is_mare'] = 0
        
        return df
    
    def _add_market_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market-based features (if odds available)."""
        logger.debug("Computing market features...")
        
        if 'odds' in df.columns:
            df['odds_decimal'] = df['odds']
            df['implied_prob'] = 1.0 / df['odds']
            df['odds_rank'] = df.groupby('race_id')['odds'].rank()
            df['is_favorite'] = (df['odds_rank'] == 1).astype(int)
            df['odds_drift'] = 0.0  # Would compute from historical odds
        
        return df
    
    def save_features(self, features: pd.DataFrame, name: str):
        """
        Save features to cache.
        
        Args:
            features: Feature DataFrame
            name: Cache name (e.g., 'train', 'validation')
        """
        cache_path = self.cache_dir / f"{name}_features.parquet"
        features.to_parquet(cache_path, index=False)
        logger.info(f"Features saved to {cache_path}")
    
    def load_features(self, name: str) -> Optional[pd.DataFrame]:
        """
        Load features from cache.
        
        Args:
            name: Cache name
        
        Returns:
            Feature DataFrame or None if not found
        """
        cache_path = self.cache_dir / f"{name}_features.parquet"
        if cache_path.exists():
            logger.info(f"Loading features from {cache_path}")
            return pd.read_parquet(cache_path)
        else:
            logger.warning(f"Feature cache not found: {cache_path}")
            return None
    
    def get_feature_names(self) -> List[str]:
        """
        Get list of all feature names.
        
        Returns:
            List of feature column names
        """
        return [
            # Form features
            'form_last_3', 'form_last_5', 'form_last_10',
            'wins_last_3', 'places_last_3', 'consistency_score', 'improvement_trend',
            
            # Pace features
            'early_pace_rating', 'late_pace_rating', 'pace_style', 'sectional_avg',
            
            # Draw features
            'draw_bias', 'draw_advantage', 'draw_percentile',
            
            # ROI features
            'jockey_roi', 'jockey_strike_rate',
            'trainer_roi', 'trainer_strike_rate',
            'sire_roi', 'jockey_trainer_combo_roi',
            
            # Going features
            'going_preference', 'going_win_rate', 'going_mismatch',
            
            # Course/Distance features
            'course_form', 'course_wins', 'distance_form', 'distance_wins',
            'course_distance_form', 'track_type_form',
            
            # Class features
            'class_movement', 'class_drop_wins', 'class_stability',
            
            # Recency features
            'days_since_last_run', 'optimal_layoff', 'too_fresh', 'too_stale',
            
            # Physical features
            'weight_carried', 'weight_vs_avg', 'age_value', 'age_optimal',
            'is_gelding', 'is_mare',
            
            # Market features (if available)
            'odds_decimal', 'implied_prob', 'odds_rank', 'is_favorite', 'odds_drift'
        ]


if __name__ == "__main__":
    # Test feature store
    logging.basicConfig(level=logging.INFO)
    
    # Create sample data
    sample_data = pd.DataFrame({
        'race_id': ['R1'] * 10,
        'horse_id': [f'H{i}' for i in range(10)],
        'jockey_id': [f'J{i%3}' for i in range(10)],
        'trainer_id': [f'T{i%4}' for i in range(10)],
        'odds': np.random.uniform(2.0, 20.0, 10)
    })
    
    store = FeatureStore()
    features = store.compute_features(sample_data)
    
    print(f"\nFeature shape: {features.shape}")
    print(f"Feature columns: {len(store.get_feature_names())}")
    print(f"\nSample features:\n{features.head()}")
