#!/usr/bin/env python3
"""
VELO Post-Race Self-Critique Loop
Mandatory post-race analysis and learning update

When result arrives:
1. Assign market roles retrospectively
2. Evaluate gate decision correctness
3. Update quarantine promotion counters
4. Write a "why we lost/won" record
5. Adjust thresholds

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class PostRaceCritique:
    """Post-race critique and analysis."""
    race_id: str
    engine_run_id: str
    critique_timestamp: datetime
    
    # Retrospective analysis
    actual_winner: str
    predicted_winner: Optional[str]
    prediction_correct: bool
    top_4_hit: bool
    
    # Market role validation
    market_roles_assigned: Dict[str, str] = field(default_factory=dict)
    market_roles_validated: Dict[str, bool] = field(default_factory=dict)
    
    # Learning gate evaluation
    gate_decision_correct: bool = False
    gate_decision_reason: str = ""
    
    # Root cause analysis
    why_won: List[str] = field(default_factory=list)
    why_lost: List[str] = field(default_factory=list)
    
    # Threshold adjustments
    threshold_adjustments: Dict[str, float] = field(default_factory=dict)
    
    # Quarantine updates
    quarantine_promotions: int = 0
    quarantine_rejections: int = 0
    
    notes: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'race_id': self.race_id,
            'engine_run_id': self.engine_run_id,
            'critique_timestamp': self.critique_timestamp.isoformat(),
            'actual_winner': self.actual_winner,
            'predicted_winner': self.predicted_winner,
            'prediction_correct': self.prediction_correct,
            'top_4_hit': self.top_4_hit,
            'market_roles_assigned': self.market_roles_assigned,
            'market_roles_validated': self.market_roles_validated,
            'gate_decision_correct': self.gate_decision_correct,
            'gate_decision_reason': self.gate_decision_reason,
            'why_won': self.why_won,
            'why_lost': self.why_lost,
            'threshold_adjustments': self.threshold_adjustments,
            'quarantine_promotions': self.quarantine_promotions,
            'quarantine_rejections': self.quarantine_rejections,
            'notes': self.notes
        }


class PostRaceCritiqueEngine:
    """
    Post-Race Critique Engine.
    
    Performs mandatory post-race analysis and learning updates.
    """
    
    def __init__(self):
        logger.info("Post-Race Critique Engine initialized")
    
    def critique(
        self,
        race_id: str,
        engine_run_id: str,
        engine_run_data: Dict,
        race_result: Dict,
        learning_gate_result: Dict
    ) -> PostRaceCritique:
        """
        Perform post-race critique.
        
        Args:
            race_id: Race ID
            engine_run_id: Engine run ID
            engine_run_data: Original engine run data
            race_result: Actual race result
            learning_gate_result: Learning gate decision
            
        Returns:
            PostRaceCritique
        """
        logger.info(f"Post-race critique for race: {race_id}")
        
        critique = PostRaceCritique(
            race_id=race_id,
            engine_run_id=engine_run_id,
            critique_timestamp=datetime.now(),
            actual_winner=race_result.get('winner_id', 'unknown'),
            predicted_winner=engine_run_data.get('verdict', {}).get('top_strike_selection')
        )
        
        # 1. Assign market roles retrospectively
        self._assign_market_roles_retrospective(critique, engine_run_data, race_result)
        
        # 2. Evaluate gate decision correctness
        self._evaluate_gate_decision(critique, engine_run_data, race_result, learning_gate_result)
        
        # 3. Update quarantine promotion counters
        self._update_quarantine_counters(critique, learning_gate_result, race_result)
        
        # 4. Write "why we lost/won" record
        self._analyze_why_won_lost(critique, engine_run_data, race_result)
        
        # 5. Adjust thresholds
        self._adjust_thresholds(critique, engine_run_data, race_result)
        
        logger.info(f"Critique complete: Correct={critique.prediction_correct}, Gate={critique.gate_decision_correct}")
        return critique
    
    def _assign_market_roles_retrospective(
        self,
        critique: PostRaceCritique,
        engine_run_data: Dict,
        race_result: Dict
    ):
        """Assign and validate market roles retrospectively."""
        runner_scores = engine_run_data.get('runner_scores', [])
        
        for runner_score in runner_scores:
            runner_id = runner_score.get('runner_id')
            predicted_role = runner_score.get('market_role', 'unknown')
            
            # Validate role based on outcome
            actual_position = race_result.get('positions', {}).get(runner_id, 99)
            
            # Heuristic validation
            if predicted_role == 'Release_Horse':
                # Release horses should win or place well
                validated = actual_position <= 3
            elif predicted_role == 'Liquidity_Anchor':
                # Anchors often place but don't win
                validated = actual_position > 1 and actual_position <= 4
            else:
                validated = True  # Neutral for other roles
            
            critique.market_roles_assigned[runner_id] = predicted_role
            critique.market_roles_validated[runner_id] = validated
    
    def _evaluate_gate_decision(
        self,
        critique: PostRaceCritique,
        engine_run_data: Dict,
        race_result: Dict,
        learning_gate_result: Dict
    ):
        """Evaluate if learning gate decision was correct."""
        gate_status = learning_gate_result.get('learning_status', 'unknown')
        
        # Check if prediction was correct
        predicted_winner = engine_run_data.get('verdict', {}).get('top_strike_selection')
        actual_winner = race_result.get('winner_id')
        
        critique.prediction_correct = (predicted_winner == actual_winner)
        
        # Check if top-4 hit
        top_4 = engine_run_data.get('verdict', {}).get('top4_structure', [])
        critique.top_4_hit = actual_winner in top_4
        
        # Evaluate gate decision
        if gate_status == 'committed':
            # Gate allowed learning
            if critique.prediction_correct or critique.top_4_hit:
                critique.gate_decision_correct = True
                critique.gate_decision_reason = "Committed and prediction was good"
            else:
                critique.gate_decision_correct = False
                critique.gate_decision_reason = "Committed but prediction failed"
        
        elif gate_status == 'quarantined':
            # Gate quarantined learning
            if not critique.prediction_correct:
                critique.gate_decision_correct = True
                critique.gate_decision_reason = "Quarantined and prediction failed (correct)"
            else:
                critique.gate_decision_correct = False
                critique.gate_decision_reason = "Quarantined but prediction was correct (missed opportunity)"
        
        elif gate_status == 'rejected':
            # Gate rejected learning
            if not critique.prediction_correct:
                critique.gate_decision_correct = True
                critique.gate_decision_reason = "Rejected and prediction failed (correct)"
            else:
                critique.gate_decision_correct = False
                critique.gate_decision_reason = "Rejected but prediction was correct (too conservative)"
    
    def _update_quarantine_counters(
        self,
        critique: PostRaceCritique,
        learning_gate_result: Dict,
        race_result: Dict
    ):
        """Update quarantine promotion/rejection counters."""
        gate_status = learning_gate_result.get('learning_status', 'unknown')
        
        if gate_status == 'quarantined':
            # Check if quarantined decision should be promoted
            if critique.prediction_correct or critique.top_4_hit:
                critique.quarantine_promotions = 1
                logger.info("Quarantine promotion: prediction was correct")
            else:
                critique.quarantine_rejections = 1
                logger.info("Quarantine rejection: prediction failed")
    
    def _analyze_why_won_lost(
        self,
        critique: PostRaceCritique,
        engine_run_data: Dict,
        race_result: Dict
    ):
        """Analyze why we won or lost."""
        if critique.prediction_correct:
            # Why we won
            reasons = []
            
            verdict = engine_run_data.get('verdict', {})
            
            if verdict.get('win_suppressed') == False:
                reasons.append("Win not suppressed - confidence justified")
            
            market_roles = verdict.get('market_roles', {})
            predicted_winner = verdict.get('top_strike_selection')
            winner_role = market_roles.get(predicted_winner, 'unknown')
            
            if winner_role == 'Release_Horse':
                reasons.append("Correctly identified Release Horse")
            
            chaos_level = engine_run_data.get('chaos_level', 0.0)
            if chaos_level < 0.60:
                reasons.append("Structure race - stable prediction")
            
            critique.why_won = reasons
        
        else:
            # Why we lost
            reasons = []
            
            verdict = engine_run_data.get('verdict', {})
            
            if verdict.get('win_suppressed') == True:
                reasons.append(f"Win suppressed: {verdict.get('suppression_reason', 'unknown')}")
            
            chaos_level = engine_run_data.get('chaos_level', 0.0)
            if chaos_level >= 0.60:
                reasons.append("Chaos race - high variance")
            
            manipulation_risk = engine_run_data.get('manipulation_risk', 0.0)
            if manipulation_risk >= 0.60:
                reasons.append("High manipulation risk detected")
            
            # Check if actual winner was flagged
            actual_winner = race_result.get('winner_id')
            market_roles = verdict.get('market_roles', {})
            winner_role = market_roles.get(actual_winner, 'unknown')
            
            if winner_role == 'Liquidity_Anchor':
                reasons.append("Winner was Liquidity Anchor - trap race")
            
            critique.why_lost = reasons
    
    def _adjust_thresholds(
        self,
        critique: PostRaceCritique,
        engine_run_data: Dict,
        race_result: Dict
    ):
        """Adjust thresholds based on outcome."""
        adjustments = {}
        
        # If gate was too conservative (rejected/quarantined but correct)
        if not critique.gate_decision_correct:
            if critique.prediction_correct:
                # Lower thresholds slightly
                adjustments['chaos_threshold'] = -0.02
                adjustments['manipulation_threshold'] = -0.02
                logger.info("Lowering thresholds - gate was too conservative")
        
        # If gate was too permissive (committed but wrong)
        elif critique.gate_decision_correct and not critique.prediction_correct:
            # Raise thresholds slightly
            adjustments['chaos_threshold'] = 0.02
            adjustments['manipulation_threshold'] = 0.02
            logger.info("Raising thresholds - gate was too permissive")
        
        critique.threshold_adjustments = adjustments


def perform_post_race_critique(
    race_id: str,
    engine_run_id: str,
    engine_run_data: Dict,
    race_result: Dict,
    learning_gate_result: Dict
) -> PostRaceCritique:
    """
    Convenience function to perform post-race critique.
    
    Args:
        race_id: Race ID
        engine_run_id: Engine run ID
        engine_run_data: Engine run data
        race_result: Race result
        learning_gate_result: Learning gate result
        
    Returns:
        PostRaceCritique
    """
    engine = PostRaceCritiqueEngine()
    return engine.critique(race_id, engine_run_id, engine_run_data, race_result, learning_gate_result)


if __name__ == "__main__":
    # Example usage
    engine_run_data = {
        'verdict': {
            'top_strike_selection': 'r1',
            'top4_structure': ['r1', 'r2', 'r3', 'r4'],
            'win_suppressed': False,
            'market_roles': {
                'r1': 'Release_Horse',
                'r2': 'Liquidity_Anchor'
            }
        },
        'runner_scores': [
            {'runner_id': 'r1', 'market_role': 'Release_Horse'},
            {'runner_id': 'r2', 'market_role': 'Liquidity_Anchor'}
        ],
        'chaos_level': 0.35,
        'manipulation_risk': 0.25
    }
    
    race_result = {
        'winner_id': 'r1',
        'positions': {
            'r1': 1,
            'r2': 2,
            'r3': 3,
            'r4': 5
        }
    }
    
    learning_gate_result = {
        'learning_status': 'committed'
    }
    
    critique = perform_post_race_critique(
        'test_001',
        'engine_run_001',
        engine_run_data,
        race_result,
        learning_gate_result
    )
    
    print(f"Critique: {critique.to_dict()}")
