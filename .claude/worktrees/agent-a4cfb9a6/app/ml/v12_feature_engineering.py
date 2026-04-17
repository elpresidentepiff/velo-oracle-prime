#!/usr/bin/env python3
"""
VELO v12 Feature Engineering Pipeline
Builds 47+ engineered features from raw raceform data

This module transforms raw racing data into a comprehensive feature set including:
- Form features (win/place rates over various windows)
- Pace features (early/late pace ratings, style classification)
- Draw features (bias, advantage, percentile)
- Trainer/Jockey/Sire features (strike rates, ROI)
- Course/Going/Distance features (preferences, form)
- Class features (movement, stability)
- Recency features (days since last run, optimal layoff)
- Weight/Age features (carried weight, age value, gender)
- Market features (odds, implied probability, favoritism)

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Feature version constant
FEATURE_VERSION = "v12"


class V12FeatureEngineer:
    """
    VELO v12 Feature Engineering Pipeline
    
    Transforms raw racing data into 61+ engineered features for ML models.
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        self.feature_count = 0
        self.core_features = ['ran', 'num', 'age', 'rpr', 'or', 'ts', 'wgt_num', 'draw']
        self.schema = self._load_schema(schema_path)
        
    def _load_schema(self, schema_path: Optional[str] = None) -> Dict:
        """Load feature schema from JSON file."""
        if schema_path is None:
            schema_path = Path(__file__).parent / "feature_schema_v12.json"
        
        try:
            with open(schema_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Schema file not found: {schema_path}. Proceeding without schema validation.")
            return {}
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names from schema (contract enforcement)."""
        if not self.schema:
            return self.get_feature_list()
        return [f['name'] for f in self.schema.get('features', [])]
    
    def validate_schema(self, df: pd.DataFrame) -> bool:
        """Validate that DataFrame matches feature schema exactly."""
        if not self.schema:
            logger.warning("No schema loaded. Skipping validation.")
            return True
        
        schema_features = set(self.get_feature_names())
        df_features = set(df.columns) - {'win', 'place'}  # Exclude targets
        
        missing = schema_features - df_features
        extra = df_features - schema_features
        
        if missing:
            logger.error(f"Missing features: {missing}")
            return False
        
        if extra:
            logger.error(f"Extra features not in schema: {extra}")
            return False
        
        logger.info("✓ Schema validation passed")
        return True
        
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean raw data: handle en-dashes, convert to numeric, parse weights."""
        logger.info("Cleaning data...")
        
        # Clean en-dash and convert to numeric
        for col in ['rpr', 'or', 'ts', 'wgt']:
            if col in df.columns:
                df[col] = df[col].replace('–', np.nan)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert weight to numeric pounds
        if 'wgt' in df.columns:
            df['wgt_num'] = df['wgt'].apply(self._parse_weight)
        
        logger.info(f"  ✓ Cleaned: {len(df):,} rows")
        return df
    
    @staticmethod
    def _parse_weight(w) -> Optional[float]:
        """Parse weight from stones-pounds format to total pounds."""
        if pd.isna(w):
            return np.nan
        try:
            if isinstance(w, str) and '-' in w:
                stones, lbs = w.split('-')
                return int(stones) * 14 + int(lbs)
            return float(w)
        except:
            return np.nan
    
    def create_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create win/place target variables."""
        logger.info("Creating win/place targets...")
        
        if 'pos' in df.columns:
            df['pos_num'] = pd.to_numeric(df['pos'], errors='coerce')
            df['win'] = (df['pos_num'] == 1).astype(int)
            df['place'] = (df['pos_num'] <= 3).astype(int)
        else:
            df['win'] = 0
            df['place'] = 0
        
        logger.info("  ✓ Targets created")
        return df
    
    def build_form_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build form features: win/place rates, consistency, improvement trend."""
        logger.info("Building form features...")
        
        # Form last N races
        for n in [3, 5, 10]:
            df[f'form_last_{n}'] = df.groupby('horse')['win'].transform(
                lambda x: x.rolling(n, min_periods=1).mean().shift(1)
            )
            df[f'wins_last_{n}'] = df.groupby('horse')['win'].transform(
                lambda x: x.rolling(n, min_periods=1).sum().shift(1)
            )
            df[f'places_last_{n}'] = df.groupby('horse')['place'].transform(
                lambda x: x.rolling(n, min_periods=1).sum().shift(1)
            )
        
        # Consistency score (std of finish positions)
        df['consistency_score'] = df.groupby('horse')['ran'].transform(
            lambda x: x.rolling(10, min_periods=3).std().shift(1)
        )
        
        # Improvement trend (RPR change)
        df['improvement_trend'] = df.groupby('horse')['rpr'].transform(
            lambda x: x.diff().rolling(3, min_periods=1).mean().shift(1)
        )
        
        logger.info("  ✓ Form features built")
        return df
    
    def build_pace_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build pace features (simplified - would need sectional data for full implementation)."""
        logger.info("Building pace features...")
        
        # Placeholder pace features (would need sectional data)
        df['early_pace_rating'] = df['rpr'] * 0.9  # Simplified
        df['late_pace_rating'] = df['rpr'] * 1.1
        df['pace_style'] = np.where(df['early_pace_rating'] > df['late_pace_rating'], 1, 0)
        df['sectional_avg'] = (df['early_pace_rating'] + df['late_pace_rating']) / 2
        
        logger.info("  ✓ Pace features built")
        return df
    
    def build_draw_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build draw features: bias, advantage, percentile."""
        logger.info("Building draw features...")
        
        # Draw bias (win rate by draw position)
        draw_bias = df.groupby(['course', 'draw'])['win'].transform('mean')
        df['draw_bias'] = draw_bias
        
        # Draw advantage
        df['draw_advantage'] = df['draw'] < (df['num'] / 2)  # Low draw advantage
        
        # Draw percentile
        df['draw_percentile'] = df.groupby('race_id')['draw'].rank(pct=True)
        
        logger.info("  ✓ Draw features built")
        return df
    
    def build_entity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build trainer/jockey/sire features: strike rates, ROI."""
        logger.info("Building trainer/jockey/sire features...")
        
        # ROI and strike rates
        for entity in ['jockey', 'trainer', 'sire']:
            if entity in df.columns:
                # Strike rate
                df[f'{entity}_strike_rate'] = df.groupby(entity)['win'].transform('mean')
                
                # ROI (placeholder - would need odds data)
                df[f'{entity}_roi'] = df.groupby(entity)['win'].transform('mean') - 0.15  # Simplified
        
        # Jockey-trainer combo
        if 'jockey' in df.columns and 'trainer' in df.columns:
            df['jockey_trainer_combo_roi'] = df.groupby(['jockey', 'trainer'])['win'].transform('mean') - 0.15
        
        logger.info("  ✓ Trainer/jockey/sire features built")
        return df
    
    def build_course_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build course/going/distance features."""
        logger.info("Building course/going/distance features...")
        
        # Going preference
        if 'going' in df.columns:
            df['going_preference'] = df.groupby(['horse', 'going'])['win'].transform('mean')
            df['going_win_rate'] = df.groupby('going')['win'].transform('mean')
            df['going_mismatch'] = (df['going_preference'] < df['going_win_rate']).astype(int)
        
        # Course form
        if 'course' in df.columns:
            df['course_form'] = df.groupby(['horse', 'course'])['win'].transform('mean')
            df['course_wins'] = df.groupby(['horse', 'course'])['win'].transform('sum')
        
        # Distance form
        if 'dist' in df.columns:
            df['distance_form'] = df.groupby(['horse', 'dist'])['win'].transform('mean')
            df['distance_wins'] = df.groupby(['horse', 'dist'])['win'].transform('sum')
        
        # Course-distance form
        if 'course' in df.columns and 'dist' in df.columns:
            df['course_distance_form'] = df.groupby(['horse', 'course', 'dist'])['win'].transform('mean')
        
        # Track type form
        if 'type' in df.columns:
            df['track_type_form'] = df.groupby(['horse', 'type'])['win'].transform('mean')
        
        logger.info("  ✓ Course/going/distance features built")
        return df
    
    def build_class_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build class features (simplified - would need class ratings)."""
        logger.info("Building class features...")
        
        # Class movement (placeholder - would need class ratings)
        df['class_movement'] = 0  # Simplified
        df['class_drop_wins'] = 0
        df['class_stability'] = 1
        
        logger.info("  ✓ Class features built")
        return df
    
    def build_recency_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build recency features: days since last run, optimal layoff."""
        logger.info("Building recency features...")
        
        if 'date' in df.columns:
            df['days_since_last_run'] = df.groupby('horse')['date'].diff().dt.days
            df['optimal_layoff'] = ((df['days_since_last_run'] >= 14) & 
                                   (df['days_since_last_run'] <= 56)).astype(int)
            df['too_fresh'] = (df['days_since_last_run'] < 7).astype(int)
            df['too_stale'] = (df['days_since_last_run'] > 90).astype(int)
        
        logger.info("  ✓ Recency features built")
        return df
    
    def build_weight_age_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build weight/age features."""
        logger.info("Building weight/age features...")
        
        df['weight_carried'] = df['wgt_num']
        df['weight_vs_avg'] = df.groupby('race_id')['wgt_num'].transform(lambda x: x - x.mean())
        df['age_value'] = df['age'] / df['age'].max()
        df['age_optimal'] = ((df['age'] >= 4) & (df['age'] <= 7)).astype(int)
        
        # Gender features
        if 'sex' in df.columns:
            df['is_gelding'] = (df['sex'] == 'G').astype(int)
            df['is_mare'] = (df['sex'] == 'M').astype(int)
        
        logger.info("  ✓ Weight/age features built")
        return df
    
    def build_market_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build market features (placeholder - would need actual odds data)."""
        logger.info("Building market features...")
        
        # Placeholder odds features (would need actual odds data)
        df['odds_decimal'] = 8.0  # Default
        df['implied_prob'] = 1 / df['odds_decimal']
        df['odds_rank'] = df.groupby('race_id')['odds_decimal'].rank()
        df['is_favorite'] = (df['odds_rank'] == 1).astype(int)
        df['odds_drift'] = 0.0  # Placeholder
        
        logger.info("  ✓ Market features built")
        return df
    
    def get_feature_list(self) -> List[str]:
        """Get list of all engineered features."""
        form_features = [f'form_last_{n}' for n in [3, 5, 10]] + \
                       [f'wins_last_{n}' for n in [3, 5, 10]] + \
                       [f'places_last_{n}' for n in [3, 5, 10]] + \
                       ['consistency_score', 'improvement_trend']
        
        pace_features = ['early_pace_rating', 'late_pace_rating', 'pace_style', 'sectional_avg']
        
        draw_features = ['draw_bias', 'draw_advantage', 'draw_percentile']
        
        entity_features = ['jockey_roi', 'jockey_strike_rate', 'trainer_roi', 
                          'trainer_strike_rate', 'sire_roi', 'jockey_trainer_combo_roi']
        
        course_features = ['going_preference', 'going_win_rate', 'going_mismatch', 
                          'course_form', 'course_wins', 'distance_form', 'distance_wins', 
                          'course_distance_form', 'track_type_form']
        
        class_features = ['class_movement', 'class_drop_wins', 'class_stability']
        
        recency_features = ['days_since_last_run', 'optimal_layoff', 'too_fresh', 'too_stale']
        
        weight_age_features = ['weight_carried', 'weight_vs_avg', 'age_value', 
                              'age_optimal', 'is_gelding', 'is_mare']
        
        market_features = ['odds_decimal', 'implied_prob', 'odds_rank', 
                          'is_favorite', 'odds_drift']
        
        return (self.core_features + form_features + pace_features + draw_features + 
                entity_features + course_features + class_features + recency_features + 
                weight_age_features + market_features)
    
    def transform(self, df: pd.DataFrame, output_path: Optional[str] = None) -> pd.DataFrame:
        """
        Full feature engineering pipeline.
        
        Args:
            df: Raw racing data DataFrame
            output_path: Optional path to save output parquet file
            
        Returns:
            DataFrame with engineered features
        """
        logger.info("="*80)
        logger.info("VELO v12 FEATURE ENGINEERING PIPELINE")
        logger.info("="*80)
        logger.info(f"Start: {datetime.now()}")
        logger.info(f"Input rows: {len(df):,}")
        
        # Sort by date for time-series features
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.sort_values(['horse', 'date']).reset_index(drop=True)
        
        # Clean data
        df = self.clean_data(df)
        
        # Create targets
        df = self.create_targets(df)
        
        # Build all feature groups
        df = self.build_form_features(df)
        df = self.build_pace_features(df)
        df = self.build_draw_features(df)
        df = self.build_entity_features(df)
        df = self.build_course_features(df)
        df = self.build_class_features(df)
        df = self.build_recency_features(df)
        df = self.build_weight_age_features(df)
        df = self.build_market_features(df)
        
        # Select final features
        all_features = self.get_feature_list()
        final_features = [f for f in all_features if f in df.columns] + ['win', 'place']
        
        df_v12 = df[final_features].copy()
        
        # Drop rows with too many NaNs
        df_v12 = df_v12.dropna(thresh=len(final_features) * 0.7)  # Keep rows with 70%+ data
        
        self.feature_count = len(final_features)
        
        # Validate schema
        if not self.validate_schema(df_v12):
            raise ValueError("Feature schema validation failed. Output does not match contract.")
        
        # Save if output path provided
        if output_path:
            df_v12.to_parquet(output_path, index=False)
            logger.info(f"  ✓ Saved: {output_path}")
        
        logger.info("="*80)
        logger.info("v12 FEATURE ENGINEERING COMPLETE")
        logger.info("="*80)
        logger.info(f"Output rows: {len(df_v12):,}")
        logger.info(f"Features: {self.feature_count}")
        logger.info(f"End: {datetime.now()}")
        
        return df_v12


def main():
    """Example usage of V12FeatureEngineer."""
    # Load raw data
    df = pd.read_csv("/path/to/raceform.csv", low_memory=False)
    
    # Initialize feature engineer
    engineer = V12FeatureEngineer()
    
    # Transform data
    df_v12 = engineer.transform(df, output_path="/path/to/output.parquet")
    
    print(f"Engineered {engineer.feature_count} features from {len(df):,} rows")


if __name__ == "__main__":
    main()
