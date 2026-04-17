#!/usr/bin/env python3
"""
VELO Race Engineering Features
Features that reflect how races are constructed and targeted

We need features that reflect how races are ENGINEERED, not just horse form.

4.1 Condition Targeting Index (CTI)
- Match to race conditions (age/sex/class/distance/going/band/penalties)
- Prior evidence of trainer using similar conditions
- Pattern: "horse often runs in this exact template when ready"

4.2 Entry Intent Markers (EIM)
- Travel distance (if available)
- Quick turnaround vs long gap
- First-time headgear, switch in jockey, notable booking
- Class move + distance move + surface move combination
- Stable form (hot/cold) + "needs a win" context

4.3 Multi-Runner Stable Coupling (MSC)
- If same trainer has 2+ runners:
  * Detect complementary roles (pace + finisher)
  * Detect "protect the fav" patterns
  * Detect "one is the plot" with market shape divergence

4.4 Handicap Mark Strategy (HMS)
- UK/IRE angle: trainers manage marks
- mark_pressure: horse running from career-high OR dropping to a "floor"
- drop_program: multiple runs with declining effort to drop mark
- "today is the go" when conditions finally match + market indicates

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class RaceEngineeringFeatures:
    """Race engineering features for a runner."""
    runner_id: str
    cti_score: float = 0.0  # Condition Targeting Index
    eim_score: float = 0.0  # Entry Intent Markers
    msc_threat_flag: bool = False  # Multi-Runner Stable Coupling
    msc_role: str = "solo"  # pace_setter, finisher, decoy, solo
    hms_signal: float = 0.0  # Handicap Mark Strategy
    
    def to_dict(self) -> Dict:
        return {
            'runner_id': self.runner_id,
            'cti_score': self.cti_score,
            'eim_score': self.eim_score,
            'msc_threat_flag': self.msc_threat_flag,
            'msc_role': self.msc_role,
            'hms_signal': self.hms_signal
        }


class RaceEngineeringFeatureBuilder:
    """
    Race Engineering Feature Builder.
    
    Builds features that reflect how races are constructed and targeted.
    """
    
    def __init__(self):
        logger.info("Race Engineering Feature Builder initialized")
    
    def build_features(
        self,
        runners: List[Dict],
        race_ctx: Dict,
        historical_data: Optional[pd.DataFrame] = None
    ) -> List[RaceEngineeringFeatures]:
        """
        Build race engineering features for all runners.
        
        Args:
            runners: List of runner data
            race_ctx: Race context
            historical_data: Optional historical data for pattern matching
            
        Returns:
            List of RaceEngineeringFeatures
        """
        logger.info(f"Building race engineering features for {len(runners)} runners")
        
        features_list = []
        
        for runner in runners:
            features = RaceEngineeringFeatures(runner_id=runner.get('runner_id', 'unknown'))
            
            # 1. Condition Targeting Index
            features.cti_score = self._calculate_cti(runner, race_ctx, historical_data)
            
            # 2. Entry Intent Markers
            features.eim_score = self._calculate_eim(runner, race_ctx)
            
            # 3. Handicap Mark Strategy
            features.hms_signal = self._calculate_hms(runner, historical_data)
            
            features_list.append(features)
        
        # 4. Multi-Runner Stable Coupling (requires all runners)
        self._calculate_msc(features_list, runners, race_ctx)
        
        return features_list
    
    def _calculate_cti(
        self,
        runner: Dict,
        race_ctx: Dict,
        historical_data: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate Condition Targeting Index.
        
        Measures how well this runner matches the race conditions template.
        """
        score = 0.0
        count = 0
        
        # Age match
        runner_age = runner.get('age', 0)
        race_age_band = race_ctx.get('age_band', 'open')
        if race_age_band == 'open' or self._age_matches_band(runner_age, race_age_band):
            score += 1.0
        count += 1
        
        # Sex match
        runner_sex = runner.get('sex', 'unknown')
        race_sex_restriction = race_ctx.get('sex_restriction', 'open')
        if race_sex_restriction == 'open' or runner_sex in race_sex_restriction:
            score += 1.0
        count += 1
        
        # Class match
        runner_class = runner.get('class_rating', 0)
        race_class = race_ctx.get('class_level', 0)
        class_diff = abs(runner_class - race_class)
        if class_diff == 0:
            score += 1.0
        elif class_diff == 1:
            score += 0.5
        count += 1
        
        # Distance match (historical preference)
        if historical_data is not None:
            runner_hist = historical_data[historical_data['horse'] == runner.get('horse_name')]
            if len(runner_hist) > 0:
                race_dist = race_ctx.get('distance', 0)
                dist_wins = runner_hist[runner_hist['dist'] == race_dist]['win'].sum()
                dist_runs = len(runner_hist[runner_hist['dist'] == race_dist])
                if dist_runs > 0:
                    dist_win_rate = dist_wins / dist_runs
                    score += dist_win_rate
                    count += 1
        
        # Normalize
        return score / count if count > 0 else 0.0
    
    def _calculate_eim(self, runner: Dict, race_ctx: Dict) -> float:
        """
        Calculate Entry Intent Markers.
        
        Detects signals that trainer is targeting this race.
        """
        signals = []
        
        # Quick turnaround (< 14 days)
        days_since = runner.get('days_since_last_run', 999)
        if 7 <= days_since <= 14:
            signals.append(0.3)  # Positive signal
        
        # Long layoff (> 90 days) - negative unless fresh
        if days_since > 90:
            signals.append(-0.2)
        
        # First-time headgear
        if runner.get('first_time_headgear', False):
            signals.append(0.4)
        
        # Notable jockey booking
        if runner.get('jockey_booking_notable', False):
            signals.append(0.5)
        
        # Jockey switch to higher-rated
        jockey_upgrade = runner.get('jockey_upgrade', False)
        if jockey_upgrade:
            signals.append(0.3)
        
        # Class drop
        class_movement = runner.get('class_movement', 0)
        if class_movement < 0:  # Dropping in class
            signals.append(0.4)
        elif class_movement > 0:  # Rising in class
            signals.append(-0.2)
        
        # Stable form (hot stable)
        stable_form = runner.get('stable_form_last_14', 0.0)
        if stable_form > 0.25:
            signals.append(0.3)
        
        # Sum and normalize
        total = sum(signals)
        return max(-1.0, min(1.0, total))  # Clamp to [-1, 1]
    
    def _calculate_hms(
        self,
        runner: Dict,
        historical_data: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate Handicap Mark Strategy signal.
        
        Detects if trainer is managing handicap mark.
        """
        signal = 0.0
        
        # Mark pressure
        mark_pressure = runner.get('mark_pressure', 'normal')
        
        if mark_pressure == 'career_high':
            # Running off career-high mark - negative signal
            signal -= 0.5
        elif mark_pressure == 'floor':
            # Dropped to floor mark - positive signal
            signal += 0.5
        
        # Drop program detection (requires historical data)
        if historical_data is not None:
            runner_hist = historical_data[historical_data['horse'] == runner.get('horse_name')]
            if len(runner_hist) >= 3:
                # Check last 3 runs for declining effort
                last_3 = runner_hist.tail(3)
                positions = last_3['pos'].apply(lambda x: int(x) if str(x).isdigit() else 99).tolist()
                
                # If positions getting worse → drop program
                if len(positions) == 3 and positions[0] < positions[1] < positions[2]:
                    signal += 0.6  # Strong signal: ready to strike
        
        # "Today is the go" detection
        # Conditions match + market support
        conditions_match = runner.get('cti_score', 0.0) > 0.7
        market_support = runner.get('odds_drift', 0.0) < -0.2  # Shortening
        
        if conditions_match and market_support and mark_pressure == 'floor':
            signal += 0.8  # Very strong signal
        
        return max(-1.0, min(1.0, signal))  # Clamp to [-1, 1]
    
    def _calculate_msc(
        self,
        features_list: List[RaceEngineeringFeatures],
        runners: List[Dict],
        race_ctx: Dict
    ):
        """
        Calculate Multi-Runner Stable Coupling.
        
        Detects multi-runner tactics from same stable.
        Modifies features_list in place.
        """
        # Group by trainer
        trainer_groups = {}
        for i, runner in enumerate(runners):
            trainer = runner.get('trainer', 'unknown')
            if trainer not in trainer_groups:
                trainer_groups[trainer] = []
            trainer_groups[trainer].append((i, runner))
        
        # Analyze each trainer group
        for trainer, stable_runners in trainer_groups.items():
            if len(stable_runners) < 2:
                continue  # Solo runner
            
            # Multi-runner stable detected
            logger.info(f"Multi-runner stable detected: {trainer} with {len(stable_runners)} runners")
            
            # Sort by odds (shortest to longest)
            stable_runners_sorted = sorted(stable_runners, key=lambda x: x[1].get('odds_decimal', 100))
            
            for idx, (i, runner) in enumerate(stable_runners_sorted):
                features = features_list[i]
                features.msc_threat_flag = True
                
                # Assign role
                pace_style = runner.get('pace_style', 'unknown')
                
                if idx == 0:
                    # Shortest price = likely finisher
                    features.msc_role = 'finisher'
                elif pace_style == 'front_runner':
                    features.msc_role = 'pace_setter'
                else:
                    features.msc_role = 'decoy'
    
    def _age_matches_band(self, age: int, band: str) -> bool:
        """Check if age matches age band."""
        if band == '2yo':
            return age == 2
        elif band == '3yo':
            return age == 3
        elif band == '3yo+':
            return age >= 3
        elif band == '4yo+':
            return age >= 4
        return True


def build_race_engineering_features(
    runners: List[Dict],
    race_ctx: Dict,
    historical_data: Optional[pd.DataFrame] = None
) -> List[RaceEngineeringFeatures]:
    """
    Convenience function to build race engineering features.
    
    Args:
        runners: Runner data
        race_ctx: Race context
        historical_data: Historical data
        
    Returns:
        List of RaceEngineeringFeatures
    """
    builder = RaceEngineeringFeatureBuilder()
    return builder.build_features(runners, race_ctx, historical_data)


if __name__ == "__main__":
    # Example usage
    runners = [
        {
            'runner_id': 'r1',
            'horse_name': 'Horse A',
            'trainer': 'Trainer X',
            'age': 4,
            'sex': 'G',
            'class_rating': 85,
            'days_since_last_run': 10,
            'first_time_headgear': True,
            'jockey_booking_notable': True,
            'odds_decimal': 3.5,
            'pace_style': 'closer'
        },
        {
            'runner_id': 'r2',
            'horse_name': 'Horse B',
            'trainer': 'Trainer X',
            'age': 5,
            'sex': 'G',
            'class_rating': 85,
            'days_since_last_run': 12,
            'odds_decimal': 8.0,
            'pace_style': 'front_runner'
        },
        {
            'runner_id': 'r3',
            'horse_name': 'Horse C',
            'trainer': 'Trainer Y',
            'age': 4,
            'sex': 'M',
            'class_rating': 82,
            'days_since_last_run': 120,
            'odds_decimal': 5.0
        }
    ]
    
    race_ctx = {
        'race_id': 'test_001',
        'course': 'Newmarket',
        'distance': 1200,
        'class_level': 85,
        'age_band': 'open',
        'sex_restriction': 'open'
    }
    
    features = build_race_engineering_features(runners, race_ctx)
    
    for feat in features:
        print(f"\n{feat.runner_id}:")
        print(f"  CTI: {feat.cti_score:.2f}")
        print(f"  EIM: {feat.eim_score:.2f}")
        print(f"  HMS: {feat.hms_signal:.2f}")
        print(f"  MSC: {feat.msc_role} (threat={feat.msc_threat_flag})")
