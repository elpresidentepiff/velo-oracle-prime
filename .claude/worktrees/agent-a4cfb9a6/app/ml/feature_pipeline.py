#!/usr/bin/env python3
"""
VELO Feature Pipeline
Wires v12 feature engineering into training + inference paths

This module provides:
- Single command to generate features for a full day card
- Persistent storage to /data/features/v12/{race_id}.parquet
- Integration with training and inference workflows
- Crash-resistant batch processing

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import logging

from .v12_feature_engineering import V12FeatureEngineer, FEATURE_VERSION

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """
    Feature generation pipeline for training and inference.
    
    Wires V12FeatureEngineer into the system with persistent storage.
    """
    
    def __init__(self, output_dir: str = "/data/features/v12"):
        self.engineer = V12FeatureEngineer()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.version = FEATURE_VERSION
        
    def generate_race_features(
        self, 
        race_obj: Dict, 
        market_obj: Optional[Dict] = None,
        race_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Generate features for a single race.
        
        Args:
            race_obj: Race data dictionary
            market_obj: Optional market data dictionary
            race_id: Optional race ID for file naming
            
        Returns:
            DataFrame with engineered features
        """
        logger.info(f"Generating features for race: {race_id or 'unknown'}")
        
        # Convert race_obj to DataFrame
        df = self._race_obj_to_df(race_obj, market_obj)
        
        # Transform with V12FeatureEngineer
        df_features = self.engineer.transform(df)
        
        # Save to persistent storage
        if race_id:
            output_path = self.output_dir / f"{race_id}.parquet"
            df_features.to_parquet(output_path, index=False)
            logger.info(f"✓ Features saved: {output_path}")
        
        return df_features
    
    def generate_day_card_features(
        self, 
        races: List[Dict], 
        markets: Optional[List[Dict]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Generate features for a full day card.
        
        Acceptance criteria: Process full day card without crashing.
        
        Args:
            races: List of race data dictionaries
            markets: Optional list of market data dictionaries
            
        Returns:
            Dictionary mapping race_id to feature DataFrame
        """
        logger.info(f"="*80)
        logger.info(f"GENERATING FEATURES FOR {len(races)} RACES")
        logger.info(f"="*80)
        
        results = {}
        errors = []
        
        for i, race in enumerate(races):
            race_id = race.get('race_id', f"race_{i}")
            market = markets[i] if markets and i < len(markets) else None
            
            try:
                df_features = self.generate_race_features(race, market, race_id)
                results[race_id] = df_features
                logger.info(f"✓ [{i+1}/{len(races)}] {race_id}: {len(df_features)} runners, {len(df_features.columns)} features")
            except Exception as e:
                logger.error(f"✗ [{i+1}/{len(races)}] {race_id}: {str(e)}")
                errors.append({'race_id': race_id, 'error': str(e)})
        
        logger.info(f"="*80)
        logger.info(f"COMPLETE: {len(results)}/{len(races)} races processed")
        if errors:
            logger.warning(f"ERRORS: {len(errors)} races failed")
            for err in errors:
                logger.warning(f"  - {err['race_id']}: {err['error']}")
        logger.info(f"="*80)
        
        return results
    
    def load_race_features(self, race_id: str) -> Optional[pd.DataFrame]:
        """
        Load pre-generated features for a race.
        
        Args:
            race_id: Race identifier
            
        Returns:
            DataFrame with features or None if not found
        """
        feature_path = self.output_dir / f"{race_id}.parquet"
        
        if not feature_path.exists():
            logger.warning(f"Features not found for race: {race_id}")
            return None
        
        df = pd.read_parquet(feature_path)
        logger.info(f"✓ Loaded features for {race_id}: {len(df)} runners")
        return df
    
    def _race_obj_to_df(
        self, 
        race_obj: Dict, 
        market_obj: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Convert race object to DataFrame for feature engineering.
        
        Args:
            race_obj: Race data dictionary
            market_obj: Optional market data dictionary
            
        Returns:
            DataFrame ready for feature engineering
        """
        # Extract runners from race object
        runners = race_obj.get('runners', [])
        
        if not runners:
            raise ValueError("No runners found in race object")
        
        # Convert to DataFrame
        df = pd.DataFrame(runners)
        
        # Add race-level fields
        for key in ['course', 'date', 'dist', 'going', 'class', 'type']:
            if key in race_obj:
                df[key] = race_obj[key]
        
        # Add market data if available
        if market_obj:
            market_df = pd.DataFrame(market_obj.get('runners', []))
            if not market_df.empty and 'runner_id' in market_df.columns:
                df = df.merge(market_df, on='runner_id', how='left', suffixes=('', '_market'))
        
        return df


def generate_features_for_training(
    data_path: str,
    output_path: str,
    sample_size: Optional[int] = None
) -> pd.DataFrame:
    """
    Generate features for model training from raw data file.
    
    Args:
        data_path: Path to raw data CSV/parquet
        output_path: Path to save engineered features
        sample_size: Optional sample size for faster iteration
        
    Returns:
        DataFrame with engineered features
    """
    logger.info(f"Loading training data from: {data_path}")
    
    # Load data
    if data_path.endswith('.parquet'):
        df = pd.read_parquet(data_path)
    else:
        df = pd.read_csv(data_path, low_memory=False)
    
    # Sample if requested
    if sample_size and len(df) > sample_size:
        logger.info(f"Sampling {sample_size:,} rows from {len(df):,}")
        df = df.sample(n=sample_size, random_state=42)
    
    # Generate features
    engineer = V12FeatureEngineer()
    df_features = engineer.transform(df, output_path=output_path)
    
    logger.info(f"✓ Training features saved: {output_path}")
    return df_features


def generate_features_for_inference(
    race_card: Dict,
    market_data: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Generate features for live inference.
    
    Args:
        race_card: Race card data
        market_data: Optional market data
        
    Returns:
        DataFrame with engineered features ready for model inference
    """
    pipeline = FeaturePipeline()
    
    # Extract race ID
    race_id = race_card.get('race_id', f"inference_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    # Generate features
    df_features = pipeline.generate_race_features(race_card, market_data, race_id)
    
    return df_features


if __name__ == "__main__":
    # Example: Generate features for full day card
    pipeline = FeaturePipeline()
    
    # Mock race data (replace with actual data source)
    races = [
        {
            'race_id': 'test_race_1',
            'course': 'Newmarket',
            'date': '2025-12-17',
            'dist': 1200,
            'going': 'Good',
            'class': 3,
            'runners': [
                {'horse': 'Horse A', 'age': 4, 'rpr': 95, 'or': 90, 'ts': 88, 'draw': 1},
                {'horse': 'Horse B', 'age': 5, 'rpr': 92, 'or': 87, 'ts': 85, 'draw': 2},
            ]
        }
    ]
    
    results = pipeline.generate_day_card_features(races)
    print(f"Generated features for {len(results)} races")
