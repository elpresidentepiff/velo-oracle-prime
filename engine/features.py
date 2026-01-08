"""
VÉLØ Feature Extraction Engine
Extracts production-grade betting features from hot window data.

Target: <1 second for 15-runner race
Author: VELO Team
Date: 2026-01-08
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def get_features_for_racecard(
    db,
    race_id: str,
    runners: Optional[List[Dict]] = None
) -> pd.DataFrame:
    """
    Returns complete feature set for all runners in a race.
    
    Target: <1 second for 15 runners
    
    Features per runner:
    - trainer_win_pct_14d/30d/90d
    - trainer_starts_30d
    - jockey_win_pct_14d/30d/90d
    - jt_combo_win_pct_365d
    - jt_combo_starts
    - course_avg_odds
    - course_volatility
    - trainer_form_trend (win_pct_14d - win_pct_90d)
    - jockey_form_trend (win_pct_14d - win_pct_90d)
    - has_combo_history (>= 3 starts)
    
    Args:
        db: Database client with execute/fetch methods
        race_id: UUID of the race
        runners: Optional list of runner dicts (not used, for compatibility)
    
    Returns:
        DataFrame with features for all runners in the race
    """
    
    # Single optimized query with LEFT JOINs for all features
    query = """
    SELECT 
        r.id as runner_id,
        r.horse_name,
        r.odds,
        r.trainer,
        r.jockey,
        ra.course,
        ra.distance,
        
        -- Trainer features
        t14.win_pct as trainer_win_pct_14d,
        t30.win_pct as trainer_win_pct_30d,
        t90.win_pct as trainer_win_pct_90d,
        t30.starts as trainer_starts_30d,
        
        -- Jockey features
        j14.win_pct as jockey_win_pct_14d,
        j30.win_pct as jockey_win_pct_30d,
        j90.win_pct as jockey_win_pct_90d,
        
        -- Combo features
        jt.win_pct as jt_combo_win_pct_365d,
        jt.starts as jt_combo_starts,
        
        -- Course features
        cd.avg_winning_odds as course_avg_odds,
        cd.odds_volatility as course_volatility
        
    FROM runners r
    JOIN races ra ON r.race_id = ra.id
    LEFT JOIN trainer_stats_14d t14 ON r.trainer = t14.trainer
    LEFT JOIN trainer_stats_30d t30 ON r.trainer = t30.trainer
    LEFT JOIN trainer_stats_90d t90 ON r.trainer = t90.trainer
    LEFT JOIN jockey_stats_14d j14 ON r.jockey = j14.jockey
    LEFT JOIN jockey_stats_30d j30 ON r.jockey = j30.jockey
    LEFT JOIN jockey_stats_90d j90 ON r.jockey = j90.jockey
    LEFT JOIN jt_combo_stats_365d jt 
        ON r.jockey = jt.jockey AND r.trainer = jt.trainer
    LEFT JOIN course_distance_stats_36m cd
        ON ra.course = cd.course 
        AND CASE 
            WHEN CAST(REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') AS INTEGER) < 1200 THEN 'sprint'
            WHEN CAST(REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') AS INTEGER) < 1600 THEN 'mile'
            WHEN CAST(REGEXP_REPLACE(ra.distance, '[^0-9]', '', 'g') AS INTEGER) < 2000 THEN 'middle'
            ELSE 'staying'
        END = cd.distance_band
    WHERE ra.id = $1
    """
    
    try:
        # Execute query
        if hasattr(db, 'fetch'):
            # asyncpg-style client
            results = await db.fetch(query, race_id)
        elif hasattr(db, 'execute'):
            # Supabase-style client
            response = db.table('runners').select('*').eq('race_id', race_id).execute()
            # For Supabase, we need to do manual joins - fallback to simpler query
            logger.warning("Using fallback query for Supabase client")
            results = response.data
        else:
            raise ValueError("Unsupported database client type")
        
        # Convert to DataFrame
        if not results:
            logger.warning(f"No runners found for race_id: {race_id}")
            return pd.DataFrame()
        
        df = pd.DataFrame([dict(r) for r in results])
        
        # Derived features
        df['trainer_form_trend'] = (
            df.get('trainer_win_pct_14d', 0) - df.get('trainer_win_pct_90d', 0)
        )
        df['jockey_form_trend'] = (
            df.get('jockey_win_pct_14d', 0) - df.get('jockey_win_pct_90d', 0)
        )
        df['has_combo_history'] = df.get('jt_combo_starts', 0) >= 3
        
        # Fill NaNs (new trainers/jockeys with no history)
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        df[numeric_cols] = df[numeric_cols].fillna(0.0)
        
        logger.info(f"Extracted features for {len(df)} runners in race {race_id}")
        return df
        
    except Exception as e:
        logger.error(f"Error extracting features for race {race_id}: {e}")
        raise


async def get_features_batch(
    db,
    race_ids: List[str]
) -> Dict[str, pd.DataFrame]:
    """
    Extract features for multiple races in batch.
    
    Args:
        db: Database client
        race_ids: List of race UUIDs
    
    Returns:
        Dictionary mapping race_id -> feature DataFrame
    """
    results = {}
    
    for race_id in race_ids:
        try:
            df = await get_features_for_racecard(db, race_id)
            results[race_id] = df
        except Exception as e:
            logger.error(f"Failed to extract features for race {race_id}: {e}")
            results[race_id] = pd.DataFrame()
    
    return results


def calculate_distance_band(distance_text: str) -> str:
    """
    Convert distance text to distance band category.
    
    Args:
        distance_text: Distance string like "1m 2f" or "1200m"
    
    Returns:
        Distance band: 'sprint', 'mile', 'middle', or 'staying'
    """
    if not distance_text:
        return 'unknown'
    
    try:
        # Extract numeric value
        import re
        numeric = re.sub(r'[^0-9]', '', distance_text)
        if not numeric:
            return 'unknown'
        
        distance_m = int(numeric)
        
        if distance_m < 1200:
            return 'sprint'
        elif distance_m < 1600:
            return 'mile'
        elif distance_m < 2000:
            return 'middle'
        else:
            return 'staying'
    except:
        return 'unknown'
