"""
VÉLØ v11 - Data & Feature Fabric
Layer 1: Comprehensive feature engineering for all model families
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta


class V11DataFabric:
    """
    Transforms raw race data into structured feature blocks for v11 models
    
    Feature Blocks:
    1. Static ability features (RPR, TS, OR, best figures)
    2. Form cycle features (performance deltas, bounce risk)
    3. Intent features (trainer patterns, jockey bookings, money signals)
    4. Market microstructure (price movements, volume, spreads)
    5. Race geometry (pace, field distribution, draw, chaos)
    """
    
    def __init__(self):
        self.feature_blocks = {
            'ability': [],
            'form_cycle': [],
            'intent': [],
            'market': [],
            'geometry': []
        }
    
    def build_features(self, race_data: Dict, runner_data: List[Dict]) -> pd.DataFrame:
        """
        Build complete feature set for a race
        
        Args:
            race_data: Race metadata (track, distance, going, etc)
            runner_data: List of runners with form, odds, connections
            
        Returns:
            DataFrame with one row per runner, all feature blocks
        """
        runners = []
        
        for runner in runner_data:
            features = {}
            
            # Static ability features
            features.update(self._build_ability_features(runner))
            
            # Form cycle features
            features.update(self._build_form_cycle_features(runner))
            
            # Intent features
            features.update(self._build_intent_features(runner, race_data))
            
            # Market microstructure
            features.update(self._build_market_features(runner))
            
            # Race geometry
            features.update(self._build_geometry_features(runner, race_data, runner_data))
            
            runners.append(features)
        
        return pd.DataFrame(runners)
    
    def _build_ability_features(self, runner: Dict) -> Dict:
        """
        Block 1: Static ability features
        RPR, TS, OR history, best figures, median, variance
        """
        form = runner.get('form', [])
        
        if not form:
            return {
                'rpr_best': 0,
                'rpr_median': 0,
                'rpr_variance': 0,
                'ts_best': 0,
                'or_current': 0,
                'class_best': 0
            }
        
        rprs = [r.get('rpr', 0) for r in form if r.get('rpr')]
        
        return {
            'rpr_best': max(rprs) if rprs else 0,
            'rpr_median': np.median(rprs) if rprs else 0,
            'rpr_variance': np.var(rprs) if len(rprs) > 1 else 0,
            'ts_best': max([r.get('ts', 0) for r in form]),
            'or_current': runner.get('official_rating', 0),
            'class_best': min([r.get('class', 7) for r in form])
        }
    
    def _build_form_cycle_features(self, runner: Dict) -> Dict:
        """
        Block 2: Form cycle features
        Performance deltas, up/down curve, bounce risk, layoff
        """
        form = runner.get('form', [])
        
        if len(form) < 2:
            return {
                'form_delta_last': 0,
                'form_trend': 0,
                'bounce_risk': 0,
                'days_since_run': 999
            }
        
        # Recent performance deltas
        recent_positions = [r.get('position', 99) for r in form[:3]]
        delta = recent_positions[0] - recent_positions[1] if len(recent_positions) > 1 else 0
        
        # Trend (improving = negative, regressing = positive)
        trend = np.polyfit(range(len(recent_positions)), recent_positions, 1)[0] if len(recent_positions) > 2 else 0
        
        # Bounce risk (won last time = higher risk)
        bounce_risk = 1.0 if form[0].get('position') == 1 else 0.0
        
        # Days since last run
        last_run = form[0].get('date')
        days_since = 999
        if last_run:
            try:
                last_date = datetime.fromisoformat(last_run)
                days_since = (datetime.now() - last_date).days
            except:
                pass
        
        return {
            'form_delta_last': delta,
            'form_trend': trend,
            'bounce_risk': bounce_risk,
            'days_since_run': days_since
        }
    
    def _build_intent_features(self, runner: Dict, race_data: Dict) -> Dict:
        """
        Block 3: Intent features
        Trainer patterns, jockey bookings, class drops, stable form
        """
        trainer_stats = runner.get('trainer_stats', {})
        jockey_stats = runner.get('jockey_stats', {})
        
        # Class movement
        form = runner.get('form', [])
        current_class = race_data.get('class', 5)
        last_class = form[0].get('class', 5) if form else 5
        class_drop = last_class - current_class
        
        return {
            'trainer_win_rate': trainer_stats.get('win_rate', 0),
            'trainer_roi': trainer_stats.get('roi', 0),
            'jockey_win_rate': jockey_stats.get('win_rate', 0),
            'jockey_booking_strength': 1.0 if jockey_stats.get('win_rate', 0) > 0.15 else 0.0,
            'class_drop': max(0, class_drop),
            'stable_form': trainer_stats.get('recent_form', 0)
        }
    
    def _build_market_features(self, runner: Dict) -> Dict:
        """
        Block 4: Market microstructure
        Price movements, volume, drifts, steams
        """
        odds_timeline = runner.get('odds_timeline', [])
        
        if not odds_timeline:
            return {
                'current_odds': runner.get('odds', 10.0),
                'opening_odds': runner.get('odds', 10.0),
                'price_drift': 0,
                'steam_detected': 0,
                'volume_spike': 0
            }
        
        current = odds_timeline[-1].get('odds', 10.0)
        opening = odds_timeline[0].get('odds', 10.0)
        drift = current - opening
        
        # Steam detection (rapid price shortening)
        steam = 0
        if len(odds_timeline) > 5:
            recent_move = odds_timeline[-5].get('odds', current) - current
            if recent_move > 2.0:  # Shortened by 2+ points in last 5 updates
                steam = 1
        
        return {
            'current_odds': current,
            'opening_odds': opening,
            'price_drift': drift,
            'steam_detected': steam,
            'volume_spike': 0  # Would need volume data
        }
    
    def _build_geometry_features(self, runner: Dict, race_data: Dict, all_runners: List[Dict]) -> Dict:
        """
        Block 5: Race geometry
        Expected pace, field distribution, draw, chaos score
        """
        field_size = len(all_runners)
        
        # Draw advantage (lower is better on most tracks)
        draw = runner.get('draw', field_size // 2)
        draw_advantage = 1.0 - (draw / field_size) if field_size > 0 else 0.5
        
        # Pace - count early pace runners
        pace_runners = sum(1 for r in all_runners if r.get('running_style') == 'front_runner')
        pace_pressure = pace_runners / field_size if field_size > 0 else 0
        
        # Chaos score - field size, going, class
        chaos_score = (
            (field_size / 20.0) * 0.4 +  # Larger fields = more chaos
            (1.0 if race_data.get('going') in ['heavy', 'soft'] else 0.0) * 0.3 +
            (1.0 if race_data.get('class', 5) >= 5 else 0.0) * 0.3
        )
        
        return {
            'field_size': field_size,
            'draw': draw,
            'draw_advantage': draw_advantage,
            'pace_pressure': pace_pressure,
            'chaos_score': chaos_score,
            'track_bias': 0  # Would need historical track data
        }
    
    def get_feature_names(self) -> List[str]:
        """Return all feature names in order"""
        return [
            # Ability
            'rpr_best', 'rpr_median', 'rpr_variance', 'ts_best', 'or_current', 'class_best',
            # Form cycle
            'form_delta_last', 'form_trend', 'bounce_risk', 'days_since_run',
            # Intent
            'trainer_win_rate', 'trainer_roi', 'jockey_win_rate', 'jockey_booking_strength',
            'class_drop', 'stable_form',
            # Market
            'current_odds', 'opening_odds', 'price_drift', 'steam_detected', 'volume_spike',
            # Geometry
            'field_size', 'draw', 'draw_advantage', 'pace_pressure', 'chaos_score', 'track_bias'
        ]
