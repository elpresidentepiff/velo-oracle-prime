"""
NDS - Narrative Disruption Scan

Purpose: Detect market misreads driven by hype, bias, or false narratives

The NDS identifies when the market has mispriced a horse due to:
- Media hype (overbet favorites)
- Recency bias (last race performance overweighted)
- False narratives (breeding, connections, "due to win")
- Behavioral biases (gambler's fallacy, hot hand fallacy)

Key Concepts:
- Narrative = Story the market believes
- Disruption = Reality contradicts the narrative
- Opportunity = Bet against the false narrative

Author: VÉLØ Oracle Team
Version: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class NarrativeType(Enum):
    """Types of market narratives"""
    HYPE_FAVORITE = "hype_favorite"           # Overbet due to media/hype
    RECENCY_BIAS = "recency_bias"             # Last race overweighted
    FALSE_FORM = "false_form"                 # Form looks better than it is
    BREEDING_BIAS = "breeding_bias"           # Overbet due to sire/dam
    CONNECTION_BIAS = "connection_bias"       # Overbet due to trainer/jockey
    DUE_TO_WIN = "due_to_win"                 # Gambler's fallacy
    HOT_STREAK = "hot_streak"                 # Hot hand fallacy
    NONE = "none"                             # No clear narrative


class DisruptionStrength(Enum):
    """Strength of narrative disruption"""
    STRONG = "strong"        # Clear disruption, high confidence
    MODERATE = "moderate"    # Some disruption
    WEAK = "weak"            # Minimal disruption
    NONE = "none"            # No disruption detected


@dataclass
class NDSSignal:
    """NDS analysis result for a single runner"""
    runner_id: str
    horse_name: str
    
    # Narrative detection
    narrative_type: NarrativeType
    narrative_strength: float         # How strong is the narrative (0-1)
    
    # Disruption signals
    overround_signal: float           # Market overround analysis (0-1)
    recency_signal: float             # Recency bias detection (0-1)
    form_quality_signal: float        # Form quality vs perception (0-1)
    odds_drift_signal: float          # Odds movement analysis (0-1)
    
    # Disruption classification
    disruption_strength: DisruptionStrength
    nds_score: float                  # Combined disruption score (0-1)
    confidence: float                 # Confidence in disruption (0-1)
    
    # Opportunity
    is_fade_opportunity: bool         # Bet against this horse
    is_back_opportunity: bool         # Bet on this horse
    
    # Metadata
    odds: float
    implied_prob: float
    market_overround: float


class NDS:
    """
    Narrative Disruption Scan
    
    Detects market misreads caused by false narratives and behavioral biases.
    """
    
    def __init__(
        self,
        overround_threshold: float = 1.15,
        recency_weight: float = 0.7,
        min_disruption_score: float = 0.6
    ):
        """
        Initialize NDS engine
        
        Args:
            overround_threshold: Market overround threshold for hype detection
            recency_weight: Weight given to last race vs historical form
            min_disruption_score: Minimum score for disruption classification
        """
        self.overround_threshold = overround_threshold
        self.recency_weight = recency_weight
        self.min_disruption_score = min_disruption_score
    
    def calculate_overround_signal(
        self,
        runner_odds: float,
        market_overround: float
    ) -> float:
        """
        Detect if horse is overbet relative to market efficiency
        
        High overround + short odds = hype favorite
        
        Args:
            runner_odds: Decimal odds for this runner
            market_overround: Total market overround (sum of implied probs)
        
        Returns:
            Signal strength (0-1), higher = more overbet
        """
        implied_prob = 1.0 / runner_odds
        
        # If market overround is high AND this horse has short odds
        # it's likely overbet
        if market_overround > self.overround_threshold and runner_odds < 5.0:
            # Signal strength proportional to how much it contributes to overround
            signal = np.clip(implied_prob * market_overround / 2.0, 0, 1)
            return signal
        
        return 0.0
    
    def calculate_recency_signal(
        self,
        runner: pd.Series,
        historical_data: pd.DataFrame
    ) -> float:
        """
        Detect recency bias (last race overweighted)
        
        If last race was exceptional but historical form is poor,
        the market may be overweighting recent performance.
        
        Args:
            runner: Current runner data
            historical_data: Historical runs for this horse
        
        Returns:
            Signal strength (0-1), higher = stronger recency bias
        """
        horse = runner.get('horse')
        current_date = pd.to_datetime(runner.get('date'))
        
        # Get historical runs for this horse
        prev_runs = historical_data[
            (historical_data['horse'] == horse) &
            (pd.to_datetime(historical_data['date']) < current_date)
        ].sort_values('date', ascending=False)
        
        if len(prev_runs) < 3:
            return 0.0  # Insufficient data
        
        # Last race position
        last_pos = prev_runs.iloc[0].get('pos_int')
        
        # Historical average position (excluding last race)
        hist_positions = prev_runs.iloc[1:6]['pos_int'].dropna()
        if len(hist_positions) == 0:
            return 0.0
        
        avg_hist_pos = hist_positions.mean()
        
        # If last race was much better than historical average
        if pd.notna(last_pos) and last_pos <= 3 and avg_hist_pos > 6:
            # Strong recency bias signal
            signal = np.clip((avg_hist_pos - last_pos) / 10.0, 0, 1)
            return signal
        
        return 0.0
    
    def calculate_form_quality_signal(
        self,
        runner: pd.Series,
        historical_data: pd.DataFrame
    ) -> float:
        """
        Detect false form (form looks better than it is)
        
        Example: Won last 2 races but against weak opposition
        
        Args:
            runner: Current runner data
            historical_data: Historical runs for this horse
        
        Returns:
            Signal strength (0-1), higher = more false form
        """
        horse = runner.get('horse')
        current_date = pd.to_datetime(runner.get('date'))
        
        prev_runs = historical_data[
            (historical_data['horse'] == horse) &
            (pd.to_datetime(historical_data['date']) < current_date)
        ].sort_values('date', ascending=False).head(5)
        
        if len(prev_runs) < 3:
            return 0.0
        
        # Check if recent wins were in lower class
        current_class = runner.get('class', 4)
        
        wins_in_lower_class = 0
        for _, run in prev_runs.iterrows():
            if run.get('pos_int') == 1:
                run_class = run.get('class', 4)
                try:
                    if int(run_class) > int(current_class):  # Higher number = lower class
                        wins_in_lower_class += 1
                except:
                    pass
        
        if wins_in_lower_class >= 2:
            # Form is false - won in lower class, now stepping up
            return 0.8
        
        return 0.0
    
    def calculate_odds_drift_signal(
        self,
        runner: pd.Series
    ) -> float:
        """
        Detect odds drift (money leaving the horse)
        
        If odds are drifting, smart money may be fading the narrative
        
        Args:
            runner: Runner data (would need historical odds in production)
        
        Returns:
            Signal strength (0-1), higher = more drift
        """
        # TODO: Requires historical odds data
        # For now, placeholder
        return 0.0
    
    def detect_narrative_type(
        self,
        runner: pd.Series,
        overround_signal: float,
        recency_signal: float,
        form_quality_signal: float
    ) -> NarrativeType:
        """
        Classify the type of narrative affecting this horse
        
        Args:
            runner: Runner data
            overround_signal: Overround signal strength
            recency_signal: Recency bias signal strength
            form_quality_signal: Form quality signal strength
        
        Returns:
            NarrativeType classification
        """
        odds = runner.get('sp_decimal', 100)
        
        # HYPE_FAVORITE: Short odds + high overround
        if odds < 3.0 and overround_signal > 0.6:
            return NarrativeType.HYPE_FAVORITE
        
        # RECENCY_BIAS: Strong recency signal
        if recency_signal > 0.6:
            return NarrativeType.RECENCY_BIAS
        
        # FALSE_FORM: Strong form quality signal
        if form_quality_signal > 0.6:
            return NarrativeType.FALSE_FORM
        
        # DUE_TO_WIN: Long losing streak, short odds
        # (market thinks "due to win" - gambler's fallacy)
        if odds < 5.0:
            # Check for losing streak
            # TODO: Implement streak detection
            pass
        
        return NarrativeType.NONE
    
    def calculate_narrative_strength(
        self,
        narrative_type: NarrativeType,
        signals: Dict[str, float]
    ) -> float:
        """
        Calculate how strong the narrative is
        
        Args:
            narrative_type: Type of narrative
            signals: Dict of signal strengths
        
        Returns:
            Narrative strength (0-1)
        """
        if narrative_type == NarrativeType.NONE:
            return 0.0
        
        # Average of relevant signals
        return np.mean(list(signals.values()))
    
    def classify_disruption_strength(
        self,
        nds_score: float
    ) -> DisruptionStrength:
        """
        Classify disruption strength
        
        Args:
            nds_score: NDS score (0-1)
        
        Returns:
            DisruptionStrength classification
        """
        if nds_score >= self.min_disruption_score:
            return DisruptionStrength.STRONG
        elif nds_score >= 0.4:
            return DisruptionStrength.MODERATE
        elif nds_score >= 0.2:
            return DisruptionStrength.WEAK
        else:
            return DisruptionStrength.NONE
    
    def calculate_nds_score(
        self,
        signals: Dict[str, float],
        narrative_strength: float
    ) -> float:
        """
        Calculate final NDS score
        
        High score = strong disruption = betting opportunity
        
        Args:
            signals: Dict of signal strengths
            narrative_strength: How strong the narrative is
        
        Returns:
            NDS score (0-1)
        """
        # Average of disruption signals
        avg_signal = np.mean(list(signals.values()))
        
        # Weight by narrative strength
        # Strong narrative + strong disruption = high opportunity
        score = avg_signal * narrative_strength
        
        return np.clip(score, 0, 1)
    
    def identify_opportunities(
        self,
        narrative_type: NarrativeType,
        disruption_strength: DisruptionStrength,
        odds: float
    ) -> Tuple[bool, bool]:
        """
        Identify betting opportunities
        
        Args:
            narrative_type: Type of narrative
            disruption_strength: Strength of disruption
            odds: Decimal odds
        
        Returns:
            (is_fade_opportunity, is_back_opportunity)
        """
        is_fade = False
        is_back = False
        
        # FADE opportunities (bet against)
        if disruption_strength in [DisruptionStrength.STRONG, DisruptionStrength.MODERATE]:
            if narrative_type in [
                NarrativeType.HYPE_FAVORITE,
                NarrativeType.RECENCY_BIAS,
                NarrativeType.FALSE_FORM
            ]:
                is_fade = True
        
        # BACK opportunities (bet on)
        # If a longshot has no negative narrative, it might be underbet
        if (narrative_type == NarrativeType.NONE and
            odds > 10.0 and
            disruption_strength == DisruptionStrength.NONE):
            is_back = True
        
        return is_fade, is_back
    
    def analyze_runner(
        self,
        runner: pd.Series,
        market_overround: float,
        historical_data: pd.DataFrame
    ) -> NDSSignal:
        """
        Analyze narrative disruption for a single runner
        
        Args:
            runner: Runner data
            market_overround: Total market overround
            historical_data: Historical race data
        
        Returns:
            NDSSignal object with full analysis
        """
        odds = runner.get('sp_decimal', 100)
        implied_prob = 1.0 / odds if odds > 0 else 0.0
        
        # Calculate signals
        overround_signal = self.calculate_overround_signal(odds, market_overround)
        recency_signal = self.calculate_recency_signal(runner, historical_data)
        form_quality_signal = self.calculate_form_quality_signal(runner, historical_data)
        odds_drift_signal = self.calculate_odds_drift_signal(runner)
        
        signals = {
            'overround': overround_signal,
            'recency': recency_signal,
            'form_quality': form_quality_signal,
            'odds_drift': odds_drift_signal
        }
        
        # Detect narrative
        narrative_type = self.detect_narrative_type(
            runner, overround_signal, recency_signal, form_quality_signal
        )
        
        # Calculate narrative strength
        narrative_strength = self.calculate_narrative_strength(narrative_type, signals)
        
        # Calculate NDS score
        nds_score = self.calculate_nds_score(signals, narrative_strength)
        
        # Classify disruption
        disruption_strength = self.classify_disruption_strength(nds_score)
        
        # Identify opportunities
        is_fade, is_back = self.identify_opportunities(
            narrative_type, disruption_strength, odds
        )
        
        # Confidence (inverse of signal variance)
        confidence = 1.0 - np.clip(np.std(list(signals.values())), 0, 1)
        
        return NDSSignal(
            runner_id=f"{runner.get('date')}_{runner.get('course')}_{runner.get('num')}",
            horse_name=runner.get('horse', 'Unknown'),
            narrative_type=narrative_type,
            narrative_strength=narrative_strength,
            overround_signal=overround_signal,
            recency_signal=recency_signal,
            form_quality_signal=form_quality_signal,
            odds_drift_signal=odds_drift_signal,
            disruption_strength=disruption_strength,
            nds_score=nds_score,
            confidence=confidence,
            is_fade_opportunity=is_fade,
            is_back_opportunity=is_back,
            odds=odds,
            implied_prob=implied_prob,
            market_overround=market_overround
        )
    
    def analyze_race(
        self,
        runners: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> List[NDSSignal]:
        """
        Analyze all runners in a race for narrative disruption
        
        Args:
            runners: DataFrame of runners in race
            historical_data: Historical race data
        
        Returns:
            List of NDSSignal objects, sorted by nds_score (descending)
        """
        # Calculate market overround
        total_implied_prob = (1.0 / runners['sp_decimal']).sum()
        market_overround = total_implied_prob
        
        signals = []
        for idx, runner in runners.iterrows():
            signal = self.analyze_runner(runner, market_overround, historical_data)
            signals.append(signal)
        
        # Sort by NDS score (descending)
        signals.sort(key=lambda x: x.nds_score, reverse=True)
        
        return signals
    
    def get_fade_opportunities(
        self,
        signals: List[NDSSignal]
    ) -> List[NDSSignal]:
        """
        Filter to only fade opportunities
        
        Args:
            signals: List of NDS signals
        
        Returns:
            Filtered list of fade opportunities
        """
        return [s for s in signals if s.is_fade_opportunity]
    
    def get_back_opportunities(
        self,
        signals: List[NDSSignal]
    ) -> List[NDSSignal]:
        """
        Filter to only back opportunities
        
        Args:
            signals: List of NDS signals
        
        Returns:
            Filtered list of back opportunities
        """
        return [s for s in signals if s.is_back_opportunity]

