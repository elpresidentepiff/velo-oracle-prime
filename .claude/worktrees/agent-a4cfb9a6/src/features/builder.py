"""
Feature Builder - Modular Feature Engineering Pipeline

This module provides a production-grade feature engineering system with:
- Modular extractors for each feature type
- Unified schema compliance
- Comprehensive logging and validation
- Testable, documented components

Author: VÉLØ Oracle Team
Version: 2.0
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

from .schema import (
    SQPE_FEATURE_NAMES,
    TIE_FEATURE_NAMES,
    TARGET_NAMES,
    validate_dataframe,
    SQPE_FEATURES,
    TIE_FEATURES,
    TARGET_SCHEMA,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Feature Extractor Base Class
# ============================================================================

class FeatureExtractor:
    """
    Base class for feature extractors.
    
    Each extractor is responsible for generating a specific subset of features
    from the raw data.
    """
    
    def __init__(self, name: str, cache=None):
        self.name = name
        self.cache = cache
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Extract features from raw data.
        
        Args:
            df: Current race data
            history: Historical data for lookback features
        
        Returns:
            DataFrame with extracted features
        """
        raise NotImplementedError("Subclasses must implement extract()")
    
    def validate(self, df: pd.DataFrame) -> bool:
        """Validate extracted features."""
        return True


# ============================================================================
# Rating Features
# ============================================================================

class RatingExtractor(FeatureExtractor):
    """Extract and normalize rating features (OR, RPR, TS)."""
    
    def __init__(self):
        super().__init__("RatingExtractor", cache=None)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract rating features."""
        result = df.copy()
        
        # Normalize ratings (assume 0-140 range)
        result['rating_or_norm'] = result['or_int'].fillna(0) / 140.0
        result['rating_rpr_norm'] = result['rpr_int'].fillna(0) / 140.0
        result['rating_ts_norm'] = result['ts_int'].fillna(0) / 140.0
        
        # Average rating
        ratings = result[['or_int', 'rpr_int', 'ts_int']].fillna(0)
        result['rating_avg'] = ratings.mean(axis=1)
        
        # Rating consistency (std dev)
        result['rating_std'] = ratings.std(axis=1).fillna(0)
        
        # Best rating
        result['rating_best'] = ratings.max(axis=1)
        
        self.logger.info(f"Extracted {6} rating features")
        return result


# ============================================================================
# Form Features
# ============================================================================

class FormExtractor(FeatureExtractor):
    """Extract form features from historical runs."""
    
    def __init__(self, cache=None):
        super().__init__("FormExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract form features."""
        result = df.copy()

        # Use cache if available
        if self.cache is not None:
            form_features = []
            for idx, row in df.iterrows():
                horse = row['horse']
                stats = self.cache.form_stats.get(horse, {})
                
                form_features.append({
                    'form_last_pos': stats.get('last_pos', 0.0),
                    'form_avg_pos_3': stats.get('avg_pos_3', 0.0),
                    'form_avg_pos_5': stats.get('avg_pos_5', 0.0),
                    'form_wins_3': stats.get('wins_3', 0),
                    'form_wins_5': stats.get('wins_5', 0),
                    'form_places_3': stats.get('places_3', 0),
                })
            
            form_df = pd.DataFrame(form_features, index=df.index)
            result = pd.concat([result, form_df], axis=1)
            self.logger.info(f"Extracted {6} form features (from cache)")
            return result
        
        # Fallback to history-based extraction

        
        if history is None or history.empty:
            self.logger.warning("No history provided - using default form features")
            result['form_last_pos'] = 0.0
            result['form_avg_pos_3'] = 0.0
            result['form_avg_pos_5'] = 0.0
            result['form_wins_3'] = 0
            result['form_wins_5'] = 0
            result['form_places_3'] = 0
            return result
        
        # For each horse, get last N runs
        form_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            
            # Get horse history before current race
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ].sort_values('date', ascending=False)
            
            if len(horse_hist) == 0:
                # No history
                form_features.append({
                    'form_last_pos': 0.0,
                    'form_avg_pos_3': 0.0,
                    'form_avg_pos_5': 0.0,
                    'form_wins_3': 0,
                    'form_wins_5': 0,
                    'form_places_3': 0,
                })
                continue
            
            # Last position
            last_pos = horse_hist.iloc[0]['pos_int'] if pd.notna(horse_hist.iloc[0]['pos_int']) else 0
            
            # Average positions
            last_3 = horse_hist.head(3)['pos_int'].fillna(0)
            last_5 = horse_hist.head(5)['pos_int'].fillna(0)
            
            avg_pos_3 = last_3.mean() if len(last_3) > 0 else 0.0
            avg_pos_5 = last_5.mean() if len(last_5) > 0 else 0.0
            
            # Wins
            wins_3 = (last_3 == 1).sum()
            wins_5 = (last_5 == 1).sum()
            
            # Places (top 3)
            places_3 = (last_3 <= 3).sum()
            
            form_features.append({
                'form_last_pos': float(last_pos),
                'form_avg_pos_3': avg_pos_3,
                'form_avg_pos_5': avg_pos_5,
                'form_wins_3': wins_3,
                'form_wins_5': wins_5,
                'form_places_3': places_3,
            })
        
        # Merge back
        form_df = pd.DataFrame(form_features, index=df.index)
        result = pd.concat([result, form_df], axis=1)
        
        self.logger.info(f"Extracted {6} form features for {len(df)} runners")
        return result


