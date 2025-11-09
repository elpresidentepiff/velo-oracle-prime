"""
SQPE - Sub-Quadratic Prediction Engine

Purpose: Filter noise, amplify convergence signals, rank true-value edges

The SQPE is the first intelligence layer that transforms raw Benter probabilities
into strategic insights by analyzing signal convergence across multiple factors.

Key Concepts:
- Signal convergence: When multiple independent factors agree
- Noise filtering: Reject weak or contradictory signals
- Sub-quadratic complexity: Efficient O(n log n) ranking instead of O(n²)

Author: VÉLØ Oracle Team
Version: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SignalStrength(Enum):
    """Signal strength classification"""
    STRONG = "strong"          # High confidence, multiple factors align
    MODERATE = "moderate"      # Some factors align
    WEAK = "weak"              # Single factor or contradictory
    NOISE = "noise"            # No clear signal


@dataclass
class SQPESignal:
    """SQPE analysis result for a single runner"""
    runner_id: str
    horse_name: str
    
    # Core probabilities
    p_benter: float           # Benter model probability
    p_public: float           # Market probability
    edge: float               # p_benter - p_public
    
    # Signal components
    rating_signal: float      # Strength from ratings (0-1)
    form_signal: float        # Strength from recent form (0-1)
    class_signal: float       # Strength from class/quality (0-1)
    market_signal: float      # Strength from market movement (0-1)
    
    # Convergence analysis
    convergence_score: float  # How many signals agree (0-1)
    signal_strength: SignalStrength
    
    # Final ranking
    sqpe_score: float         # Combined score for ranking
    confidence: float         # Confidence in prediction (0-1)
    
    # Metadata
    odds: float
    is_longshot: bool         # odds > 10.0


class SQPE:
    """
    Sub-Quadratic Prediction Engine
    
    Analyzes signal convergence and filters noise to identify
    true-value opportunities.
    """
    
    def __init__(
        self,
        convergence_threshold: float = 0.6,
        min_confidence: float = 0.5,
        longshot_threshold: float = 10.0
    ):
        """
        Initialize SQPE engine
        
        Args:
            convergence_threshold: Minimum convergence score (0-1)
            min_confidence: Minimum confidence for strong signal
            longshot_threshold: Odds threshold for longshot classification
        """
        self.convergence_threshold = convergence_threshold
        self.min_confidence = min_confidence
        self.longshot_threshold = longshot_threshold
    
    def calculate_rating_signal(self, runner: pd.Series) -> float:
        """
        Calculate signal strength from ratings
        
        Args:
            runner: Runner data with or_int, rpr_int, ts_int
        
        Returns:
            Signal strength (0-1)
        """
        ratings = []
        if pd.notna(runner.get('or_int')): ratings.append(runner['or_int'])
        if pd.notna(runner.get('rpr_int')): ratings.append(runner['rpr_int'])
        if pd.notna(runner.get('ts_int')): ratings.append(runner['ts_int'])
        
        if not ratings:
            return 0.0
        
        # Normalize to 0-1 (assuming ratings 0-140 range)
        avg_rating = np.mean(ratings)
        normalized = np.clip(avg_rating / 140.0, 0, 1)
        
        # Consistency bonus: if all ratings agree (low std), boost signal
        if len(ratings) > 1:
            std = np.std(ratings)
            consistency = 1.0 - np.clip(std / 20.0, 0, 1)
            normalized *= (1.0 + 0.2 * consistency)  # Up to 20% boost
        
        return np.clip(normalized, 0, 1)
    
    def calculate_form_signal(self, runner: pd.Series) -> float:
        """
        Calculate signal strength from recent form
        
        Args:
            runner: Runner data with form string
        
        Returns:
            Signal strength (0-1)
        """
        # TODO: Parse form string (e.g., "1-2-3-4-5")
        # For now, placeholder based on recent position
        if pd.notna(runner.get('pos_int')) and runner['pos_int'] <= 3:
            return 0.7
        return 0.3
    
    def calculate_class_signal(self, runner: pd.Series) -> float:
        """
        Calculate signal strength from class/quality
        
        Args:
            runner: Runner data with class, pattern
        
        Returns:
            Signal strength (0-1)
        """
        # Class: 1-7 (1 = highest)
        if pd.notna(runner.get('class')):
            try:
                class_val = int(runner['class'])
                # Invert: class 1 = 1.0, class 7 = 0.0
                return np.clip((8 - class_val) / 7.0, 0, 1)
            except:
                pass
        
        return 0.5  # Neutral if unknown
    
    def calculate_market_signal(self, runner: pd.Series) -> float:
        """
        Calculate signal strength from market behavior
        
        Args:
            runner: Runner data with sp_decimal
        
        Returns:
            Signal strength (0-1)
        """
        # TODO: Track odds movement (requires historical odds)
        # For now, use implied probability as proxy
        if pd.notna(runner.get('sp_decimal')):
            p_market = 1.0 / runner['sp_decimal']
            # Higher market confidence = stronger signal
            return np.clip(p_market * 2.0, 0, 1)
        
        return 0.0
    
    def calculate_convergence(self, signals: List[float]) -> float:
        """
        Calculate convergence score from multiple signals
        
        High convergence = signals agree (all high or all low)
        Low convergence = signals contradict (some high, some low)
        
        Args:
            signals: List of signal strengths (0-1)
        
        Returns:
            Convergence score (0-1)
        """
        if not signals:
            return 0.0
        
        # Method: 1 - (standard deviation of signals)
        # Low std = high convergence
        std = np.std(signals)
        convergence = 1.0 - np.clip(std, 0, 1)
        
        return convergence
    
    def classify_signal_strength(
        self,
        convergence: float,
        confidence: float
    ) -> SignalStrength:
        """
        Classify overall signal strength
        
        Args:
            convergence: Convergence score (0-1)
            confidence: Confidence score (0-1)
        
        Returns:
            Signal strength classification
        """
        if convergence >= self.convergence_threshold and confidence >= self.min_confidence:
            return SignalStrength.STRONG
        elif convergence >= 0.4 and confidence >= 0.3:
            return SignalStrength.MODERATE
        elif convergence >= 0.2:
            return SignalStrength.WEAK
        else:
            return SignalStrength.NOISE
    
    def calculate_sqpe_score(
        self,
        edge: float,
        convergence: float,
        confidence: float,
        is_longshot: bool
    ) -> float:
        """
        Calculate final SQPE score for ranking
        
        Formula: edge × convergence × confidence × longshot_penalty
        
        Args:
            edge: Benter edge (p_model - p_market)
            convergence: Signal convergence (0-1)
            confidence: Prediction confidence (0-1)
            is_longshot: Whether this is a longshot bet
        
        Returns:
            SQPE score (higher = better opportunity)
        """
        # Base score: edge weighted by convergence and confidence
        score = edge * convergence * confidence
        
        # Longshot penalty: require higher convergence for longshots
        if is_longshot:
            longshot_penalty = 0.7  # 30% penalty
            score *= longshot_penalty
        
        return score
    
    def analyze_runner(
        self,
        runner: pd.Series,
        p_benter: float,
        p_public: float
    ) -> SQPESignal:
        """
        Analyze a single runner and generate SQPE signal
        
        Args:
            runner: Runner data (pandas Series)
            p_benter: Benter model probability
            p_public: Market probability
        
        Returns:
            SQPESignal object with full analysis
        """
        # Calculate individual signals
        rating_signal = self.calculate_rating_signal(runner)
        form_signal = self.calculate_form_signal(runner)
        class_signal = self.calculate_class_signal(runner)
        market_signal = self.calculate_market_signal(runner)
        
        # Calculate convergence
        signals = [rating_signal, form_signal, class_signal, market_signal]
        convergence = self.calculate_convergence(signals)
        
        # Calculate confidence (average of all signals)
        confidence = np.mean(signals)
        
        # Edge
        edge = p_benter - p_public
        
        # Longshot classification
        odds = runner.get('sp_decimal', 0)
        is_longshot = odds > self.longshot_threshold
        
        # Signal strength
        signal_strength = self.classify_signal_strength(convergence, confidence)
        
        # SQPE score
        sqpe_score = self.calculate_sqpe_score(
            edge, convergence, confidence, is_longshot
        )
        
        return SQPESignal(
            runner_id=f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}",
            horse_name=runner.get('horse', 'Unknown'),
            p_benter=p_benter,
            p_public=p_public,
            edge=edge,
            rating_signal=rating_signal,
            form_signal=form_signal,
            class_signal=class_signal,
            market_signal=market_signal,
            convergence_score=convergence,
            signal_strength=signal_strength,
            sqpe_score=sqpe_score,
            confidence=confidence,
            odds=odds,
            is_longshot=is_longshot
        )
    
    def analyze_race(
        self,
        runners: pd.DataFrame,
        p_benter_dict: Dict[str, float],
        p_public_dict: Dict[str, float]
    ) -> List[SQPESignal]:
        """
        Analyze all runners in a race
        
        Args:
            runners: DataFrame of runners in race
            p_benter_dict: Dict mapping runner_id to Benter probability
            p_public_dict: Dict mapping runner_id to public probability
        
        Returns:
            List of SQPESignal objects, sorted by sqpe_score (descending)
        """
        signals = []
        
        for idx, runner in runners.iterrows():
            runner_id = f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}"
            
            p_benter = p_benter_dict.get(runner_id, 0.0)
            p_public = p_public_dict.get(runner_id, 0.0)
            
            signal = self.analyze_runner(runner, p_benter, p_public)
            signals.append(signal)
        
        # Sort by SQPE score (descending)
        signals.sort(key=lambda x: x.sqpe_score, reverse=True)
        
        return signals
    
    def filter_strong_signals(
        self,
        signals: List[SQPESignal]
    ) -> List[SQPESignal]:
        """
        Filter to only strong signals
        
        Args:
            signals: List of SQPE signals
        
        Returns:
            Filtered list containing only strong signals
        """
        return [
            s for s in signals
            if s.signal_strength == SignalStrength.STRONG
        ]
    
    def get_top_opportunities(
        self,
        signals: List[SQPESignal],
        top_n: int = 3
    ) -> List[SQPESignal]:
        """
        Get top N opportunities by SQPE score
        
        Args:
            signals: List of SQPE signals (should be sorted)
            top_n: Number of top opportunities to return
        
        Returns:
            Top N signals
        """
        return signals[:top_n]

