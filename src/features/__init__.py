"""
VÉLØ Feature Engineering Module

Modular, schema-driven feature engineering for SQPE and TIE.

Author: VÉLØ Oracle Team
Version: 2.0
"""

from .schema import (
    FeatureType,
    FeatureDefinition,
    SQPE_FEATURE_NAMES,
    TIE_FEATURE_NAMES,
    RAW_FEATURE_NAMES,
    TARGET_NAMES,
    SQPE_FEATURES,
    TIE_FEATURES,
    RAW_SCHEMA,
    TARGET_SCHEMA,
    validate_dataframe,
)

from .builder import (
    FeatureBuilder,
    FeatureBuilderConfig,
    FeatureExtractor,
)

__all__ = [
    # Schema
    'FeatureType',
    'FeatureDefinition',
    'SQPE_FEATURE_NAMES',
    'TIE_FEATURE_NAMES',
    'RAW_FEATURE_NAMES',
    'TARGET_NAMES',
    'SQPE_FEATURES',
    'TIE_FEATURES',
    'RAW_SCHEMA',
    'TARGET_SCHEMA',
    'validate_dataframe',
    
    # Builder
    'FeatureBuilder',
    'FeatureBuilderConfig',
    'FeatureExtractor',
]