# ============================================================================
# Class Features
# ============================================================================

class ClassExtractor(FeatureExtractor):
    """Extract class-related features."""
    
    def __init__(self, cache=None):
        super().__init__("ClassExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract class features."""
        result = df.copy()
        
        result['class_current'] = result['class'].fillna(4)  # Default to class 4
        
        if history is None or history.empty:
            result['class_avg_3'] = result['class_current']
            result['class_delta'] = 0.0
            result['class_win_rate'] = 0.0
            return result
        
        class_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            current_class = row['class'] if pd.notna(row['class']) else 4
            
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ].sort_values('date', ascending=False)
            
            if len(horse_hist) == 0:
                class_features.append({
                    'class_avg_3': current_class,
                    'class_delta': 0.0,
                    'class_win_rate': 0.0,
                })
                continue
            
            # Average class last 3 runs
            last_3_class = horse_hist.head(3)['class'].fillna(4)
            class_avg_3 = last_3_class.mean()
            
            # Class delta (negative = class drop = easier race)
            class_delta = current_class - class_avg_3
            
            # Win rate at this class
            same_class = horse_hist[horse_hist['class'] == current_class]
            if len(same_class) > 0:
                class_win_rate = (same_class['pos_int'] == 1).sum() / len(same_class)
            else:
                class_win_rate = 0.0
            
            class_features.append({
                'class_avg_3': class_avg_3,
                'class_delta': class_delta,
                'class_win_rate': class_win_rate,
            })
        
        class_df = pd.DataFrame(class_features, index=df.index)
        result = pd.concat([result, class_df], axis=1)
        
        self.logger.info(f"Extracted {4} class features")
        return result


# ============================================================================
# Distance Features
# ============================================================================

