"""
TIE - Trainer Intention Engine

Purpose: Quantify trainer placement strategy and detect intentional setups

The TIE analyzes trainer behavior patterns to identify when a horse is being
"placed to win" vs "placed for experience" vs "placed to deceive the market".

Key Concepts:
- Placement intent: Is the trainer trying to win TODAY?
- Jockey booking: Significant jockey changes signal intent
- Prep cycle: Optimal spacing between runs
- Seasonal patterns: Trainers have preferred months/courses

Author: VÉLØ Oracle Team
Version: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class TrainerIntent(Enum):
    """Trainer intention classification"""
    WIN_TODAY = "win_today"           # All signals point to winning attempt
    PLACED_TO_WIN = "placed_to_win"   # Strong setup, good chance
    NEUTRAL = "neutral"                # Standard placement
    EXPERIENCE = "experience"          # Building fitness/experience
    DECEIVE = "deceive"                # Intentionally misleading market


@dataclass
class TIESignal:
    """TIE analysis result for a single runner"""
    runner_id: str
    horse_name: str
    trainer_name: str
    jockey_name: str
    
    # Intent signals
    jockey_booking_signal: float      # Jockey upgrade/downgrade (0-1)
    prep_cycle_signal: float          # Days since last run optimality (0-1)
    course_affinity_signal: float     # Trainer success at this course (0-1)
    distance_affinity_signal: float   # Trainer success at this distance (0-1)
    seasonal_signal: float            # Trainer success in this month (0-1)
    
    # Trainer statistics
    trainer_strike_rate: float        # Overall win rate
    trainer_roi: float                # Overall ROI
    jockey_trainer_combo_sr: float    # Win rate for this jockey-trainer combo
    
    # Intent classification
    intent: TrainerIntent
    tie_score: float                  # Combined intention score (0-1)
    confidence: float                 # Confidence in classification (0-1)
    
    # Metadata
    days_since_last_run: Optional[int]
    is_jockey_upgrade: bool
    is_course_specialist: bool


class TIE:
    """
    Trainer Intention Engine
    
    Analyzes trainer behavior to detect intentional win setups.
    """
    
    def __init__(
        self,
        min_trainer_runs: int = 20,
        optimal_prep_days: Tuple[int, int] = (14, 28),
        jockey_upgrade_threshold: float = 0.05
    ):
        """
        Initialize TIE engine
        
        Args:
            min_trainer_runs: Minimum runs required for trainer stats
            optimal_prep_days: (min, max) days for optimal prep cycle
            jockey_upgrade_threshold: Min strike rate diff for upgrade
        """
        self.min_trainer_runs = min_trainer_runs
        self.optimal_prep_days = optimal_prep_days
        self.jockey_upgrade_threshold = jockey_upgrade_threshold
        
        # Caches (would be loaded from database in production)
        self.trainer_stats_cache = {}
        self.jockey_stats_cache = {}
        self.combo_stats_cache = {}
    
    def calculate_jockey_booking_signal(
        self,
        runner: pd.Series,
        historical_data: pd.DataFrame
    ) -> Tuple[float, bool]:
        """
        Calculate signal from jockey booking
        
        Significant jockey upgrade = strong intent signal
        
        Args:
            runner: Current runner data
            historical_data: Historical runs for this horse
        
        Returns:
            (signal_strength, is_upgrade)
        """
        current_jockey = runner.get('jockey')
        
        if historical_data.empty or pd.isna(current_jockey):
            return 0.5, False  # Neutral if no history
        
        # Get previous jockey
        prev_runs = historical_data[historical_data['horse'] == runner.get('horse')]
        if len(prev_runs) == 0:
            return 0.5, False
        
        prev_jockey = prev_runs.iloc[0].get('jockey')
        
        if pd.isna(prev_jockey) or prev_jockey == current_jockey:
            return 0.5, False  # No change
        
        # Compare jockey strike rates
        current_sr = self._get_jockey_strike_rate(current_jockey)
        prev_sr = self._get_jockey_strike_rate(prev_jockey)
        
        diff = current_sr - prev_sr
        
        if diff >= self.jockey_upgrade_threshold:
            # Significant upgrade
            signal = np.clip(0.5 + diff, 0, 1)
            return signal, True
        elif diff <= -self.jockey_upgrade_threshold:
            # Downgrade (negative signal)
            signal = np.clip(0.5 + diff, 0, 1)
            return signal, False
        else:
            # Lateral move
            return 0.5, False
    
    def calculate_prep_cycle_signal(
        self,
        runner: pd.Series,
        historical_data: pd.DataFrame
    ) -> Tuple[float, Optional[int]]:
        """
        Calculate signal from prep cycle (days since last run)
        
        Optimal prep = 14-28 days for most horses
        Too short = underprepared
        Too long = ring rust
        
        Args:
            runner: Current runner data
            historical_data: Historical runs for this horse
        
        Returns:
            (signal_strength, days_since_last_run)
        """
        current_date = pd.to_datetime(runner.get('date'))
        
        # Get last run for this horse
        prev_runs = historical_data[
            (historical_data['horse'] == runner.get('horse')) &
            (pd.to_datetime(historical_data['date']) < current_date)
        ].sort_values('date', ascending=False)
        
        if len(prev_runs) == 0:
            return 0.5, None  # No history
        
        last_run_date = pd.to_datetime(prev_runs.iloc[0]['date'])
        days_since = (current_date - last_run_date).days
        
        # Calculate signal based on optimal range
        min_days, max_days = self.optimal_prep_days
        
        if min_days <= days_since <= max_days:
            # Optimal prep
            signal = 1.0
        elif days_since < min_days:
            # Too soon (linear penalty)
            signal = np.clip(days_since / min_days, 0, 1)
        else:
            # Too long (exponential decay)
            excess_days = days_since - max_days
            signal = np.exp(-excess_days / 30.0)  # Decay over 30 days
        
        return signal, days_since
    
    def calculate_course_affinity_signal(
        self,
        trainer: str,
        course: str,
        historical_data: pd.DataFrame
    ) -> Tuple[float, bool]:
        """
        Calculate trainer's success rate at this course
        
        Args:
            trainer: Trainer name
            course: Course name
            historical_data: Historical race data
        
        Returns:
            (signal_strength, is_specialist)
        """
        # Get trainer's runs at this course
        trainer_course_runs = historical_data[
            (historical_data['trainer'] == trainer) &
            (historical_data['course'] == course)
        ]
        
        if len(trainer_course_runs) < 5:
            return 0.5, False  # Insufficient data
        
        # Calculate strike rate
        wins = (trainer_course_runs['pos_int'] == 1).sum()
        runs = len(trainer_course_runs)
        course_sr = wins / runs
        
        # Compare to overall strike rate
        overall_sr = self._get_trainer_strike_rate(trainer)
        
        # Specialist if course SR > overall SR by 5%+
        is_specialist = course_sr > (overall_sr + 0.05)
        
        # Signal strength
        signal = np.clip(course_sr * 2.0, 0, 1)
        
        return signal, is_specialist
    
    def calculate_distance_affinity_signal(
        self,
        trainer: str,
        distance: int,
        historical_data: pd.DataFrame
    ) -> float:
        """
        Calculate trainer's success at this distance
        
        Args:
            trainer: Trainer name
            distance: Race distance in yards
            historical_data: Historical race data
        
        Returns:
            Signal strength (0-1)
        """
        # Distance tolerance: ±10%
        dist_min = distance * 0.9
        dist_max = distance * 1.1
        
        trainer_dist_runs = historical_data[
            (historical_data['trainer'] == trainer) &
            (historical_data['dist'] >= dist_min) &
            (historical_data['dist'] <= dist_max)
        ]
        
        if len(trainer_dist_runs) < 5:
            return 0.5  # Neutral
        
        wins = (trainer_dist_runs['pos_int'] == 1).sum()
        runs = len(trainer_dist_runs)
        dist_sr = wins / runs
        
        return np.clip(dist_sr * 2.0, 0, 1)
    
    def calculate_seasonal_signal(
        self,
        trainer: str,
        month: int,
        historical_data: pd.DataFrame
    ) -> float:
        """
        Calculate trainer's success in this month
        
        Some trainers have seasonal patterns (e.g., better in summer)
        
        Args:
            trainer: Trainer name
            month: Month (1-12)
            historical_data: Historical race data
        
        Returns:
            Signal strength (0-1)
        """
        historical_data = historical_data.copy()
        historical_data['month'] = pd.to_datetime(historical_data['date']).dt.month
        
        trainer_month_runs = historical_data[
            (historical_data['trainer'] == trainer) &
            (historical_data['month'] == month)
        ]
        
        if len(trainer_month_runs) < 10:
            return 0.5  # Neutral
        
        wins = (trainer_month_runs['pos_int'] == 1).sum()
        runs = len(trainer_month_runs)
        month_sr = wins / runs
        
        return np.clip(month_sr * 2.0, 0, 1)
    
    def classify_intent(
        self,
        signals: Dict[str, float],
        is_jockey_upgrade: bool,
        is_course_specialist: bool
    ) -> TrainerIntent:
        """
        Classify trainer intention based on signals
        
        Args:
            signals: Dict of signal strengths
            is_jockey_upgrade: Whether jockey was upgraded
            is_course_specialist: Whether trainer is course specialist
        
        Returns:
            TrainerIntent classification
        """
        avg_signal = np.mean(list(signals.values()))
        
        # WIN_TODAY: All signals strong + jockey upgrade + course specialist
        if (avg_signal >= 0.8 and
            is_jockey_upgrade and
            is_course_specialist):
            return TrainerIntent.WIN_TODAY
        
        # PLACED_TO_WIN: Most signals strong
        elif avg_signal >= 0.7:
            return TrainerIntent.PLACED_TO_WIN
        
        # EXPERIENCE: Weak signals, especially prep cycle
        elif avg_signal <= 0.3 or signals.get('prep_cycle', 0.5) <= 0.3:
            return TrainerIntent.EXPERIENCE
        
        # DECEIVE: Contradictory signals (high variance)
        elif np.std(list(signals.values())) > 0.3:
            return TrainerIntent.DECEIVE
        
        # NEUTRAL: Everything else
        else:
            return TrainerIntent.NEUTRAL
    
    def calculate_tie_score(
        self,
        signals: Dict[str, float],
        intent: TrainerIntent
    ) -> float:
        """
        Calculate final TIE score
        
        Args:
            signals: Dict of signal strengths
            intent: Classified intent
        
        Returns:
            TIE score (0-1)
        """
        base_score = np.mean(list(signals.values()))
        
        # Intent multipliers
        multipliers = {
            TrainerIntent.WIN_TODAY: 1.3,
            TrainerIntent.PLACED_TO_WIN: 1.1,
            TrainerIntent.NEUTRAL: 1.0,
            TrainerIntent.EXPERIENCE: 0.7,
            TrainerIntent.DECEIVE: 0.5
        }
        
        multiplier = multipliers.get(intent, 1.0)
        score = base_score * multiplier
        
        return np.clip(score, 0, 1)
    
    def analyze_runner(
        self,
        runner: pd.Series,
        historical_data: pd.DataFrame
    ) -> TIESignal:
        """
        Analyze trainer intention for a single runner
        
        Args:
            runner: Runner data
            historical_data: Historical race data
        
        Returns:
            TIESignal object with full analysis
        """
        trainer = runner.get('trainer', 'Unknown')
        jockey = runner.get('jockey', 'Unknown')
        course = runner.get('course', 'Unknown')
        distance = runner.get('dist', 0)
        month = pd.to_datetime(runner.get('date')).month
        
        # Calculate signals
        jockey_signal, is_upgrade = self.calculate_jockey_booking_signal(
            runner, historical_data
        )
        prep_signal, days_since = self.calculate_prep_cycle_signal(
            runner, historical_data
        )
        course_signal, is_specialist = self.calculate_course_affinity_signal(
            trainer, course, historical_data
        )
        dist_signal = self.calculate_distance_affinity_signal(
            trainer, distance, historical_data
        )
        seasonal_signal = self.calculate_seasonal_signal(
            trainer, month, historical_data
        )
        
        signals = {
            'jockey_booking': jockey_signal,
            'prep_cycle': prep_signal,
            'course_affinity': course_signal,
            'distance_affinity': dist_signal,
            'seasonal': seasonal_signal
        }
        
        # Classify intent
        intent = self.classify_intent(signals, is_upgrade, is_specialist)
        
        # Calculate TIE score
        tie_score = self.calculate_tie_score(signals, intent)
        
        # Confidence (inverse of signal variance)
        confidence = 1.0 - np.clip(np.std(list(signals.values())), 0, 1)
        
        # Get trainer stats
        trainer_sr = self._get_trainer_strike_rate(trainer)
        trainer_roi = self._get_trainer_roi(trainer)
        combo_sr = self._get_combo_strike_rate(trainer, jockey)
        
        return TIESignal(
            runner_id=f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}",
            horse_name=runner.get('horse', 'Unknown'),
            trainer_name=trainer,
            jockey_name=jockey,
            jockey_booking_signal=jockey_signal,
            prep_cycle_signal=prep_signal,
            course_affinity_signal=course_signal,
            distance_affinity_signal=dist_signal,
            seasonal_signal=seasonal_signal,
            trainer_strike_rate=trainer_sr,
            trainer_roi=trainer_roi,
            jockey_trainer_combo_sr=combo_sr,
            intent=intent,
            tie_score=tie_score,
            confidence=confidence,
            days_since_last_run=days_since,
            is_jockey_upgrade=is_upgrade,
            is_course_specialist=is_specialist
        )
    
    # Helper methods (would query database in production)
    
    def _get_trainer_strike_rate(self, trainer: str) -> float:
        """Get trainer's overall strike rate"""
        # Placeholder - would query database
        return 0.15  # 15% average
    
    def _get_trainer_roi(self, trainer: str) -> float:
        """Get trainer's overall ROI"""
        # Placeholder - would query database
        return 0.85  # -15% average (£0.85 return per £1 staked)
    
    def _get_jockey_strike_rate(self, jockey: str) -> float:
        """Get jockey's overall strike rate"""
        # Placeholder - would query database
        return 0.12  # 12% average
    
    def _get_combo_strike_rate(self, trainer: str, jockey: str) -> float:
        """Get jockey-trainer combination strike rate"""
        # Placeholder - would query database
        return 0.18  # 18% average (combos often better than individuals)

