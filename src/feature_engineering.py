"""
VÉLØ Feature Engineering Pipeline
Extracts 61 features across 9 domains from race data.
"""

import numpy as np
from typing import Dict, List, Any, Optional


class FeatureEngineer:
    """
    Transforms raw race data into 61 engineered features for LightGBM model.
    
    Feature domains:
    1. Form (10 features)
    2. Pace (8 features)
    3. Draw (5 features)
    4. Trainer/Jockey (12 features)
    5. Course/Going/Distance (10 features)
    6. Class (6 features)
    7. Recency (4 features)
    8. Weight/Age (3 features)
    9. Market (3 features)
    """
    
    def __init__(self):
        self.feature_names = self._get_feature_names()
    
    def _get_feature_names(self) -> List[str]:
        """Return ordered list of 61 feature names."""
        return [
            # Form domain (10)
            'rpr_last_3_avg',
            'ts_last_3_avg',
            'or_current',
            'form_consistency_score',
            'peak_form_recency',
            'form_decline_flag',
            'class_drop_indicator',
            'career_win_rate',
            'c_d_win_rate',
            'recent_placings',
            
            # Pace domain (8)
            'early_pace_score',
            'late_pace_score',
            'pace_geometry',
            'pace_collapse_prob',
            'closer_advantage',
            'front_runner_flag',
            'pace_pressure_index',
            'tactical_speed_score',
            
            # Draw domain (5)
            'draw_bias_score',
            'draw_advantage_index',
            'rail_position',
            'draw_going_interaction',
            'wide_draw_penalty',
            
            # Trainer/Jockey domain (12)
            'trainer_strike_rate_30d',
            'jockey_strike_rate_30d',
            'trainer_jockey_combo_win_rate',
            'first_choice_jockey_flag',
            'jockey_booking_intent',
            'stable_form_index',
            'trainer_course_record',
            'jockey_course_record',
            'trainer_distance_record',
            'trainer_going_record',
            'jockey_intent_score',
            'stable_star_flag',
            
            # Course/Going/Distance domain (10)
            'course_suitability_score',
            'going_suitability_score',
            'distance_suitability_score',
            'c_d_win_count',
            'course_win_count',
            'distance_win_count',
            'trip_match_score',
            'surface_preference',
            'going_extreme_flag',
            'distance_optimal_flag',
            
            # Class domain (6)
            'class_rating',
            'class_movement',
            'competitive_index',
            'or_vs_class_gap',
            'class_rise_flag',
            'class_drop_flag',
            
            # Recency domain (4)
            'days_since_last_run',
            'runs_this_season',
            'layoff_flag',
            'freshness_score',
            
            # Weight/Age domain (3)
            'weight_carried',
            'age',
            'weight_for_age_adjustment',
            
            # Market domain (3)
            'odds',
            'odds_drift',
            'bsp_advantage',
        ]
    
    def extract_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> np.ndarray:
        """
        Extract 61 features for a single runner.
        
        Args:
            runner: Runner data dict with form, ratings, history
            race: Race context (going, distance, field size, etc.)
        
        Returns:
            np.ndarray of shape (61,) with engineered features
        """
        features = []
        
        # Form domain (10)
        features.extend(self._extract_form_features(runner))
        
        # Pace domain (8)
        features.extend(self._extract_pace_features(runner, race))
        
        # Draw domain (5)
        features.extend(self._extract_draw_features(runner, race))
        
        # Trainer/Jockey domain (12)
        features.extend(self._extract_trainer_jockey_features(runner, race))
        
        # Course/Going/Distance domain (10)
        features.extend(self._extract_course_going_distance_features(runner, race))
        
        # Class domain (6)
        features.extend(self._extract_class_features(runner, race))
        
        # Recency domain (4)
        features.extend(self._extract_recency_features(runner))
        
        # Weight/Age domain (3)
        features.extend(self._extract_weight_age_features(runner, race))
        
        # Market domain (3)
        features.extend(self._extract_market_features(runner))
        
        return np.array(features, dtype=np.float32)
    
    def _extract_form_features(self, runner: Dict[str, Any]) -> List[float]:
        """Extract 10 form features."""
        return [
            runner.get('rpr_last_3_avg', 0.0),
            runner.get('ts_last_3_avg', 0.0),
            runner.get('or_current', 0.0),
            runner.get('form_consistency_score', 0.0),
            runner.get('peak_form_recency', 999.0),  # days since peak
            float(runner.get('form_decline_flag', False)),
            float(runner.get('class_drop_indicator', False)),
            runner.get('career_win_rate', 0.0),
            runner.get('c_d_win_rate', 0.0),
            runner.get('recent_placings', 0.0),  # top-3 finishes in last 5
        ]
    
    def _extract_pace_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        """Extract 8 pace features."""
        return [
            runner.get('early_pace_score', 0.0),
            runner.get('late_pace_score', 0.0),
            runner.get('pace_geometry', 0.0),  # how pace profile fits race
            runner.get('pace_collapse_prob', 0.0),
            runner.get('closer_advantage', 0.0),
            float(runner.get('front_runner_flag', False)),
            race.get('pace_pressure_index', 0.0),  # field-level pace pressure
            runner.get('tactical_speed_score', 0.0),
        ]
    
    def _extract_draw_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        """Extract 5 draw features."""
        draw = runner.get('draw', 0)
        runners = race.get('runners', 1)
        
        return [
            race.get('draw_bias_score', 0.0),  # track-specific bias
            runner.get('draw_advantage_index', 0.0),
            float(draw <= 3),  # rail position flag
            runner.get('draw_going_interaction', 0.0),
            float(draw > runners * 0.7),  # wide draw penalty
        ]
    
    def _extract_trainer_jockey_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        """Extract 12 trainer/jockey features."""
        return [
            runner.get('trainer_strike_rate_30d', 0.0),
            runner.get('jockey_strike_rate_30d', 0.0),
            runner.get('trainer_jockey_combo_win_rate', 0.0),
            float(runner.get('first_choice_jockey_flag', False)),
            runner.get('jockey_booking_intent', 0.0),  # 0-100 score
            runner.get('stable_form_index', 0.0),
            runner.get('trainer_course_record', 0.0),
            runner.get('jockey_course_record', 0.0),
            runner.get('trainer_distance_record', 0.0),
            runner.get('trainer_going_record', 0.0),
            runner.get('jockey_intent_score', 0.0),  # 0-100 score
            float(runner.get('stable_star_flag', False)),
        ]
    
    def _extract_course_going_distance_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        """Extract 10 course/going/distance features."""
        return [
            runner.get('course_suitability_score', 0.0),
            runner.get('going_suitability_score', 0.0),
            runner.get('distance_suitability_score', 0.0),
            runner.get('c_d_win_count', 0.0),
            runner.get('course_win_count', 0.0),
            runner.get('distance_win_count', 0.0),
            runner.get('trip_match_score', 0.0),
            runner.get('surface_preference', 0.0),  # AW vs turf
            float(race.get('going', '') in ['HEAVY', 'SOFT']),
            float(runner.get('distance_optimal_flag', False)),
        ]
    
    def _extract_class_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        """Extract 6 class features."""
        return [
            runner.get('class_rating', 0.0),
            runner.get('class_movement', 0.0),  # +1 = rise, -1 = drop
            runner.get('competitive_index', 0.0),
            runner.get('or_vs_class_gap', 0.0),
            float(runner.get('class_rise_flag', False)),
            float(runner.get('class_drop_flag', False)),
        ]
    
    def _extract_recency_features(self, runner: Dict[str, Any]) -> List[float]:
        """Extract 4 recency features."""
        days_since_last = runner.get('days_since_last_run', 999)
        
        return [
            days_since_last,
            runner.get('runs_this_season', 0.0),
            float(days_since_last > 90),  # layoff flag
            runner.get('freshness_score', 0.0),
        ]
    
    def _extract_weight_age_features(self, runner: Dict[str, Any], race: Dict[str, Any]) -> List[float]:
        """Extract 3 weight/age features."""
        return [
            runner.get('weight_carried', 0.0),
            runner.get('age', 0.0),
            runner.get('weight_for_age_adjustment', 0.0),
        ]
    
    def _extract_market_features(self, runner: Dict[str, Any]) -> List[float]:
        """Extract 3 market features."""
        return [
            runner.get('odds', 999.0),
            runner.get('odds_drift', 0.0),  # % change from opening
            runner.get('bsp_advantage', 0.0),  # BSP vs SP difference
        ]
    
    def extract_race_features(self, race_data: Dict[str, Any]) -> np.ndarray:
        """
        Extract features for all runners in a race.
        
        Args:
            race_data: Dict with 'runners' list and race context
        
        Returns:
            np.ndarray of shape (n_runners, 61)
        """
        runners = race_data.get('runners', [])
        race_context = {
            'going': race_data.get('going'),
            'distance': race_data.get('distance'),
            'runners': len(runners),
            'pace_pressure_index': race_data.get('pace_pressure_index', 0.0),
            'draw_bias_score': race_data.get('draw_bias_score', 0.0),
        }
        
        features_matrix = []
        for runner in runners:
            features = self.extract_features(runner, race_context)
            features_matrix.append(features)
        
        return np.array(features_matrix)