class DistanceExtractor(FeatureExtractor):
    """Extract distance-related features."""
    
    def __init__(self, cache=None):
        super().__init__("DistanceExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract distance features."""
        result = df.copy()
        
        # Normalize distance (typical range 1000-4000 yards)
        result['dist_current'] = result['dist'].fillna(2000) / 4000.0
        
        if history is None or history.empty:
            result['dist_avg_3'] = result['dist_current']
            result['dist_delta'] = 0.0
            result['dist_win_rate'] = 0.0
            return result
        
        dist_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            current_dist = row['dist'] if pd.notna(row['dist']) else 2000
            
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ].sort_values('date', ascending=False)
            
            if len(horse_hist) == 0:
                dist_features.append({
                    'dist_avg_3': current_dist / 4000.0,
                    'dist_delta': 0.0,
                    'dist_win_rate': 0.0,
                })
                continue
            
            # Average distance last 3 runs
            last_3_dist = horse_hist.head(3)['dist'].fillna(2000)
            dist_avg_3 = last_3_dist.mean() / 4000.0
            
            # Distance delta
            dist_delta = (current_dist - last_3_dist.mean()) / 4000.0
            
            # Win rate at similar distance (±10%)
            dist_min = current_dist * 0.9
            dist_max = current_dist * 1.1
            similar_dist = horse_hist[
                (horse_hist['dist'] >= dist_min) &
                (horse_hist['dist'] <= dist_max)
            ]
            
            if len(similar_dist) > 0:
                dist_win_rate = (similar_dist['pos_int'] == 1).sum() / len(similar_dist)
            else:
                dist_win_rate = 0.0
            
            dist_features.append({
                'dist_avg_3': dist_avg_3,
                'dist_delta': dist_delta,
                'dist_win_rate': dist_win_rate,
            })
        
        dist_df = pd.DataFrame(dist_features, index=df.index)
        result = pd.concat([result, dist_df], axis=1)
        
        self.logger.info(f"Extracted {4} distance features")
        return result


# ============================================================================
# Going Features
# ============================================================================

class GoingExtractor(FeatureExtractor):
    """Extract going (ground condition) features."""
    
    GOING_MAP = {
        'firm': 0,
        'good': 1,
        'good to firm': 1,
        'good to soft': 2,
        'soft': 3,
        'heavy': 4,
    }
    
    def __init__(self, cache=None):
        super().__init__("GoingExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract going features."""
        result = df.copy()
        
        # Encode going
        result['going_encoded'] = result['going'].str.lower().map(self.GOING_MAP).fillna(1)
        
        if history is None or history.empty:
            result['going_win_rate'] = 0.0
            return result
        
        going_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            current_going = result.loc[idx, 'going_encoded']  # Get from result, not row
            
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ]
            
            if len(horse_hist) == 0:
                going_features.append({'going_win_rate': 0.0})
                continue
            
            # Encode history going
            horse_hist = horse_hist.copy()
            horse_hist['going_encoded'] = horse_hist['going'].str.lower().map(self.GOING_MAP).fillna(1)
            
            # Win rate on this going
            same_going = horse_hist[horse_hist['going_encoded'] == current_going]
            if len(same_going) > 0:
                going_win_rate = (same_going['pos_int'] == 1).sum() / len(same_going)
            else:
                going_win_rate = 0.0
            
            going_features.append({'going_win_rate': going_win_rate})
        
        going_df = pd.DataFrame(going_features, index=df.index)
        result = pd.concat([result, going_df], axis=1)
        
        self.logger.info(f"Extracted {2} going features")
        return result


# ============================================================================
# Course Features
# ============================================================================

class CourseExtractor(FeatureExtractor):
    """Extract course-specific features."""
    
    def __init__(self, cache=None):
        super().__init__("CourseExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract course features."""
        result = df.copy()
        
        if history is None or history.empty:
            result['course_runs'] = 0
            result['course_win_rate'] = 0.0
            return result
        
        course_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            current_course = row['course']
            
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ]
            
            # Runs at this course
            course_hist = horse_hist[horse_hist['course'] == current_course]
            course_runs = len(course_hist)
            
            # Win rate at this course
            if course_runs > 0:
                course_win_rate = (course_hist['pos_int'] == 1).sum() / course_runs
            else:
                course_win_rate = 0.0
            
            course_features.append({
                'course_runs': course_runs,
                'course_win_rate': course_win_rate,
            })
        
        course_df = pd.DataFrame(course_features, index=df.index)
        result = pd.concat([result, course_df], axis=1)
        
        self.logger.info(f"Extracted {2} course features")
        return result


# ============================================================================
# Trainer Features
# ============================================================================

