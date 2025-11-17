"""
Unified Schema Definition for VÉLØ Oracle Feature Engineering

This module defines the canonical schema for all feature engineering operations.
No ad-hoc columns. Every feature is documented, typed, and validated.

Author: VÉLØ Oracle Team
Version: 2.0
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class FeatureType(Enum):
    """Feature type classification"""
    RATING = "rating"              # Official ratings (OR, RPR, TS)
    FORM = "form"                  # Recent performance
    CLASS = "class"                # Race class and quality
    DISTANCE = "distance"          # Distance-related
    GOING = "going"                # Ground conditions
    COURSE = "course"              # Course characteristics
    TRAINER = "trainer"            # Trainer statistics
    JOCKEY = "jockey"              # Jockey statistics
    PACE = "pace"                  # Pace analysis
    WEIGHT = "weight"              # Weight carried
    AGE = "age"                    # Horse age
    MARKET = "market"              # Market-derived
    TEMPORAL = "temporal"          # Time-based
    DERIVED = "derived"            # Engineered features


@dataclass
class FeatureDefinition:
    """
    Definition of a single feature in the unified schema.
    
    Attributes:
        name: Feature column name (snake_case)
        type: Feature type classification
        dtype: Expected pandas dtype
        description: Human-readable description
        required: Whether feature is required for training
        nullable: Whether NaN values are allowed
        default_value: Default value for missing data
        validation_range: (min, max) for numeric features
    """
    name: str
    type: FeatureType
    dtype: str
    description: str
    required: bool = True
    nullable: bool = False
    default_value: Optional[float] = None
    validation_range: Optional[tuple] = None


# ============================================================================
# RAW DATA SCHEMA (from raceform.csv)
# ============================================================================

RAW_SCHEMA = [
    # Identifiers
    FeatureDefinition("date", FeatureType.TEMPORAL, "datetime64[ns]", "Race date"),
    FeatureDefinition("course", FeatureType.COURSE, "object", "Course name"),
    FeatureDefinition("race_id", FeatureType.TEMPORAL, "object", "Unique race identifier"),
    FeatureDefinition("num", FeatureType.FORM, "int64", "Runner number in race"),
    
    # Horse identifiers
    FeatureDefinition("horse", FeatureType.FORM, "object", "Horse name"),
    FeatureDefinition("age", FeatureType.AGE, "int64", "Horse age in years", validation_range=(2, 15)),
    
    # Connections
    FeatureDefinition("trainer", FeatureType.TRAINER, "object", "Trainer name"),
    FeatureDefinition("jockey", FeatureType.JOCKEY, "object", "Jockey name"),
    
    # Race characteristics
    FeatureDefinition("class", FeatureType.CLASS, "int64", "Race class (1-7)", validation_range=(1, 7)),
    FeatureDefinition("dist", FeatureType.DISTANCE, "int64", "Distance in yards"),
    FeatureDefinition("going", FeatureType.GOING, "object", "Going description"),
    FeatureDefinition("pattern", FeatureType.CLASS, "object", "Race pattern/type"),
    
    # Ratings
    FeatureDefinition("or_int", FeatureType.RATING, "float64", "Official Rating", nullable=True),
    FeatureDefinition("rpr_int", FeatureType.RATING, "float64", "Racing Post Rating", nullable=True),
    FeatureDefinition("ts_int", FeatureType.RATING, "float64", "Topspeed Rating", nullable=True),
    
    # Weight
    FeatureDefinition("lbs", FeatureType.WEIGHT, "float64", "Weight carried in lbs", nullable=True),
    
    # Market
    FeatureDefinition("sp_decimal", FeatureType.MARKET, "float64", "Starting price (decimal)", nullable=True),
    
    # Result
    FeatureDefinition("pos_int", FeatureType.FORM, "int64", "Finishing position", nullable=True),
    FeatureDefinition("btn_int", FeatureType.FORM, "float64", "Beaten distance in lengths", nullable=True),
]


# ============================================================================
# ENGINEERED FEATURE SCHEMA (for SQPE)
# ============================================================================

SQPE_FEATURES = [
    # Rating features
    FeatureDefinition("rating_or_norm", FeatureType.RATING, "float64", "Normalized OR (0-1)"),
    FeatureDefinition("rating_rpr_norm", FeatureType.RATING, "float64", "Normalized RPR (0-1)"),
    FeatureDefinition("rating_ts_norm", FeatureType.RATING, "float64", "Normalized TS (0-1)"),
    FeatureDefinition("rating_avg", FeatureType.RATING, "float64", "Average of all ratings"),
    FeatureDefinition("rating_std", FeatureType.RATING, "float64", "Std dev of ratings (consistency)"),
    FeatureDefinition("rating_best", FeatureType.RATING, "float64", "Best rating"),
    
    # Form features
    FeatureDefinition("form_last_pos", FeatureType.FORM, "float64", "Last finishing position"),
    FeatureDefinition("form_avg_pos_3", FeatureType.FORM, "float64", "Avg position last 3 runs"),
    FeatureDefinition("form_avg_pos_5", FeatureType.FORM, "float64", "Avg position last 5 runs"),
    FeatureDefinition("form_wins_3", FeatureType.FORM, "int64", "Wins in last 3 runs"),
    FeatureDefinition("form_wins_5", FeatureType.FORM, "int64", "Wins in last 5 runs"),
    FeatureDefinition("form_places_3", FeatureType.FORM, "int64", "Top 3 finishes in last 3 runs"),
    
    # Class features
    FeatureDefinition("class_current", FeatureType.CLASS, "int64", "Current race class"),
    FeatureDefinition("class_avg_3", FeatureType.CLASS, "float64", "Avg class last 3 runs"),
    FeatureDefinition("class_delta", FeatureType.CLASS, "float64", "Class change (negative = drop)"),
    FeatureDefinition("class_win_rate", FeatureType.CLASS, "float64", "Win rate at this class"),
    
    # Distance features
    FeatureDefinition("dist_current", FeatureType.DISTANCE, "float64", "Current distance (normalized)"),
    FeatureDefinition("dist_avg_3", FeatureType.DISTANCE, "float64", "Avg distance last 3 runs"),
    FeatureDefinition("dist_delta", FeatureType.DISTANCE, "float64", "Distance change"),
    FeatureDefinition("dist_win_rate", FeatureType.DISTANCE, "float64", "Win rate at similar distance"),
    
    # Going features
    FeatureDefinition("going_encoded", FeatureType.GOING, "int64", "Going category (0-4)"),
    FeatureDefinition("going_win_rate", FeatureType.GOING, "float64", "Win rate on this going"),
    
    # Course features
    FeatureDefinition("course_runs", FeatureType.COURSE, "int64", "Runs at this course"),
    FeatureDefinition("course_win_rate", FeatureType.COURSE, "float64", "Win rate at this course"),
    
    # Trainer features (basic - TIE has more)
    FeatureDefinition("trainer_win_rate", FeatureType.TRAINER, "float64", "Trainer overall win rate"),
    FeatureDefinition("trainer_recent_win_rate", FeatureType.TRAINER, "float64", "Trainer win rate last 90 days"),
    
    # Jockey features
    FeatureDefinition("jockey_win_rate", FeatureType.JOCKEY, "float64", "Jockey overall win rate"),
    FeatureDefinition("jockey_trainer_combo_wr", FeatureType.JOCKEY, "float64", "Jockey-trainer combo win rate"),
    
    # Weight features
    FeatureDefinition("weight_lbs", FeatureType.WEIGHT, "float64", "Weight carried"),
    FeatureDefinition("weight_delta", FeatureType.WEIGHT, "float64", "Weight change vs last run"),
    
    # Age features
    FeatureDefinition("age_years", FeatureType.AGE, "int64", "Horse age"),
    FeatureDefinition("age_optimal", FeatureType.AGE, "float64", "Distance from optimal age (5-7)"),
    
    # Temporal features
    FeatureDefinition("days_since_last_run", FeatureType.TEMPORAL, "int64", "Days since last run"),
    FeatureDefinition("runs_last_30d", FeatureType.TEMPORAL, "int64", "Runs in last 30 days"),
    FeatureDefinition("runs_last_90d", FeatureType.TEMPORAL, "int64", "Runs in last 90 days"),
    
    # Market features (if available)
    FeatureDefinition("market_rank", FeatureType.MARKET, "int64", "Market rank (1 = favorite)", nullable=True),
    FeatureDefinition("market_prob", FeatureType.MARKET, "float64", "Implied probability from odds", nullable=True),
]


# ============================================================================
# TIE FEATURE SCHEMA
# ============================================================================

TIE_FEATURES = [
    # Trainer statistics
    FeatureDefinition("trainer_runs_clipped", FeatureType.TRAINER, "int64", "Trainer total runs (clipped 0-200)"),
    FeatureDefinition("trainer_win_rate", FeatureType.TRAINER, "float64", "Trainer overall win rate"),
    FeatureDefinition("trainer_recent_runs_clipped", FeatureType.TRAINER, "int64", "Trainer runs last 90d (clipped 0-50)"),
    FeatureDefinition("trainer_recent_win_rate", FeatureType.TRAINER, "float64", "Trainer win rate last 90d"),
    
    # Intent signals
    FeatureDefinition("days_since_run", FeatureType.TEMPORAL, "int64", "Days since last run (clipped -60 to 365)"),
    FeatureDefinition("class_delta", FeatureType.CLASS, "float64", "Class change (negative = drop, clipped)"),
    FeatureDefinition("jockey_change_rank", FeatureType.JOCKEY, "float64", "Jockey upgrade signal (clipped)"),
]


# ============================================================================
# TARGET SCHEMA
# ============================================================================

TARGET_SCHEMA = [
    FeatureDefinition("won", FeatureType.DERIVED, "int64", "Binary target: 1 = winner, 0 = loser"),
    FeatureDefinition("placed", FeatureType.DERIVED, "int64", "Binary: 1 = top 3, 0 = outside top 3"),
]


# ============================================================================
# SCHEMA UTILITIES
# ============================================================================

def get_feature_names(schema: List[FeatureDefinition]) -> List[str]:
    """Extract feature names from schema."""
    return [f.name for f in schema]


def get_required_features(schema: List[FeatureDefinition]) -> List[str]:
    """Get list of required feature names."""
    return [f.name for f in schema if f.required]


def get_features_by_type(schema: List[FeatureDefinition], feature_type: FeatureType) -> List[str]:
    """Get feature names of a specific type."""
    return [f.name for f in schema if f.type == feature_type]


def validate_dataframe(df, schema: List[FeatureDefinition], strict: bool = False) -> Dict[str, List[str]]:
    """
    Validate DataFrame against schema.
    
    Args:
        df: DataFrame to validate
        schema: Schema definition
        strict: If True, raise error on validation failure
    
    Returns:
        Dict with 'missing', 'type_mismatch', 'range_violation' keys
    """
    issues = {
        'missing': [],
        'type_mismatch': [],
        'range_violation': [],
    }
    
    for feature_def in schema:
        # Check if column exists
        if feature_def.name not in df.columns:
            if feature_def.required:
                issues['missing'].append(feature_def.name)
            continue
        
        # Check dtype (basic check)
        # Note: More sophisticated dtype validation could be added
        
        # Check range for numeric features
        if feature_def.validation_range is not None:
            min_val, max_val = feature_def.validation_range
            col_min = df[feature_def.name].min()
            col_max = df[feature_def.name].max()
            
            if col_min < min_val or col_max > max_val:
                issues['range_violation'].append(
                    f"{feature_def.name}: [{col_min}, {col_max}] outside [{min_val}, {max_val}]"
                )
    
    if strict and any(issues.values()):
        raise ValueError(f"Schema validation failed: {issues}")
    
    return issues


# Export commonly used feature lists
SQPE_FEATURE_NAMES = get_feature_names(SQPE_FEATURES)
TIE_FEATURE_NAMES = get_feature_names(TIE_FEATURES)
RAW_FEATURE_NAMES = get_feature_names(RAW_SCHEMA)
TARGET_NAMES = get_feature_names(TARGET_SCHEMA)

