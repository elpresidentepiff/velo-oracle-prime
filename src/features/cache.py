"""
Feature Cache System - 10-20x Speedup for Historical Lookups

Pre-computes and caches trainer/jockey/course statistics to avoid
repeated O(n) scans during feature extraction.

Usage:
    cache = FeatureCache()
    cache.build_from_history(history_df, date='2015-05-01')
    
    # O(1) lookup instead of O(n) scan
    trainer_stats = cache.get_trainer_stats('Brian Ellison')
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureCache:
    """
    Pre-computed historical statistics cache.
    
    Stores:
    - Trainer stats (overall + recent)
    - Jockey stats (overall + combos)
    - Course stats (per horse)
    - Going stats (per horse)
    - Class stats (per horse)
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize feature cache.
        
        Args:
            cache_dir: Directory to store cache files. If None, uses memory only.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory caches
        self.trainer_stats = {}
        self.jockey_stats = {}
        self.course_stats = {}
        self.going_stats = {}
        self.class_stats = {}
        
        self.cache_date = None
        self.is_loaded = False
    
    def build_from_history(self, history_df: pd.DataFrame, date: str = None):
        """
        Build cache from historical data up to a given date.
        
        Args:
            history_df: Historical race data
            date: Cache cutoff date (only use data before this)
        """
        if date:
            history_df = history_df[history_df['date'] < date].copy()
        
        self.cache_date = date or history_df['date'].max()
        
        logger.info(f"Building feature cache from {len(history_df):,} historical rows")
        logger.info(f"Cache date: {self.cache_date}")
        
        # Build trainer stats
        self._build_trainer_stats(history_df)
        
        # Build jockey stats
        self._build_jockey_stats(history_df)
        
        # Build per-horse stats
        self._build_horse_stats(history_df)
        
        self.is_loaded = True
        logger.info("Feature cache built successfully")
    
    def _build_trainer_stats(self, df: pd.DataFrame):
        """Build trainer statistics."""
        logger.info("Building trainer stats...")
        
        # Overall stats
        trainer_overall = df.groupby('trainer').agg({
            'pos_int': lambda x: (x == 1).sum(),  # wins
            'race_id': 'count',  # runs
        }).rename(columns={'pos_int': 'wins', 'race_id': 'runs'})
        
        trainer_overall['win_rate'] = trainer_overall['wins'] / trainer_overall['runs']
        
        # Recent stats (last 90 days)
        recent_cutoff = pd.to_datetime(self.cache_date) - timedelta(days=90)
        df_recent = df[df['date'] >= recent_cutoff]
        
        trainer_recent = df_recent.groupby('trainer').agg({
            'pos_int': lambda x: (x == 1).sum(),
            'race_id': 'count',
        }).rename(columns={'pos_int': 'recent_wins', 'race_id': 'recent_runs'})
        
        trainer_recent['recent_win_rate'] = trainer_recent['recent_wins'] / trainer_recent['recent_runs']
        
        # Combine
        self.trainer_stats = trainer_overall.join(trainer_recent, how='outer').fillna(0).to_dict('index')
        
        logger.info(f"  Cached {len(self.trainer_stats):,} trainers")
    
    def _build_jockey_stats(self, df: pd.DataFrame):
        """Build jockey statistics."""
        logger.info("Building jockey stats...")
        
        # Overall jockey stats
        jockey_overall = df.groupby('jockey').agg({
            'pos_int': lambda x: (x == 1).sum(),
            'race_id': 'count',
        }).rename(columns={'pos_int': 'wins', 'race_id': 'runs'})
        
        jockey_overall['win_rate'] = jockey_overall['wins'] / jockey_overall['runs']
        
        # Jockey-trainer combos
        combo_stats = df.groupby(['jockey', 'trainer']).agg({
            'pos_int': lambda x: (x == 1).sum(),
            'race_id': 'count',
        }).rename(columns={'pos_int': 'wins', 'race_id': 'runs'})
        
        combo_stats['win_rate'] = combo_stats['wins'] / combo_stats['runs']
        
        self.jockey_stats = {
            'overall': jockey_overall.to_dict('index'),
            'combos': combo_stats.to_dict('index'),
        }
        
        logger.info(f"  Cached {len(jockey_overall):,} jockeys, {len(combo_stats):,} combos")
    
    def _build_horse_stats(self, df: pd.DataFrame):
        """Build per-horse statistics (course, going, class)."""
        logger.info("Building per-horse stats...")
        
        # Course stats
        course_stats = df.groupby(['horse', 'course']).agg({
            'pos_int': lambda x: (x == 1).sum(),
            'race_id': 'count',
        }).rename(columns={'pos_int': 'wins', 'race_id': 'runs'})
        
        course_stats['win_rate'] = course_stats['wins'] / course_stats['runs']
        self.course_stats = course_stats.to_dict('index')
        
        # Going stats
        going_stats = df.groupby(['horse', 'going']).agg({
            'pos_int': lambda x: (x == 1).sum(),
            'race_id': 'count',
        }).rename(columns={'pos_int': 'wins', 'race_id': 'runs'})
        
        going_stats['win_rate'] = going_stats['wins'] / going_stats['runs']
        self.going_stats = going_stats.to_dict('index')
        
        # Class stats
        class_stats = df.groupby(['horse', 'class']).agg({
            'pos_int': lambda x: (x == 1).sum(),
            'race_id': 'count',
        }).rename(columns={'pos_int': 'wins', 'race_id': 'runs'})
        
        class_stats['win_rate'] = class_stats['wins'] / class_stats['runs']
        self.class_stats = class_stats.to_dict('index')
        
        logger.info(f"  Cached course: {len(course_stats):,}, going: {len(going_stats):,}, class: {len(class_stats):,}")
    
    def get_trainer_stats(self, trainer: str) -> Dict:
        """Get trainer statistics (O(1) lookup)."""
        return self.trainer_stats.get(trainer, {
            'wins': 0,
            'runs': 0,
            'win_rate': 0.0,
            'recent_wins': 0,
            'recent_runs': 0,
            'recent_win_rate': 0.0,
        })
    
    def get_jockey_stats(self, jockey: str) -> Dict:
        """Get jockey statistics (O(1) lookup)."""
        return self.jockey_stats['overall'].get(jockey, {
            'wins': 0,
            'runs': 0,
            'win_rate': 0.0,
        })
    
    def get_jockey_trainer_stats(self, jockey: str, trainer: str) -> Dict:
        """Get jockey-trainer combo statistics (O(1) lookup)."""
        return self.jockey_stats['combos'].get((jockey, trainer), {
            'wins': 0,
            'runs': 0,
            'win_rate': 0.0,
        })
    
    def get_course_stats(self, horse: str, course: str) -> Dict:
        """Get horse course statistics (O(1) lookup)."""
        return self.course_stats.get((horse, course), {
            'wins': 0,
            'runs': 0,
            'win_rate': 0.0,
        })
    
    def get_going_stats(self, horse: str, going: str) -> Dict:
        """Get horse going statistics (O(1) lookup)."""
        return self.going_stats.get((horse, going), {
            'wins': 0,
            'runs': 0,
            'win_rate': 0.0,
        })
    
    def get_class_stats(self, horse: str, class_val: int) -> Dict:
        """Get horse class statistics (O(1) lookup)."""
        return self.class_stats.get((horse, class_val), {
            'wins': 0,
            'runs': 0,
            'win_rate': 0.0,
        })
    
    def save(self, filepath: Path):
        """Save cache to disk."""
        cache_data = {
            'trainer_stats': self.trainer_stats,
            'jockey_stats': self.jockey_stats,
            'course_stats': self.course_stats,
            'going_stats': self.going_stats,
            'class_stats': self.class_stats,
            'cache_date': self.cache_date,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(cache_data, f)
        
        logger.info(f"Cache saved to {filepath}")
    
    def load(self, filepath: Path):
        """Load cache from disk."""
        with open(filepath, 'rb') as f:
            cache_data = pickle.load(f)
        
        self.trainer_stats = cache_data['trainer_stats']
        self.jockey_stats = cache_data['jockey_stats']
        self.course_stats = cache_data['course_stats']
        self.going_stats = cache_data['going_stats']
        self.class_stats = cache_data['class_stats']
        self.cache_date = cache_data['cache_date']
        self.is_loaded = True
        
        logger.info(f"Cache loaded from {filepath} (date: {self.cache_date})")