class TrainerExtractor(FeatureExtractor):
    """Extract trainer statistics."""
    
    def __init__(self, cache=None):
        super().__init__("TrainerExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract trainer features."""
        result = df.copy()
        
        if history is None or history.empty:
            result['trainer_win_rate'] = 0.0
            result['trainer_recent_win_rate'] = 0.0
            return result
        
        # Build trainer stats
        trainer_stats = history.groupby('trainer').agg({
            'pos_int': lambda x: (x == 1).sum() / len(x) if len(x) > 0 else 0.0
        }).rename(columns={'pos_int': 'trainer_win_rate'})
        
        # Recent stats (last 90 days)
        max_date = pd.to_datetime(history['date']).max()
        cutoff = max_date - pd.Timedelta(days=90)
        recent = history[pd.to_datetime(history['date']) >= cutoff]
        
        trainer_recent = recent.groupby('trainer').agg({
            'pos_int': lambda x: (x == 1).sum() / len(x) if len(x) > 0 else 0.0
        }).rename(columns={'pos_int': 'trainer_recent_win_rate'})
        
        # Merge
        result = result.merge(trainer_stats, left_on='trainer', right_index=True, how='left')
        result = result.merge(trainer_recent, left_on='trainer', right_index=True, how='left')
        
        result['trainer_win_rate'] = result['trainer_win_rate'].fillna(0.0)
        result['trainer_recent_win_rate'] = result['trainer_recent_win_rate'].fillna(0.0)
        
        self.logger.info(f"Extracted {2} trainer features")
        return result


# ============================================================================
# Jockey Features
# ============================================================================

class JockeyExtractor(FeatureExtractor):
    """Extract jockey statistics."""
    
    def __init__(self, cache=None):
        super().__init__("JockeyExtractor", cache=cache)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract jockey features."""
        result = df.copy()
        
        if history is None or history.empty:
            result['jockey_win_rate'] = 0.0
            result['jockey_trainer_combo_wr'] = 0.0
            return result
        
        # Jockey win rate
        jockey_stats = history.groupby('jockey').agg({
            'pos_int': lambda x: (x == 1).sum() / len(x) if len(x) > 0 else 0.0
        }).rename(columns={'pos_int': 'jockey_win_rate'})
        
        # Jockey-trainer combo win rate
        combo_stats = history.groupby(['jockey', 'trainer']).agg({
            'pos_int': lambda x: (x == 1).sum() / len(x) if len(x) > 0 else 0.0
        }).rename(columns={'pos_int': 'jockey_trainer_combo_wr'})
        
        # Merge
        result = result.merge(jockey_stats, left_on='jockey', right_index=True, how='left')
        result = result.merge(
            combo_stats,
            left_on=['jockey', 'trainer'],
            right_index=True,
            how='left'
        )
        
        result['jockey_win_rate'] = result['jockey_win_rate'].fillna(0.0)
        result['jockey_trainer_combo_wr'] = result['jockey_trainer_combo_wr'].fillna(0.0)
        
        self.logger.info(f"Extracted {2} jockey features")
        return result


# ============================================================================
# Weight Features
# ============================================================================

class WeightExtractor(FeatureExtractor):
    """Extract weight-related features."""
    
    def __init__(self):
        super().__init__("WeightExtractor", cache=None)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract weight features."""
        result = df.copy()
        
        result['weight_lbs'] = result['lbs'].fillna(130.0)  # Default weight
        
        if history is None or history.empty:
            result['weight_delta'] = 0.0
            return result
        
        weight_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            current_weight = row['lbs'] if pd.notna(row['lbs']) else 130.0
            
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ].sort_values('date', ascending=False)
            
            if len(horse_hist) == 0 or pd.isna(horse_hist.iloc[0]['lbs']):
                weight_delta = 0.0
            else:
                last_weight = horse_hist.iloc[0]['lbs']
                weight_delta = current_weight - last_weight
            
            weight_features.append({'weight_delta': weight_delta})
        
        weight_df = pd.DataFrame(weight_features, index=df.index)
        result = pd.concat([result, weight_df], axis=1)
        
        self.logger.info(f"Extracted {2} weight features")
        return result


# ============================================================================
# Age Features
# ============================================================================