def create_sample_runner() -> Dict[str, Any]:
    """Create sample runner data for testing."""
    return {
        # Form
        'rpr_last_3_avg': 120.0,
        'ts_last_3_avg': 95.0,
        'or_current': 115.0,
        'form_consistency_score': 0.75,
        'peak_form_recency': 30.0,
        'form_decline_flag': False,
        'class_drop_indicator': True,
        'career_win_rate': 0.25,
        'c_d_win_rate': 0.33,
        'recent_placings': 3.0,
        
        # Pace
        'early_pace_score': 0.6,
        'late_pace_score': 0.8,
        'pace_geometry': 0.7,
        'pace_collapse_prob': 0.2,
        'closer_advantage': 0.5,
        'front_runner_flag': False,
        'tactical_speed_score': 0.65,
        
        # Draw
        'draw': 5,
        'draw_advantage_index': 0.1,
        'draw_going_interaction': 0.05,
        
        # Trainer/Jockey
        'trainer_strike_rate_30d': 0.20,
        'jockey_strike_rate_30d': 0.18,
        'trainer_jockey_combo_win_rate': 0.25,
        'first_choice_jockey_flag': True,
        'jockey_booking_intent': 75.0,
        'stable_form_index': 0.65,
        'trainer_course_record': 0.15,
        'jockey_course_record': 0.20,
        'trainer_distance_record': 0.18,
        'trainer_going_record': 0.22,
        'jockey_intent_score': 70.0,
        'stable_star_flag': True,
        
        # Course/Going/Distance
        'course_suitability_score': 0.75,
        'going_suitability_score': 0.80,
        'distance_suitability_score': 0.85,
        'c_d_win_count': 2.0,
        'course_win_count': 3.0,
        'distance_win_count': 4.0,
        'trip_match_score': 0.90,
        'surface_preference': 0.70,
        'distance_optimal_flag': True,
        
        # Class
        'class_rating': 3.0,
        'class_movement': -1.0,  # dropping in class
        'competitive_index': 0.70,
        'or_vs_class_gap': -5.0,
        'class_rise_flag': False,
        'class_drop_flag': True,
        
        # Recency
        'days_since_last_run': 21.0,
        'runs_this_season': 4.0,
        'freshness_score': 0.75,
        
        # Weight/Age
        'weight_carried': 140.0,
        'age': 5.0,
        'weight_for_age_adjustment': 0.0,
        
        # Market
        'odds': 3.5,
        'odds_drift': -5.0,  # 5% shorter
        'bsp_advantage': 2.0,  # 2% better on BSP
    }


if __name__ == "__main__":
    # Test feature extraction
    engineer = FeatureEngineer()
    
    sample_runner = create_sample_runner()
    sample_race = {
        'going': 'GOOD',
        'distance': '2m',
        'runners': 10,
        'pace_pressure_index': 0.6,
        'draw_bias_score': 0.1,
    }
    
    features = engineer.extract_features(sample_runner, sample_race)
    
    print("Feature Engineering Test")
    print("=" * 80)
    print(f"Extracted {len(features)} features")
    print(f"Feature shape: {features.shape}")
    print()
    print("Sample features:")
    for i, (name, value) in enumerate(zip(engineer.feature_names[:10], features[:10])):
        print(f"  {i+1:2d}. {name:30s} = {value:.3f}")
    print(f"  ... ({len(features)-10} more features)")
    print()
    print("✅ Feature engineering pipeline working")
