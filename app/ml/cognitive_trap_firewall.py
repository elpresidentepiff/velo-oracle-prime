#!/usr/bin/env python3
"""
VELO Cognitive Trap Firewall (CTF)
Protects VELO from human biases and cognitive traps

We are building an Oracle. It must not get hypnotized by the same traps humans do.

Implement explicit bias detectors (store flags):
1. Anchoring effect: favourite/short price overweighted
   → downweight win confidence unless release signal present
2. Recency bias: last-run over-influence
   → stability cluster must confirm
3. Narrative trap: "big stable/jockey therefore win"
   → require intent markers
4. Sunk cost/tilt: if user is chasing losses
   → default to conservative chassis (Top-4) and reduce stake suggestions

This is not psychology fluff. It's a risk-control module for an adversarial market.

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BiasType(Enum):
    """Types of cognitive biases detected."""
    ANCHORING = "anchoring"
    RECENCY = "recency"
    NARRATIVE = "narrative"
    SUNK_COST = "sunk_cost"
    OVERCONFIDENCE = "overconfidence"


@dataclass
class BiasDetection:
    """A detected cognitive bias."""
    bias_type: BiasType
    severity: float  # 0.0 to 1.0
    affected_runner: Optional[str] = None
    mitigation: str = ""
    evidence: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'bias_type': self.bias_type.value,
            'severity': self.severity,
            'affected_runner': self.affected_runner,
            'mitigation': self.mitigation,
            'evidence': self.evidence
        }


@dataclass
class CTFReport:
    """Cognitive Trap Firewall report."""
    biases_detected: List[BiasDetection] = field(default_factory=list)
    max_severity: float = 0.0
    mitigations_applied: List[str] = field(default_factory=list)
    decision_adjusted: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'biases_detected': [b.to_dict() for b in self.biases_detected],
            'max_severity': self.max_severity,
            'mitigations_applied': self.mitigations_applied,
            'decision_adjusted': self.decision_adjusted
        }


class CognitiveTrapFirewall:
    """
    Cognitive Trap Firewall.
    
    Detects and mitigates cognitive biases that could corrupt decision-making.
    """
    
    # Severity thresholds
    SEVERITY_LOW = 0.3
    SEVERITY_MEDIUM = 0.6
    SEVERITY_HIGH = 0.8
    
    def __init__(self):
        logger.info("CTF initialized (War Mode)")
    
    def scan(
        self,
        runners: List[Dict],
        predictions: Dict,
        market_ctx: Dict,
        user_ctx: Optional[Dict] = None
    ) -> CTFReport:
        """
        Scan for cognitive biases and generate mitigation report.
        
        Args:
            runners: Runner data
            predictions: Model predictions
            market_ctx: Market context
            user_ctx: Optional user context (for sunk cost detection)
            
        Returns:
            CTFReport with detected biases and mitigations
        """
        logger.info("CTF scanning for cognitive biases")
        
        biases = []
        
        # 1. Anchoring effect detection
        anchoring_bias = self._detect_anchoring(runners, predictions, market_ctx)
        if anchoring_bias:
            biases.append(anchoring_bias)
        
        # 2. Recency bias detection
        recency_bias = self._detect_recency(runners, predictions)
        if recency_bias:
            biases.append(recency_bias)
        
        # 3. Narrative trap detection
        narrative_bias = self._detect_narrative(runners, predictions)
        if narrative_bias:
            biases.append(narrative_bias)
        
        # 4. Sunk cost/tilt detection
        if user_ctx:
            sunk_cost_bias = self._detect_sunk_cost(user_ctx)
            if sunk_cost_bias:
                biases.append(sunk_cost_bias)
        
        # Calculate max severity
        max_severity = max([b.severity for b in biases], default=0.0)
        
        # Determine if decision should be adjusted
        decision_adjusted = max_severity >= self.SEVERITY_MEDIUM
        
        # Collect mitigations
        mitigations = [b.mitigation for b in biases if b.mitigation]
        
        report = CTFReport(
            biases_detected=biases,
            max_severity=max_severity,
            mitigations_applied=mitigations,
            decision_adjusted=decision_adjusted
        )
        
        logger.info(f"CTF: {len(biases)} biases detected, max severity {max_severity:.2f}")
        return report
    
    def _detect_anchoring(
        self,
        runners: List[Dict],
        predictions: Dict,
        market_ctx: Dict
    ) -> Optional[BiasDetection]:
        """
        Detect anchoring effect: favourite/short price overweighted.
        
        Mitigation: Downweight win confidence unless release signal present.
        """
        # Find favorite
        favorite = None
        for runner in runners:
            if runner.get('is_favorite', False):
                favorite = runner
                break
        
        if not favorite:
            return None
        
        runner_id = favorite.get('runner_id')
        
        # Check if favorite is predicted to win
        top_selection = predictions.get('top_selection')
        
        if top_selection != runner_id:
            return None  # No anchoring if favorite not selected
        
        # Check for release signals
        market_role = favorite.get('market_role', 'unknown')
        is_release = (market_role == 'Release_Horse')
        
        # If favorite selected WITHOUT release signal → anchoring risk
        if not is_release:
            severity = 0.7  # High severity
            
            return BiasDetection(
                bias_type=BiasType.ANCHORING,
                severity=severity,
                affected_runner=runner_id,
                mitigation="Downweight win confidence; require release signal",
                evidence={
                    'is_favorite': True,
                    'market_role': market_role,
                    'release_signal': is_release
                }
            )
        
        return None
    
    def _detect_recency(
        self,
        runners: List[Dict],
        predictions: Dict
    ) -> Optional[BiasDetection]:
        """
        Detect recency bias: last-run over-influence.
        
        Mitigation: Stability cluster must confirm.
        """
        top_selection = predictions.get('top_selection')
        
        # Find top selection runner
        top_runner = None
        for runner in runners:
            if runner.get('runner_id') == top_selection:
                top_runner = runner
                break
        
        if not top_runner:
            return None
        
        # Check if last run was exceptional
        last_run_pos = top_runner.get('last_run_position', 99)
        avg_position = top_runner.get('avg_position_last_5', 5.0)
        
        # If last run much better than average → recency risk
        if last_run_pos <= 2 and avg_position > 4.0:
            # Check stability cluster
            stability_score = top_runner.get('stability_score', 0.0)
            
            if stability_score < 0.65:
                severity = 0.6
                
                return BiasDetection(
                    bias_type=BiasType.RECENCY,
                    severity=severity,
                    affected_runner=top_selection,
                    mitigation="Require stability cluster confirmation",
                    evidence={
                        'last_run_position': last_run_pos,
                        'avg_position': avg_position,
                        'stability_score': stability_score
                    }
                )
        
        return None
    
    def _detect_narrative(
        self,
        runners: List[Dict],
        predictions: Dict
    ) -> Optional[BiasDetection]:
        """
        Detect narrative trap: "big stable/jockey therefore win".
        
        Mitigation: Require intent markers.
        """
        top_selection = predictions.get('top_selection')
        
        # Find top selection runner
        top_runner = None
        for runner in runners:
            if runner.get('runner_id') == top_selection:
                top_runner = runner
                break
        
        if not top_runner:
            return None
        
        # Check for "big name" markers
        trainer = top_runner.get('trainer', '')
        jockey = top_runner.get('jockey', '')
        
        # Simplified: check if trainer/jockey has high profile
        # (In production, maintain list of high-profile connections)
        is_big_stable = top_runner.get('trainer_strike_rate', 0.0) > 0.20
        is_top_jockey = top_runner.get('jockey_strike_rate', 0.0) > 0.20
        
        if is_big_stable or is_top_jockey:
            # Check for intent markers
            intent_class = top_runner.get('intent_class', 'Unknown')
            
            if intent_class == 'Unknown':
                severity = 0.5
                
                return BiasDetection(
                    bias_type=BiasType.NARRATIVE,
                    severity=severity,
                    affected_runner=top_selection,
                    mitigation="Require intent markers (Win signal)",
                    evidence={
                        'trainer': trainer,
                        'jockey': jockey,
                        'intent_class': intent_class,
                        'big_stable': is_big_stable,
                        'top_jockey': is_top_jockey
                    }
                )
        
        return None
    
    def _detect_sunk_cost(self, user_ctx: Dict) -> Optional[BiasDetection]:
        """
        Detect sunk cost/tilt: user chasing losses.
        
        Mitigation: Default to conservative chassis (Top-4) and reduce stakes.
        """
        # Check recent P&L
        recent_pnl = user_ctx.get('recent_pnl', 0.0)
        losing_streak = user_ctx.get('losing_streak', 0)
        
        # If significant losses or losing streak → tilt risk
        if recent_pnl < -100 or losing_streak >= 3:
            severity = 0.8  # High severity
            
            return BiasDetection(
                bias_type=BiasType.SUNK_COST,
                severity=severity,
                mitigation="Force conservative chassis (Top-4 only); reduce stake suggestions",
                evidence={
                    'recent_pnl': recent_pnl,
                    'losing_streak': losing_streak
                }
            )
        
        return None
    
    def apply_mitigations(
        self,
        report: CTFReport,
        decision: Dict
    ) -> Dict:
        """
        Apply mitigations to decision based on CTF report.
        
        Args:
            report: CTF report
            decision: Original decision
            
        Returns:
            Adjusted decision
        """
        if not report.decision_adjusted:
            return decision
        
        adjusted = decision.copy()
        
        for bias in report.biases_detected:
            if bias.bias_type == BiasType.ANCHORING:
                # Downweight win confidence
                adjusted['win_confidence'] = adjusted.get('win_confidence', 0.5) * 0.7
                logger.info("CTF: Downweighted win confidence due to anchoring")
            
            elif bias.bias_type == BiasType.RECENCY:
                # Require higher stability threshold
                adjusted['stability_required'] = 0.70
                logger.info("CTF: Increased stability requirement due to recency bias")
            
            elif bias.bias_type == BiasType.NARRATIVE:
                # Require intent confirmation
                adjusted['intent_required'] = True
                logger.info("CTF: Requiring intent confirmation due to narrative trap")
            
            elif bias.bias_type == BiasType.SUNK_COST:
                # Force conservative chassis
                adjusted['chassis'] = 'Top-4'
                adjusted['suppress_win'] = True
                adjusted['stake_multiplier'] = 0.5
                logger.info("CTF: Forced conservative chassis due to sunk cost/tilt")
        
        return adjusted


def scan_cognitive_traps(
    runners: List[Dict],
    predictions: Dict,
    market_ctx: Dict,
    user_ctx: Optional[Dict] = None
) -> CTFReport:
    """
    Convenience function to scan for cognitive traps.
    
    Args:
        runners: Runner data
        predictions: Predictions
        market_ctx: Market context
        user_ctx: User context
        
    Returns:
        CTFReport
    """
    firewall = CognitiveTrapFirewall()
    return firewall.scan(runners, predictions, market_ctx, user_ctx)


if __name__ == "__main__":
    # Example usage
    runners = [
        {
            'runner_id': 'r1',
            'horse_name': 'Horse A',
            'is_favorite': True,
            'market_role': 'Liquidity_Anchor',
            'trainer_strike_rate': 0.25,
            'jockey_strike_rate': 0.22
        },
        {
            'runner_id': 'r2',
            'horse_name': 'Horse B',
            'is_favorite': False
        }
    ]
    
    predictions = {
        'top_selection': 'r1',
        'probabilities': {'r1': 0.45, 'r2': 0.30}
    }
    
    market_ctx = {}
    user_ctx = {'recent_pnl': -150, 'losing_streak': 4}
    
    report = scan_cognitive_traps(runners, predictions, market_ctx, user_ctx)
    print(f"CTF Report: {report.to_dict()}")
