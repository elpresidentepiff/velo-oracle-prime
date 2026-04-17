#!/usr/bin/env python3
"""
VELO Activity-Dependent Learning Gate (ADLG)
Prevents engine from learning garbage and getting "trained into losing"

CRITICAL: VELO only commits learning when ALL gate conditions pass.

Gate conditions (must all pass):
1. Signal convergence: SQPE + SSES + TIE + Stability Cluster above thresholds
2. Manipulation state not "High" (or commit only to quarantine)
3. Ablation robustness: decision survives feature-family silencing
4. Outcome verified and post-race critique completed
5. No integrity red flags (late non-runner chaos, weird pace collapse flagged)

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LearningStatus(Enum):
    """Learning status for race outcomes."""
    COMMITTED = "committed"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


@dataclass
class GateCondition:
    """A single gate condition check."""
    name: str
    passed: bool
    score: float
    threshold: float
    reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'passed': self.passed,
            'score': self.score,
            'threshold': self.threshold,
            'reason': self.reason
        }


@dataclass
class LearningGateResult:
    """Result from learning gate evaluation."""
    learning_status: LearningStatus
    learning_gate_score: float
    conditions: List[GateCondition] = field(default_factory=list)
    gate_reasons: List[str] = field(default_factory=list)
    ablation_flips: int = 0
    integrity_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'learning_status': self.learning_status.value,
            'learning_gate_score': self.learning_gate_score,
            'conditions': [c.to_dict() for c in self.conditions],
            'gate_reasons': self.gate_reasons,
            'ablation_flips': self.ablation_flips,
            'integrity_flags': self.integrity_flags
        }


class ActivityDependentLearningGate:
    """
    Activity-Dependent Learning Gate.
    
    Prevents VELO from learning from low-signal / manipulated races.
    Only commits learning when robustness tests pass.
    """
    
    # Thresholds for gate conditions
    SIGNAL_CONVERGENCE_THRESHOLD = 0.70
    MANIPULATION_THRESHOLD = 0.60  # If > 0.60, reject or quarantine
    ABLATION_FLIP_MAX = 1  # Max allowed ablation flips
    STABILITY_THRESHOLD = 0.65
    
    def __init__(self):
        logger.info("ADLG initialized (War Mode)")
    
    def evaluate(
        self,
        engine_outputs: Dict,
        ablation_results: Dict,
        race_outcome: Dict,
        integrity_check: Dict,
        race_ctx: Dict = None
    ) -> LearningGateResult:
        """
        Evaluate whether to commit learning from this race.
        
        Args:
            engine_outputs: Engine scores and predictions
            ablation_results: Results from ablation tests
            race_outcome: Actual race outcome
            integrity_check: Integrity check results
            
        Returns:
            LearningGateResult with status and reasons
        """
        # Get race ID from race_ctx first, fallback to race_outcome
        race_id = 'unknown'
        race_name = 'unknown'
        if race_ctx:
            race_id = race_ctx.get('race_id', 'unknown')
            race_name = f"{race_ctx.get('course', 'unknown')}_{race_ctx.get('off_time', 'unknown')}"
        else:
            race_id = race_outcome.get('race_id', 'unknown')
        logger.info(f"ADLG evaluating race: {race_id} ({race_name})")
        
        conditions = []
        
        # Condition 1: Signal convergence
        signal_convergence = self._check_signal_convergence(engine_outputs)
        conditions.append(signal_convergence)
        
        # Condition 2: Manipulation state
        manipulation_check = self._check_manipulation_state(engine_outputs)
        conditions.append(manipulation_check)
        
        # Condition 3: Ablation robustness
        ablation_check = self._check_ablation_robustness(ablation_results)
        conditions.append(ablation_check)
        
        # Condition 4: Outcome verified
        outcome_check = self._check_outcome_verified(race_outcome)
        conditions.append(outcome_check)
        
        # Condition 5: Integrity flags
        integrity_flags = integrity_check.get('flags', [])
        integrity_ok = len(integrity_flags) == 0
        conditions.append(GateCondition(
            name="integrity_check",
            passed=integrity_ok,
            score=1.0 if integrity_ok else 0.0,
            threshold=1.0,
            reason=f"{len(integrity_flags)} integrity flags" if not integrity_ok else "clean"
        ))
        
        # Calculate overall gate score
        gate_score = sum(c.score for c in conditions) / len(conditions)
        
        # Determine learning status
        all_passed = all(c.passed for c in conditions)
        
        if all_passed:
            status = LearningStatus.COMMITTED
            reasons = ["All gate conditions passed"]
        elif manipulation_check.score > self.MANIPULATION_THRESHOLD:
            status = LearningStatus.REJECTED
            reasons = ["High manipulation detected"]
        elif ablation_check.score < 0.5:
            status = LearningStatus.QUARANTINED
            reasons = ["Ablation robustness failed - decision too fragile"]
        else:
            status = LearningStatus.QUARANTINED
            reasons = [f"Gate score {gate_score:.2f} below threshold"]
        
        # Collect failed condition reasons
        for cond in conditions:
            if not cond.passed and cond.reason:
                reasons.append(f"{cond.name}: {cond.reason}")
        
        result = LearningGateResult(
            learning_status=status,
            learning_gate_score=gate_score,
            conditions=conditions,
            gate_reasons=reasons,
            ablation_flips=ablation_results.get('flip_count', 0),
            integrity_flags=integrity_flags
        )
        
        logger.info(f"ADLG: Status={status.value}, Score={gate_score:.2f}, Flips={result.ablation_flips}")
        return result
    
    def _check_signal_convergence(self, engine_outputs: Dict) -> GateCondition:
        """Check if SQPE + SSES + TIE + Stability converge."""
        sqpe_score = engine_outputs.get('sqpe_score', 0.0)
        sses_score = engine_outputs.get('sses_score', 0.0)
        tie_score = engine_outputs.get('tie_score', 0.0)
        stability_score = engine_outputs.get('stability_score', 0.0)
        
        # Average convergence
        convergence = (sqpe_score + sses_score + tie_score + stability_score) / 4.0
        passed = convergence >= self.SIGNAL_CONVERGENCE_THRESHOLD
        
        return GateCondition(
            name="signal_convergence",
            passed=passed,
            score=convergence,
            threshold=self.SIGNAL_CONVERGENCE_THRESHOLD,
            reason=f"Convergence {convergence:.2f}" if not passed else ""
        )
    
    def _check_manipulation_state(self, engine_outputs: Dict) -> GateCondition:
        """Check manipulation risk level."""
        manipulation_risk = engine_outputs.get('manipulation_risk', 0.0)
        passed = manipulation_risk <= self.MANIPULATION_THRESHOLD
        
        return GateCondition(
            name="manipulation_check",
            passed=passed,
            score=1.0 - manipulation_risk,  # Invert so lower risk = higher score
            threshold=1.0 - self.MANIPULATION_THRESHOLD,
            reason=f"Manipulation risk {manipulation_risk:.2f}" if not passed else ""
        )
    
    def _check_ablation_robustness(self, ablation_results: Dict) -> GateCondition:
        """Check if decision survives feature ablation."""
        flip_count = ablation_results.get('flip_count', 0)
        prob_delta_max = ablation_results.get('prob_delta_max', 0.0)
        
        # Decision is robust if it doesn't flip with ablations
        passed = flip_count <= self.ABLATION_FLIP_MAX and prob_delta_max < 0.15
        
        # Score inversely proportional to flips
        score = max(0.0, 1.0 - (flip_count / 5.0) - prob_delta_max)
        
        return GateCondition(
            name="ablation_robustness",
            passed=passed,
            score=score,
            threshold=0.70,
            reason=f"{flip_count} flips, max delta {prob_delta_max:.2f}" if not passed else ""
        )
    
    def _check_outcome_verified(self, race_outcome: Dict) -> GateCondition:
        """Check if outcome is verified and complete."""
        verified = race_outcome.get('verified', False)
        has_winner = race_outcome.get('winner_id') is not None
        
        passed = verified and has_winner
        score = 1.0 if passed else 0.0
        
        return GateCondition(
            name="outcome_verified",
            passed=passed,
            score=score,
            threshold=1.0,
            reason="Outcome not verified or incomplete" if not passed else ""
        )


def evaluate_learning_gate(
    engine_outputs: Dict,
    ablation_results: Dict,
    race_outcome: Dict,
    integrity_check: Dict,
    race_ctx: Dict = None
) -> LearningGateResult:
    """
    Convenience function to evaluate learning gate.
    
    Args:
        engine_outputs: Engine outputs
        ablation_results: Ablation test results
        race_outcome: Race outcome
        integrity_check: Integrity check
        
    Returns:
        LearningGateResult
    """
    gate = ActivityDependentLearningGate()
    return gate.evaluate(engine_outputs, ablation_results, race_outcome, integrity_check, race_ctx)


if __name__ == "__main__":
    # Example usage
    engine_outputs = {
        'sqpe_score': 0.85,
        'sses_score': 0.78,
        'tie_score': 0.72,
        'stability_score': 0.80,
        'manipulation_risk': 0.25
    }
    
    ablation_results = {
        'flip_count': 0,
        'prob_delta_max': 0.08
    }
    
    race_outcome = {
        'race_id': 'test_001',
        'verified': True,
        'winner_id': 'r1'
    }
    
    integrity_check = {
        'flags': []
    }
    
    result = evaluate_learning_gate(engine_outputs, ablation_results, race_outcome, integrity_check)
    print(f"Learning Gate Result: {result.to_dict()}")