class AgeExtractor(FeatureExtractor):
    """Extract age-related features."""
    
    def __init__(self):
        super().__init__("AgeExtractor", cache=None)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract age features."""
        result = df.copy()
        
        result['age_years'] = result['age'].fillna(5)
        
        # Optimal age is typically 5-7 for flat racing
        result['age_optimal'] = result['age_years'].apply(
            lambda x: abs(x - 6) if pd.notna(x) else 1
        )
        
        self.logger.info(f"Extracted {2} age features")
        return result


# ============================================================================
# Temporal Features
# ============================================================================

class TemporalExtractor(FeatureExtractor):
    """Extract temporal/recency features."""
    
    def __init__(self):
        super().__init__("TemporalExtractor", cache=None)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract temporal features."""
        result = df.copy()
        
        if history is None or history.empty:
            result['days_since_last_run'] = 30
            result['runs_last_30d'] = 0
            result['runs_last_90d'] = 0
            return result
        
        temporal_features = []
        
        for idx, row in df.iterrows():
            horse = row['horse']
            current_date = pd.to_datetime(row['date'])
            
            horse_hist = history[
                (history['horse'] == horse) &
                (pd.to_datetime(history['date']) < current_date)
            ].sort_values('date', ascending=False)
            
            if len(horse_hist) == 0:
                temporal_features.append({
                    'days_since_last_run': 30,
                    'runs_last_30d': 0,
                    'runs_last_90d': 0,
                })
                continue
            
            # Days since last run
            last_run_date = pd.to_datetime(horse_hist.iloc[0]['date'])
            days_since = (current_date - last_run_date).days
            
            # Runs in last 30/90 days
            cutoff_30 = current_date - pd.Timedelta(days=30)
            cutoff_90 = current_date - pd.Timedelta(days=90)
            
            runs_30d = len(horse_hist[pd.to_datetime(horse_hist['date']) >= cutoff_30])
            runs_90d = len(horse_hist[pd.to_datetime(horse_hist['date']) >= cutoff_90])
            
            temporal_features.append({
                'days_since_last_run': days_since,
                'runs_last_30d': runs_30d,
                'runs_last_90d': runs_90d,
            })
        
        temporal_df = pd.DataFrame(temporal_features, index=df.index)
        result = pd.concat([result, temporal_df], axis=1)
        
        self.logger.info(f"Extracted {3} temporal features")
        return result


# ============================================================================
# Market Features
# ============================================================================

