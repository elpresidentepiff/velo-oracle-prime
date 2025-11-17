"""
Intelligence Orchestrator

Purpose: Coordinate SQPE, TIE, NDS modules with dual-signal logic

The Orchestrator integrates all intelligence modules and enforces the
dual-signal requirement: NO BET unless 2+ modules agree.

This transforms VÉLØ from a calculator into a strategist by requiring
multiple independent confirmations before committing capital.

Author: VÉLØ Oracle Team
Version: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from .sqpe import SQPE, SQPESignal, SignalStrength
from .tie import TIE, TrainerIntentEngine
from .nds import NDS, NDSSignal, DisruptionStrength, NarrativeType


class BetRecommendation(Enum):
    """Bet recommendation classification"""
    STRONG_BACK = "strong_back"       # 3 modules agree, back this horse
    MODERATE_BACK = "moderate_back"   # 2 modules agree, back this horse
    HOLD = "hold"                     # Insufficient agreement, no bet
    MODERATE_FADE = "moderate_fade"   # 2 modules agree, fade this horse
    STRONG_FADE = "strong_fade"       # 3 modules agree, fade this horse


@dataclass
class IntelligenceSignal:
    """Combined intelligence analysis for a single runner"""
    runner_id: str
    horse_name: str
    odds: float
    
    # Module signals
    sqpe_signal: SQPESignal
    tie_signal: TIESignal
    nds_signal: NDSSignal
    
    # Agreement analysis
    modules_agree_back: int           # How many modules say "back"
    modules_agree_fade: int           # How many modules say "fade"
    agreement_score: float            # Overall agreement (0-1)
    
    # Final recommendation
    recommendation: BetRecommendation
    conviction: float                 # Strength of conviction (0-1)
    
    # Reasoning
    reasoning: List[str]              # Human-readable reasoning


class IntelligenceOrchestrator:
    """
    Orchestrates SQPE, TIE, NDS modules with dual-signal logic
    
    Enforces rule: NO BET unless 2+ modules agree
    """
    
    def __init__(
        self,
        min_modules_required: int = 2,
        sqpe_threshold: float = 0.6,
        tie_threshold: float = 0.7,
        nds_threshold: float = 0.6
    ):
        """
        Initialize orchestrator
        
        Args:
            min_modules_required: Minimum modules that must agree (2 or 3)
            sqpe_threshold: Minimum SQPE score for agreement
            tie_threshold: Minimum TIE score for agreement
            nds_threshold: Minimum NDS score for agreement
        """
        self.min_modules_required = min_modules_required
        self.sqpe_threshold = sqpe_threshold
        self.tie_threshold = tie_threshold
        self.nds_threshold = nds_threshold
        
        # Initialize modules
        self.sqpe = SQPE()
        self.tie = TIE()
        self.nds = NDS()
    
    def evaluate_sqpe_vote(self, signal: SQPESignal) -> Tuple[str, float, str]:
        """
        Determine SQPE's vote
        
        Returns:
            (vote, confidence, reasoning)
            vote: "back", "fade", or "abstain"
        """
        if signal.signal_strength == SignalStrength.STRONG and signal.edge > 0:
            if signal.sqpe_score >= self.sqpe_threshold:
                return "back", signal.confidence, f"SQPE: Strong convergence ({signal.convergence_score:.2f}), edge {signal.edge:.2%}"
        
        return "abstain", 0.0, "SQPE: Insufficient signal strength"
    
    def evaluate_tie_vote(self, signal: TIESignal) -> Tuple[str, float, str]:
        """
        Determine TIE's vote
        
        Returns:
            (vote, confidence, reasoning)
        """
        if signal.intent == TrainerIntent.WIN_TODAY:
            return "back", signal.confidence, f"TIE: WIN_TODAY intent detected (score {signal.tie_score:.2f})"
        
        elif signal.intent == TrainerIntent.PLACED_TO_WIN and signal.tie_score >= self.tie_threshold:
            return "back", signal.confidence, f"TIE: PLACED_TO_WIN (score {signal.tie_score:.2f})"
        
        elif signal.intent in [TrainerIntent.EXPERIENCE, TrainerIntent.DECEIVE]:
            return "fade", signal.confidence, f"TIE: {signal.intent.value} intent detected"
        
        return "abstain", 0.0, "TIE: Neutral intent"
    
    def evaluate_nds_vote(self, signal: NDSSignal) -> Tuple[str, float, str]:
        """
        Determine NDS's vote
        
        Returns:
            (vote, confidence, reasoning)
        """
        if signal.is_fade_opportunity and signal.nds_score >= self.nds_threshold:
            return "fade", signal.confidence, f"NDS: {signal.narrative_type.value} detected (score {signal.nds_score:.2f})"
        
        elif signal.is_back_opportunity:
            return "back", signal.confidence, f"NDS: Underbet longshot, no negative narrative"
        
        return "abstain", 0.0, "NDS: No clear narrative disruption"
    
    def calculate_agreement(
        self,
        votes: Dict[str, Tuple[str, float, str]]
    ) -> Tuple[int, int, float]:
        """
        Calculate agreement across modules
        
        Args:
            votes: Dict mapping module_name -> (vote, confidence, reasoning)
        
        Returns:
            (back_count, fade_count, agreement_score)
        """
        back_count = sum(1 for v, _, _ in votes.values() if v == "back")
        fade_count = sum(1 for v, _, _ in votes.values() if v == "fade")
        
        # Agreement score: weighted by confidence
        total_confidence = 0.0
        aligned_confidence = 0.0
        
        for vote, confidence, _ in votes.values():
            if vote != "abstain":
                total_confidence += confidence
                if vote == "back" and back_count >= fade_count:
                    aligned_confidence += confidence
                elif vote == "fade" and fade_count > back_count:
                    aligned_confidence += confidence
        
        agreement_score = aligned_confidence / total_confidence if total_confidence > 0 else 0.0
        
        return back_count, fade_count, agreement_score
    
    def make_recommendation(
        self,
        back_count: int,
        fade_count: int,
        agreement_score: float
    ) -> BetRecommendation:
        """
        Make final bet recommendation based on agreement
        
        Args:
            back_count: Number of modules voting "back"
            fade_count: Number of modules voting "fade"
            agreement_score: Overall agreement score
        
        Returns:
            BetRecommendation
        """
        # BACK recommendations
        if back_count >= 3:
            return BetRecommendation.STRONG_BACK
        elif back_count >= self.min_modules_required:
            return BetRecommendation.MODERATE_BACK
        
        # FADE recommendations
        elif fade_count >= 3:
            return BetRecommendation.STRONG_FADE
        elif fade_count >= self.min_modules_required:
            return BetRecommendation.MODERATE_FADE
        
        # HOLD (insufficient agreement)
        else:
            return BetRecommendation.HOLD
    
    def calculate_conviction(
        self,
        recommendation: BetRecommendation,
        agreement_score: float,
        back_count: int,
        fade_count: int
    ) -> float:
        """
        Calculate conviction strength
        
        Args:
            recommendation: Bet recommendation
            agreement_score: Agreement score
            back_count: Modules voting back
            fade_count: Modules voting fade
        
        Returns:
            Conviction (0-1)
        """
        if recommendation == BetRecommendation.HOLD:
            return 0.0
        
        # Base conviction from agreement score
        conviction = agreement_score
        
        # Boost for unanimous agreement
        if back_count == 3 or fade_count == 3:
            conviction *= 1.2
        
        return np.clip(conviction, 0, 1)
    
    def analyze_runner(
        self,
        runner: pd.Series,
        p_benter: float,
        p_public: float,
        historical_data: pd.DataFrame,
        market_overround: float
    ) -> IntelligenceSignal:
        """
        Analyze a single runner with all intelligence modules
        
        Args:
            runner: Runner data
            p_benter: Benter model probability
            p_public: Market probability
            historical_data: Historical race data
            market_overround: Market overround
        
        Returns:
            IntelligenceSignal with full analysis and recommendation
        """
        # Run each module
        sqpe_signal = self.sqpe.analyze_runner(runner, p_benter, p_public)
        tie_signal = self.tie.analyze_runner(runner, historical_data)
        nds_signal = self.nds.analyze_runner(runner, market_overround, historical_data)
        
        # Get votes
        sqpe_vote = self.evaluate_sqpe_vote(sqpe_signal)
        tie_vote = self.evaluate_tie_vote(tie_signal)
        nds_vote = self.evaluate_nds_vote(nds_signal)
        
        votes = {
            'SQPE': sqpe_vote,
            'TIE': tie_vote,
            'NDS': nds_vote
        }
        
        # Calculate agreement
        back_count, fade_count, agreement_score = self.calculate_agreement(votes)
        
        # Make recommendation
        recommendation = self.make_recommendation(back_count, fade_count, agreement_score)
        
        # Calculate conviction
        conviction = self.calculate_conviction(recommendation, agreement_score, back_count, fade_count)
        
        # Build reasoning
        reasoning = [reason for _, _, reason in votes.values() if reason]
        
        return IntelligenceSignal(
            runner_id=sqpe_signal.runner_id,
            horse_name=sqpe_signal.horse_name,
            odds=sqpe_signal.odds,
            sqpe_signal=sqpe_signal,
            tie_signal=tie_signal,
            nds_signal=nds_signal,
            modules_agree_back=back_count,
            modules_agree_fade=fade_count,
            agreement_score=agreement_score,
            recommendation=recommendation,
            conviction=conviction,
            reasoning=reasoning
        )
    
    def analyze_race(
        self,
        runners: pd.DataFrame,
        p_benter_dict: Dict[str, float],
        p_public_dict: Dict[str, float],
        historical_data: pd.DataFrame
    ) -> List[IntelligenceSignal]:
        """
        Analyze all runners in a race
        
        Args:
            runners: DataFrame of runners
            p_benter_dict: Benter probabilities
            p_public_dict: Public probabilities
            historical_data: Historical data
        
        Returns:
            List of IntelligenceSignal objects, sorted by conviction
        """
        # Calculate market overround
        market_overround = sum(p_public_dict.values())
        
        signals = []
        for idx, runner in runners.iterrows():
            runner_id = f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}"
            
            p_benter = p_benter_dict.get(runner_id, 0.0)
            p_public = p_public_dict.get(runner_id, 0.0)
            
            signal = self.analyze_runner(
                runner, p_benter, p_public, historical_data, market_overround
            )
            signals.append(signal)
        
        # Sort by conviction (descending)
        signals.sort(key=lambda x: x.conviction, reverse=True)
        
        return signals
    
    def filter_actionable_signals(
        self,
        signals: List[IntelligenceSignal]
    ) -> List[IntelligenceSignal]:
        """
        Filter to only actionable signals (BACK or FADE recommendations)
        
        Args:
            signals: List of intelligence signals
        
        Returns:
            Filtered list (excludes HOLD)
        """
        return [
            s for s in signals
            if s.recommendation != BetRecommendation.HOLD
        ]
    
    def get_back_recommendations(
        self,
        signals: List[IntelligenceSignal]
    ) -> List[IntelligenceSignal]:
        """
        Filter to only BACK recommendations
        
        Args:
            signals: List of intelligence signals
        
        Returns:
            Filtered list (STRONG_BACK and MODERATE_BACK only)
        """
        return [
            s for s in signals
            if s.recommendation in [BetRecommendation.STRONG_BACK, BetRecommendation.MODERATE_BACK]
        ]
    
    def get_fade_recommendations(
        self,
        signals: List[IntelligenceSignal]
    ) -> List[IntelligenceSignal]:
        """
        Filter to only FADE recommendations
        
        Args:
            signals: List of intelligence signals
        
        Returns:
            Filtered list (STRONG_FADE and MODERATE_FADE only)
        """
        return [
            s for s in signals
            if s.recommendation in [BetRecommendation.STRONG_FADE, BetRecommendation.MODERATE_FADE]
        ]

