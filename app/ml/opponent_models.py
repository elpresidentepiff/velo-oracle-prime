#!/usr/bin/env python3
"""
VELO Opponent Models (GTI - Game Theory Intelligence)
Treats market and trainers as strategic agents, not information sources

Stop treating the market as "information." Treat it as an agent.

Opponent/Agent modules:
1. Trainer Agent: objective = win vs place vs conditioning vs handicap manipulation
2. Market Agent: objective = balance book / trap liquidity / move price
3. Stable Agent: multi-runner tactics (one sets pace, one finishes)

Outputs:
- intent_class: {Win, Place, Prep, Mark-Adjust, Unknown}
- market_role: {Liquidity_Anchor, Release_Horse, Spoiler, Steam, Drift_Bait}
- stable_tactic: {Pace_Setter, Cover, Finisher, Decoy}

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntentClass(Enum):
    """Trainer/owner intent classification."""
    WIN = "Win"
    PLACE = "Place"
    PREP = "Prep"
    MARK_ADJUST = "Mark-Adjust"
    UNKNOWN = "Unknown"


class MarketRole(Enum):
    """Market role classification."""
    LIQUIDITY_ANCHOR = "Liquidity_Anchor"
    RELEASE_HORSE = "Release_Horse"
    SPOILER = "Spoiler"
    STEAM = "Steam"
    DRIFT_BAIT = "Drift_Bait"
    NOISE = "Noise"


class StableTactic(Enum):
    """Multi-runner stable tactic."""
    PACE_SETTER = "Pace_Setter"
    COVER = "Cover"
    FINISHER = "Finisher"
    DECOY = "Decoy"
    SOLO = "Solo"


@dataclass
class OpponentProfile:
    """Complete opponent/agent profile for a runner."""
    runner_id: str
    horse_name: str
    intent_class: IntentClass
    market_role: MarketRole
    stable_tactic: StableTactic
    confidence: float = 0.0
    evidence: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'runner_id': self.runner_id,
            'horse_name': self.horse_name,
            'intent_class': self.intent_class.value,
            'market_role': self.market_role.value,
            'stable_tactic': self.stable_tactic.value,
            'confidence': self.confidence,
            'evidence': self.evidence
        }


class TrainerAgentModel:
    """
    Trainer Agent Model.
    
    Models trainer intent: Win vs Place vs Prep vs Mark manipulation.
    """
    
    def __init__(self):
        logger.info("Trainer Agent Model initialized")
    
    def classify_intent(self, runner_data: Dict, race_ctx: Dict) -> IntentClass:
        """
        Classify trainer intent for this runner.
        
        Args:
            runner_data: Runner data
            race_ctx: Race context
            
        Returns:
            IntentClass
        """
        # HEURISTIC IMPLEMENTATION (replace with learned model)
        
        # Evidence markers
        evidence = {}
        
        # Check for "go" signals
        notable_jockey = runner_data.get('jockey_booking_notable', False)
        first_time_headgear = runner_data.get('first_time_headgear', False)
        quick_turnaround = runner_data.get('days_since_last') and runner_data['days_since_last'] < 14
        
        # Check for "prep" signals
        long_layoff = runner_data.get('days_since_last') and runner_data['days_since_last'] > 90
        class_rise = runner_data.get('class_movement', 0) > 0
        
        # Check for "mark adjust" signals
        career_high_mark = runner_data.get('mark_pressure') == 'career_high'
        recent_poor_form = runner_data.get('form_last_3', 1.0) < 0.2
        
        # Classify
        if notable_jockey and not long_layoff:
            return IntentClass.WIN
        elif long_layoff or class_rise:
            return IntentClass.PREP
        elif career_high_mark and recent_poor_form:
            return IntentClass.MARK_ADJUST
        else:
            return IntentClass.UNKNOWN


class MarketAgentModel:
    """
    Market Agent Model.
    
    Models market as strategic agent: Liquidity Anchor vs Release Horse.
    """
    
    def __init__(self):
        logger.info("Market Agent Model initialized")
    
    def classify_market_role(
        self,
        runner_data: Dict,
        market_ctx: Dict,
        race_ctx: Dict
    ) -> MarketRole:
        """
        Classify market role for this runner.
        
        CRITICAL HEURISTIC (War Mode v1):
        - Liquidity Anchor: short price, absorbs money, often places but doesn't win
        - Release Horse: mid price, stable cluster, intent markers, wins more than implied
        
        Args:
            runner_data: Runner data
            market_ctx: Market context
            race_ctx: Race context
            
        Returns:
            MarketRole
        """
        odds = runner_data.get('odds_decimal', 10.0)
        is_favorite = runner_data.get('is_favorite', False)
        
        # Get historical win rate vs implied probability
        win_rate = runner_data.get('win_rate_historical', 0.0)
        implied_prob = 1.0 / odds if odds > 0 else 0.0
        
        # Liquidity Anchor detection
        # Short price + trades strong but underperforms win expectation
        if is_favorite and win_rate < implied_prob * 0.7:
            return MarketRole.LIQUIDITY_ANCHOR
        
        # Release Horse detection
        # Mid price + wins more than market implies
        if 3.0 <= odds <= 8.0 and win_rate > implied_prob * 1.2:
            return MarketRole.RELEASE_HORSE
        
        # Steam detection (sharp money)
        odds_drift = runner_data.get('odds_drift', 0.0)
        if odds_drift < -0.3:  # Significant shortening
            return MarketRole.STEAM
        
        # Drift Bait detection
        if odds_drift > 0.3:  # Significant drifting
            return MarketRole.DRIFT_BAIT
        
        # Default
        return MarketRole.NOISE


class StableAgentModel:
    """
    Stable Agent Model.
    
    Models multi-runner stable tactics: Pace setter + Finisher combinations.
    """
    
    def __init__(self):
        logger.info("Stable Agent Model initialized")
    
    def detect_multi_runner_tactics(
        self,
        runners: List[Dict],
        race_ctx: Dict
    ) -> Dict[str, StableTactic]:
        """
        Detect multi-runner stable tactics.
        
        Args:
            runners: List of all runners in race
            race_ctx: Race context
            
        Returns:
            Dict mapping runner_id to StableTactic
        """
        tactics = {}
        
        # Group by trainer
        trainer_groups = {}
        for runner in runners:
            trainer = runner.get('trainer', 'unknown')
            if trainer not in trainer_groups:
                trainer_groups[trainer] = []
            trainer_groups[trainer].append(runner)
        
        # Analyze each trainer group
        for trainer, stable_runners in trainer_groups.items():
            if len(stable_runners) == 1:
                # Solo runner
                tactics[stable_runners[0]['runner_id']] = StableTactic.SOLO
            elif len(stable_runners) >= 2:
                # Multi-runner tactics
                # HEURISTIC: Assign based on pace style and odds
                stable_runners_sorted = sorted(stable_runners, key=lambda r: r.get('odds_decimal', 100))
                
                for i, runner in enumerate(stable_runners_sorted):
                    runner_id = runner['runner_id']
                    pace_style = runner.get('pace_style', 'unknown')
                    
                    # Assign tactic
                    if i == 0:
                        # Shortest price = likely finisher
                        tactics[runner_id] = StableTactic.FINISHER
                    elif pace_style == 'front_runner':
                        tactics[runner_id] = StableTactic.PACE_SETTER
                    else:
                        tactics[runner_id] = StableTactic.COVER
        
        return tactics


class OpponentModelEngine:
    """
    Opponent Model Engine.
    
    Coordinates all opponent models to produce complete profiles.
    """
    
    def __init__(self):
        self.trainer_model = TrainerAgentModel()
        self.market_model = MarketAgentModel()
        self.stable_model = StableAgentModel()
        logger.info("Opponent Model Engine initialized (War Mode)")
    
    def profile_runners(
        self,
        runners: List[Dict],
        race_ctx: Dict,
        market_ctx: Dict
    ) -> List[OpponentProfile]:
        """
        Generate opponent profiles for all runners.
        
        Args:
            runners: List of runner data
            race_ctx: Race context
            market_ctx: Market context
            
        Returns:
            List of OpponentProfile
        """
        logger.info(f"Profiling {len(runners)} runners")
        
        # Detect stable tactics first (requires all runners)
        stable_tactics = self.stable_model.detect_multi_runner_tactics(runners, race_ctx)
        
        profiles = []
        
        for runner in runners:
            runner_id = runner.get('runner_id', 'unknown')
            horse_name = runner.get('horse_name', 'unknown')
            
            # Classify intent
            intent = self.trainer_model.classify_intent(runner, race_ctx)
            
            # Classify market role
            market_role = self.market_model.classify_market_role(runner, market_ctx, race_ctx)
            
            # Get stable tactic
            stable_tactic = stable_tactics.get(runner_id, StableTactic.SOLO)
            
            # Calculate confidence (simplified)
            confidence = 0.7  # Placeholder
            
            # Collect evidence
            evidence = {
                'odds': runner.get('odds_decimal'),
                'is_favorite': runner.get('is_favorite', False),
                'trainer': runner.get('trainer'),
                'jockey': runner.get('jockey')
            }
            
            profile = OpponentProfile(
                runner_id=runner_id,
                horse_name=horse_name,
                intent_class=intent,
                market_role=market_role,
                stable_tactic=stable_tactic,
                confidence=confidence,
                evidence=evidence
            )
            
            profiles.append(profile)
        
        logger.info(f"Generated {len(profiles)} opponent profiles")
        return profiles


def profile_race_opponents(
    runners: List[Dict],
    race_ctx: Dict,
    market_ctx: Dict
) -> List[OpponentProfile]:
    """
    Convenience function to profile race opponents.
    
    Args:
        runners: Runner data
        race_ctx: Race context
        market_ctx: Market context
        
    Returns:
        List of OpponentProfile
    """
    engine = OpponentModelEngine()
    return engine.profile_runners(runners, race_ctx, market_ctx)


if __name__ == "__main__":
    # Example usage
    runners = [
        {
            'runner_id': 'r1',
            'horse_name': 'Horse A',
            'trainer': 'Trainer X',
            'jockey': 'Jockey A',
            'odds_decimal': 3.5,
            'is_favorite': True,
            'win_rate_historical': 0.20,
            'pace_style': 'closer'
        },
        {
            'runner_id': 'r2',
            'horse_name': 'Horse B',
            'trainer': 'Trainer X',
            'jockey': 'Jockey B',
            'odds_decimal': 8.0,
            'is_favorite': False,
            'win_rate_historical': 0.15,
            'pace_style': 'front_runner'
        },
        {
            'runner_id': 'r3',
            'horse_name': 'Horse C',
            'trainer': 'Trainer Y',
            'jockey': 'Jockey C',
            'odds_decimal': 5.0,
            'is_favorite': False,
            'win_rate_historical': 0.25,
            'pace_style': 'mid_pack'
        }
    ]
    
    race_ctx = {
        'race_id': 'test_001',
        'course': 'Newmarket',
        'distance': 1200
    }
    
    market_ctx = {
        'snapshot_timestamp': '2025-12-17T14:00:00'
    }
    
    profiles = profile_race_opponents(runners, race_ctx, market_ctx)
    
    for profile in profiles:
        print(f"\n{profile.horse_name}:")
        print(f"  Intent: {profile.intent_class.value}")
        print(f"  Market Role: {profile.market_role.value}")
        print(f"  Stable Tactic: {profile.stable_tactic.value}")