class MarketExtractor(FeatureExtractor):
    """Extract market-derived features."""
    
    def __init__(self):
        super().__init__("MarketExtractor", cache=None)
    
    def extract(self, df: pd.DataFrame, history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Extract market features."""
        result = df.copy()
        
        # Market rank (1 = favorite)
        result['market_rank'] = result.groupby('race_id')['sp_decimal'].rank(method='min').fillna(0).astype(int)
        
        # Implied probability from odds
        result['market_prob'] = (1.0 / result['sp_decimal']).fillna(0.0)
        
        self.logger.info(f"Extracted {2} market features")
        return result


# ============================================================================
# Feature Builder Orchestrator
# ============================================================================

@dataclass
class FeatureBuilderConfig:
    """Configuration for FeatureBuilder."""
    validate_schema: bool = True
    log_level: str = "INFO"


class FeatureBuilder:
    """
    Orchestrates all feature extractors to build complete feature sets.
    
    This is the main entry point for feature engineering.
    """
    
    def __init__(self, config: Optional[FeatureBuilderConfig] = None, cache=None):
        self.config = config or FeatureBuilderConfig()
        self.cache = cache
        
        # Configure logging
        logging.basicConfig(level=self.config.log_level)
        self.logger = logging.getLogger(__name__)
        
        if self.cache is not None:
            self.logger.info("FeatureBuilder initialized with cache (fast mode)")
        
        # Initialize extractors (pass cache to those that support it)
        self.extractors = [
            RatingExtractor(),
            FormExtractor(cache=cache),
            ClassExtractor(cache=cache),
            DistanceExtractor(cache=cache),
            GoingExtractor(cache=cache),
            CourseExtractor(cache=cache),
            TrainerExtractor(cache=cache),
            JockeyExtractor(cache=cache),
            WeightExtractor(),
            AgeExtractor(),
            TemporalExtractor(),
            MarketExtractor(),
        ]
    
    def build_sqpe_features(
        self,
        df: pd.DataFrame,
        history: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Build complete SQPE feature set.
        
        Args:
            df: Current race data (raw schema)
            history: Historical data for lookback features
        
        Returns:
            DataFrame with SQPE features
        """
        self.logger.info(f"Building SQPE features for {len(df)} runners")
        
        # Run all extractors
        result = df.copy()
        for extractor in self.extractors:
            result = extractor.extract(result, history)
        
        # Select only SQPE features
        available_features = [f for f in SQPE_FEATURE_NAMES if f in result.columns]
        missing_features = set(SQPE_FEATURE_NAMES) - set(available_features)
        
        if missing_features:
            self.logger.warning(f"Missing SQPE features: {missing_features}")
        
        sqpe_df = result[available_features]
        
        # Validate
        if self.config.validate_schema:
            issues = validate_dataframe(sqpe_df, SQPE_FEATURES, strict=False)
            if any(issues.values()):
                self.logger.warning(f"Schema validation issues: {issues}")
        
        self.logger.info(f"Built {len(available_features)} SQPE features")
        return sqpe_df
    
    def build_tie_features(
        self,
        df: pd.DataFrame,
        history: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Build TIE feature set.
        
        Args:
            df: Current race data (raw schema)
            history: Historical data for trainer stats
        
        Returns:
            DataFrame with TIE features
        """
        self.logger.info(f"Building TIE features for {len(df)} runners")
        
        # Build trainer stats
        from ..intelligence.tie import TrainerIntentEngine
        
        if history is not None and not history.empty:
            # Prepare history for TIE
            history_prep = history.copy()
            history_prep['race_date'] = pd.to_datetime(history_prep['date'])
            history_prep['won'] = (history_prep['pos_int'] == 1).astype(int)
            
            trainer_stats = TrainerIntentEngine.build_trainer_stats(
                history_prep,
                date_col='race_date',
                trainer_col='trainer',
                won_col='won'
            )
        else:
            trainer_stats = pd.DataFrame()
        
        # Build TIE features
        df_prep = df.copy()
        df_prep['days_since_run'] = df_prep.get('days_since_last_run', 30)
        df_prep['class_delta'] = df_prep.get('class_delta', 0.0)
        df_prep['jockey_change_rank'] = 0.0  # Placeholder - would need jockey history
        
        if not trainer_stats.empty:
            tie_df = TrainerIntentEngine.build_runner_features(
                df_prep,
                trainer_stats,
                trainer_col='trainer',
                days_since_run_col='days_since_run',
                class_change_col='class_delta',
                jockey_change_col='jockey_change_rank',
            )
        else:
            # Default TIE features
            tie_df = pd.DataFrame({
                'trainer_runs_clipped': [0] * len(df),
                'trainer_win_rate': [0.0] * len(df),
                'trainer_recent_runs_clipped': [0] * len(df),
                'trainer_recent_win_rate': [0.0] * len(df),
                'days_since_run': [30] * len(df),
                'class_delta': [0.0] * len(df),
                'jockey_change_rank': [0.0] * len(df),
            }, index=df.index)
        
        self.logger.info(f"Built {len(TIE_FEATURE_NAMES)} TIE features")
        return tie_df
    
    def build_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build target variables.
        
        Args:
            df: Race data with pos_int column
        
        Returns:
            DataFrame with target columns
        """
        targets = pd.DataFrame(index=df.index)
        targets['won'] = (df['pos_int'] == 1).astype(int)
        targets['placed'] = (df['pos_int'] <= 3).astype(int)
        
        self.logger.info(f"Built {len(TARGET_NAMES)} target variables")
        return targets

