#!/usr/bin/env python3
"""
VELO Decision Policy (Anti-House Chassis)
Final decision layer with strategic bet chassis logic

Hard rules:
1. In Chaos races: default = Top-4 chassis. Win only when:
   - Release Horse + Intent Win + market not manipulated + ablation stable

2. In Structure races: allow win overlays if:
   - stability + pace geometry + intent converge

Outputs must include:
- top_strike_selection
- top_4_structure
- fade_zone_runners (probabilistic)
- market_roles per runner
- learning_gate_status

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BetChassisType(Enum):
    """Bet chassis types."""
    WIN_OVERLAY = "Win_Overlay"
    TOP_4_STRUCTURE = "Top_4_Structure"
    VALUE_EW = "Value_EW"
    FADE_ONLY = "Fade_Only"
    SUPPRESS = "Suppress"


@dataclass
class DecisionOutput:
    """Final decision output from policy."""
    chassis_type: BetChassisType
    top_strike_selection: Optional[str] = None
    top_4_structure: List[str] = field(default_factory=list)
    value_ew: List[str] = field(default_factory=list)
    fade_zone: List[str] = field(default_factory=list)
    market_roles: Dict[str, str] = field(default_factory=dict)
    win_suppressed: bool = False
    suppression_reason: Optional[str] = None
    confidence: float = 0.0
    learning_gate_status: str = "pending"
    notes: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'chassis_type': self.chassis_type.value,
            'top_strike_selection': self.top_strike_selection,
            'top_4_structure': self.top_4_structure,
            'value_ew': self.value_ew,
            'fade_zone': self.fade_zone,
            'market_roles': self.market_roles,
            'win_suppressed': self.win_suppressed,
            'suppression_reason': self.suppression_reason,
            'confidence': self.confidence,
            'learning_gate_status': self.learning_gate_status,
            'notes': self.notes
        }


class DecisionPolicy:
    """
    Decision Policy Engine.
    
    Implements anti-house chassis logic with strategic bet selection.
    """
    
    # Thresholds
    CHAOS_THRESHOLD = 0.60
    STABILITY_THRESHOLD = 0.65
    MANIPULATION_THRESHOLD = 0.60
    ABLATION_FRAGILITY_THRESHOLD = 2
    
    def __init__(self):
        logger.info("Decision Policy initialized (Anti-House Chassis)")
    
    def decide(
        self,
        race_ctx: Dict,
        runner_profiles: List[Dict],
        engine_outputs: Dict,
        ablation_results: Dict,
        ctf_report: Dict
    ) -> DecisionOutput:
        """
        Make final decision using anti-house chassis logic.
        
        Args:
            race_ctx: Race context
            runner_profiles: Opponent profiles for all runners
            engine_outputs: Engine scores and predictions
            ablation_results: Ablation test results
            ctf_report: Cognitive trap firewall report
            
        Returns:
            DecisionOutput
        """
        logger.info(f"Decision Policy evaluating race: {race_ctx.get('race_id', 'unknown')}")
        
        # Extract key metrics
        chaos_level = engine_outputs.get('chaos_level', 0.0)
        manipulation_risk = engine_outputs.get('manipulation_risk', 0.0)
        stability_score = engine_outputs.get('stability_score', 0.0)
        
        # Check if CTF adjusted decision
        ctf_adjusted = ctf_report.get('decision_adjusted', False)
        
        # Determine race type
        is_chaos = chaos_level >= self.CHAOS_THRESHOLD
        is_manipulated = manipulation_risk >= self.MANIPULATION_THRESHOLD
        is_fragile = ablation_results.get('fragile', False)
        
        # Build market roles map
        market_roles = {}
        for profile in runner_profiles:
            runner_id = profile.get('runner_id')
            market_role = profile.get('market_role', 'Noise')
            market_roles[runner_id] = market_role
        
        # Get top predictions
        top_predictions = engine_outputs.get('top_predictions', [])
        if not top_predictions:
            # Fallback: create from runner profiles
            top_predictions = sorted(
                runner_profiles,
                key=lambda r: r.get('final_score', 0.0),
                reverse=True
            )[:4]
        
        top_4_ids = [r.get('runner_id') for r in top_predictions[:4]]
        top_selection = top_4_ids[0] if top_4_ids else None
        
        # Decision logic
        if is_chaos:
            decision = self._decide_chaos_race(
                top_selection,
                top_4_ids,
                runner_profiles,
                engine_outputs,
                ablation_results,
                ctf_adjusted,
                is_manipulated,
                is_fragile
            )
        else:
            decision = self._decide_structure_race(
                top_selection,
                top_4_ids,
                runner_profiles,
                engine_outputs,
                ablation_results,
                ctf_adjusted,
                is_fragile
            )
        
        # Add market roles
        decision.market_roles = market_roles
        
        # Add notes
        decision.notes = {
            'chaos_level': chaos_level,
            'manipulation_risk': manipulation_risk,
            'stability_score': stability_score,
            'is_chaos': is_chaos,
            'is_manipulated': is_manipulated,
            'is_fragile': is_fragile,
            'ctf_adjusted': ctf_adjusted
        }
        
        logger.info(f"Decision: Chassis={decision.chassis_type.value}, Win suppressed={decision.win_suppressed}")
        return decision
    
    def _decide_chaos_race(
        self,
        top_selection: str,
        top_4_ids: List[str],
        runner_profiles: List[Dict],
        engine_outputs: Dict,
        ablation_results: Dict,
        ctf_adjusted: bool,
        is_manipulated: bool,
        is_fragile: bool
    ) -> DecisionOutput:
        """
        Decision logic for chaos races.
        
        Default = Top-4 chassis. Win only when:
        - Release Horse + Intent Win + market not manipulated + ablation stable
        """
        # Find top selection profile
        top_profile = None
        for profile in runner_profiles:
            if profile.get('runner_id') == top_selection:
                top_profile = profile
                break
        
        # Check win conditions
        is_release = top_profile and top_profile.get('market_role') == 'Release_Horse'
        intent_win = top_profile and top_profile.get('intent_class') == 'Win'
        
        # Decide chassis
        if is_release and intent_win and not is_manipulated and not is_fragile and not ctf_adjusted:
            # Allow win overlay
            return DecisionOutput(
                chassis_type=BetChassisType.WIN_OVERLAY,
                top_strike_selection=top_selection,
                top_4_structure=top_4_ids,
                win_suppressed=False,
                confidence=0.75,
                notes={'reason': 'Release + Intent + Clean'}
            )
        else:
            # Default to Top-4 chassis
            suppression_reasons = []
            if not is_release:
                suppression_reasons.append("Not Release Horse")
            if not intent_win:
                suppression_reasons.append("Intent not Win")
            if is_manipulated:
                suppression_reasons.append("Manipulation detected")
            if is_fragile:
                suppression_reasons.append("Ablation fragile")
            if ctf_adjusted:
                suppression_reasons.append("CTF adjusted")
            
            return DecisionOutput(
                chassis_type=BetChassisType.TOP_4_STRUCTURE,
                top_4_structure=top_4_ids,
                win_suppressed=True,
                suppression_reason="; ".join(suppression_reasons),
                confidence=0.60,
                notes={'reason': 'Chaos race - Top-4 only'}
            )
    
    def _decide_structure_race(
        self,
        top_selection: str,
        top_4_ids: List[str],
        runner_profiles: List[Dict],
        engine_outputs: Dict,
        ablation_results: Dict,
        ctf_adjusted: bool,
        is_fragile: bool
    ) -> DecisionOutput:
        """
        Decision logic for structure races.
        
        Allow win overlays if: stability + pace geometry + intent converge
        """
        stability_score = engine_outputs.get('stability_score', 0.0)
        pace_geometry_score = engine_outputs.get('pace_geometry_score', 0.0)
        
        # Find top selection profile
        top_profile = None
        for profile in runner_profiles:
            if profile.get('runner_id') == top_selection:
                top_profile = profile
                break
        
        intent_win = top_profile and top_profile.get('intent_class') == 'Win'
        
        # Check convergence
        convergence = (
            stability_score >= self.STABILITY_THRESHOLD and
            pace_geometry_score >= 0.65 and
            intent_win and
            not is_fragile and
            not ctf_adjusted
        )
        
        if convergence:
            # Allow win overlay
            return DecisionOutput(
                chassis_type=BetChassisType.WIN_OVERLAY,
                top_strike_selection=top_selection,
                top_4_structure=top_4_ids,
                win_suppressed=False,
                confidence=0.80,
                notes={'reason': 'Structure + Convergence'}
            )
        else:
            # Top-4 chassis
            return DecisionOutput(
                chassis_type=BetChassisType.TOP_4_STRUCTURE,
                top_4_structure=top_4_ids,
                win_suppressed=True,
                suppression_reason="Convergence failed",
                confidence=0.65,
                notes={'reason': 'Structure race - convergence not met'}
            )


def make_decision(
    race_ctx: Dict,
    runner_profiles: List[Dict],
    engine_outputs: Dict,
    ablation_results: Dict,
    ctf_report: Dict
) -> DecisionOutput:
    """
    Convenience function to make decision.
    
    Args:
        race_ctx: Race context
        runner_profiles: Runner profiles
        engine_outputs: Engine outputs
        ablation_results: Ablation results
        ctf_report: CTF report
        
    Returns:
        DecisionOutput
    """
    policy = DecisionPolicy()
    return policy.decide(race_ctx, runner_profiles, engine_outputs, ablation_results, ctf_report)


if __name__ == "__main__":
    # Example usage
    race_ctx = {
        'race_id': 'test_001',
        'chaos_level': 0.35
    }
    
    runner_profiles = [
        {
            'runner_id': 'r1',
            'horse_name': 'Horse A',
            'market_role': 'Release_Horse',
            'intent_class': 'Win',
            'final_score': 0.85
        },
        {
            'runner_id': 'r2',
            'horse_name': 'Horse B',
            'market_role': 'Noise',
            'intent_class': 'Place',
            'final_score': 0.75
        }
    ]
    
    engine_outputs = {
        'chaos_level': 0.35,
        'manipulation_risk': 0.25,
        'stability_score': 0.78,
        'pace_geometry_score': 0.72,
        'top_predictions': runner_profiles
    }
    
    ablation_results = {
        'fragile': False,
        'flip_count': 0
    }
    
    ctf_report = {
        'decision_adjusted': False
    }
    
    decision = make_decision(race_ctx, runner_profiles, engine_outputs, ablation_results, ctf_report)
    print(f"Decision: {decision.to_dict()}")
