#!/usr/bin/env python3
"""
VELO v12 Failure Playbook & Safe Mode System
When tests pass but live results degrade

Objective: Diagnose fast, stop bleeding, isolate root cause

Safe Mode triggers:
- Sudden loss streak outside expected variance
- Error rate > threshold
- Missing data spikes
- Market regime shifts
- Model outputs become extreme or flat

Safe Mode actions:
- Disable market features (no_market)
- Reduce staking to minimum (or simulation-only)
- Force Top-4 chassis only (no win overlays)

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FailureClass(Enum):
    """Failure classification buckets."""
    DATA_INGESTION = "data_ingestion"
    LEAKAGE_CONTAMINATION = "leakage_contamination"
    FEATURE_DRIFT = "feature_drift"
    CALIBRATION_COLLAPSE = "calibration_collapse"
    DECISION_POLICY = "decision_policy"
    UNKNOWN = "unknown"


class SafeModeLevel(Enum):
    """Safe mode severity levels."""
    NORMAL = "normal"
    CONSERVATIVE = "conservative"
    DEFENSIVE = "defensive"
    SHUTDOWN = "shutdown"


@dataclass
class SafeModeConfig:
    """Safe mode configuration."""
    level: SafeModeLevel = SafeModeLevel.NORMAL
    market_features_enabled: bool = True
    win_overlays_enabled: bool = True
    stake_multiplier: float = 1.0
    force_top4_only: bool = False
    simulation_only: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'level': self.level.value,
            'market_features_enabled': self.market_features_enabled,
            'win_overlays_enabled': self.win_overlays_enabled,
            'stake_multiplier': self.stake_multiplier,
            'force_top4_only': self.force_top4_only,
            'simulation_only': self.simulation_only
        }


@dataclass
class FailureDiagnostic:
    """Failure diagnostic result."""
    timestamp: datetime
    failure_class: FailureClass
    severity: float  # 0.0 to 1.0
    triggers: List[str] = field(default_factory=list)
    smell_tests: Dict[str, bool] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)
    safe_mode_level: SafeModeLevel = SafeModeLevel.NORMAL
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'failure_class': self.failure_class.value,
            'severity': self.severity,
            'triggers': self.triggers,
            'smell_tests': self.smell_tests,
            'recommended_actions': self.recommended_actions,
            'safe_mode_level': self.safe_mode_level.value
        }


class SafeModeSystem:
    """
    Safe Mode System.
    
    Monitors system health and triggers safe mode when degradation detected.
    """
    
    # Thresholds
    LOSS_STREAK_THRESHOLD = 5
    ERROR_RATE_THRESHOLD = 0.10  # 10%
    MISSING_DATA_THRESHOLD = 0.20  # 20%
    EXTREME_PROB_THRESHOLD = 0.95
    FLAT_PROB_THRESHOLD = 0.05
    
    def __init__(self):
        self.current_config = SafeModeConfig()
        self.diagnostics_history: List[FailureDiagnostic] = []
        logger.info("Safe Mode System initialized")
    
    def check_triggers(
        self,
        recent_results: List[Dict],
        error_log: List[Dict],
        data_quality_metrics: Dict
    ) -> Optional[FailureDiagnostic]:
        """
        Check if safe mode should be triggered.
        
        Args:
            recent_results: Recent race results
            error_log: Recent errors
            data_quality_metrics: Data quality metrics
            
        Returns:
            FailureDiagnostic if triggered, None otherwise
        """
        triggers = []
        severity = 0.0
        
        # Check 1: Loss streak
        if len(recent_results) >= self.LOSS_STREAK_THRESHOLD:
            recent_losses = sum(1 for r in recent_results[-self.LOSS_STREAK_THRESHOLD:] 
                              if not r.get('win', False))
            if recent_losses >= self.LOSS_STREAK_THRESHOLD:
                triggers.append(f"Loss streak: {recent_losses} consecutive losses")
                severity = max(severity, 0.7)
        
        # Check 2: Error rate
        total_runs = len(recent_results)
        error_count = len(error_log)
        if total_runs > 0:
            error_rate = error_count / total_runs
            if error_rate > self.ERROR_RATE_THRESHOLD:
                triggers.append(f"Error rate: {error_rate:.2%} (threshold {self.ERROR_RATE_THRESHOLD:.2%})")
                severity = max(severity, 0.8)
        
        # Check 3: Missing data spike
        missing_rate = data_quality_metrics.get('missing_rate', 0.0)
        if missing_rate > self.MISSING_DATA_THRESHOLD:
            triggers.append(f"Missing data: {missing_rate:.2%} (threshold {self.MISSING_DATA_THRESHOLD:.2%})")
            severity = max(severity, 0.6)
        
        # Check 4: Extreme probabilities
        extreme_prob_count = data_quality_metrics.get('extreme_prob_count', 0)
        if extreme_prob_count > 0:
            triggers.append(f"Extreme probabilities detected: {extreme_prob_count} cases")
            severity = max(severity, 0.5)
        
        # If no triggers, return None
        if not triggers:
            return None
        
        # Determine safe mode level
        if severity >= 0.8:
            safe_mode_level = SafeModeLevel.SHUTDOWN
        elif severity >= 0.6:
            safe_mode_level = SafeModeLevel.DEFENSIVE
        elif severity >= 0.4:
            safe_mode_level = SafeModeLevel.CONSERVATIVE
        else:
            safe_mode_level = SafeModeLevel.NORMAL
        
        # Run smell tests
        smell_tests = self._run_smell_tests(recent_results, error_log, data_quality_metrics)
        
        # Classify failure
        failure_class = self._classify_failure(triggers, smell_tests)
        
        # Generate recommended actions
        recommended_actions = self._generate_actions(failure_class, safe_mode_level)
        
        diagnostic = FailureDiagnostic(
            timestamp=datetime.now(),
            failure_class=failure_class,
            severity=severity,
            triggers=triggers,
            smell_tests=smell_tests,
            recommended_actions=recommended_actions,
            safe_mode_level=safe_mode_level
        )
        
        self.diagnostics_history.append(diagnostic)
        logger.warning(f"Safe mode triggered: {safe_mode_level.value}, severity={severity:.2f}")
        
        return diagnostic
    
    def _run_smell_tests(
        self,
        recent_results: List[Dict],
        error_log: List[Dict],
        data_quality_metrics: Dict
    ) -> Dict[str, bool]:
        """Run 10-minute smell tests."""
        tests = {}
        
        # Smell Test 1: Determinism replay
        # (Would need actual replay logic)
        tests['determinism_replay'] = True  # Placeholder
        
        # Smell Test 2: Missingness spike
        baseline_missing = 0.05  # 5% baseline
        current_missing = data_quality_metrics.get('missing_rate', 0.0)
        tests['missingness_spike'] = (current_missing > baseline_missing * 2)
        
        # Smell Test 3: Leakage probe
        # (Would check firewall logs)
        tests['leakage_detected'] = False  # Placeholder
        
        # Smell Test 4: Probability sanity
        extreme_count = data_quality_metrics.get('extreme_prob_count', 0)
        flat_count = data_quality_metrics.get('flat_prob_count', 0)
        tests['probability_insane'] = (extreme_count > 0 or flat_count > 0)
        
        return tests
    
    def _classify_failure(
        self,
        triggers: List[str],
        smell_tests: Dict[str, bool]
    ) -> FailureClass:
        """Classify failure into bucket."""
        # Heuristic classification
        if smell_tests.get('leakage_detected', False):
            return FailureClass.LEAKAGE_CONTAMINATION
        
        if smell_tests.get('missingness_spike', False):
            return FailureClass.DATA_INGESTION
        
        if smell_tests.get('probability_insane', False):
            return FailureClass.CALIBRATION_COLLAPSE
        
        # Check trigger keywords
        trigger_text = " ".join(triggers).lower()
        if 'missing data' in trigger_text:
            return FailureClass.DATA_INGESTION
        elif 'error rate' in trigger_text:
            return FailureClass.DATA_INGESTION
        elif 'loss streak' in trigger_text:
            return FailureClass.DECISION_POLICY
        
        return FailureClass.UNKNOWN
    
    def _generate_actions(
        self,
        failure_class: FailureClass,
        safe_mode_level: SafeModeLevel
    ) -> List[str]:
        """Generate recommended actions."""
        actions = []
        
        # Base actions for safe mode level
        if safe_mode_level == SafeModeLevel.SHUTDOWN:
            actions.append("SHUTDOWN: Stop all live betting immediately")
            actions.append("Switch to simulation-only mode")
            actions.append("Notify operators")
        elif safe_mode_level == SafeModeLevel.DEFENSIVE:
            actions.append("Disable market features (no_market preset)")
            actions.append("Force Top-4 chassis only (no win overlays)")
            actions.append("Reduce stakes to 25% of normal")
        elif safe_mode_level == SafeModeLevel.CONSERVATIVE:
            actions.append("Reduce stakes to 50% of normal")
            actions.append("Disable win overlays in chaos races")
        
        # Failure-specific actions
        if failure_class == FailureClass.DATA_INGESTION:
            actions.append("Check data ingestion pipeline")
            actions.append("Verify API connections")
            actions.append("Review schema changes")
        elif failure_class == FailureClass.LEAKAGE_CONTAMINATION:
            actions.append("HALT: Stop all training immediately")
            actions.append("Run leakage firewall diagnostics")
            actions.append("Review recent code changes")
        elif failure_class == FailureClass.FEATURE_DRIFT:
            actions.append("Switch to no_market preset")
            actions.append("Run drift analysis on all feature domains")
        elif failure_class == FailureClass.CALIBRATION_COLLAPSE:
            actions.append("Revert to last stable model checkpoint")
            actions.append("Run calibration diagnostics")
        elif failure_class == FailureClass.DECISION_POLICY:
            actions.append("Review decision policy thresholds")
            actions.append("Check for cognitive trap firewall failures")
        
        return actions
    
    def activate_safe_mode(self, diagnostic: FailureDiagnostic):
        """Activate safe mode based on diagnostic."""
        level = diagnostic.safe_mode_level
        
        if level == SafeModeLevel.SHUTDOWN:
            self.current_config = SafeModeConfig(
                level=SafeModeLevel.SHUTDOWN,
                market_features_enabled=False,
                win_overlays_enabled=False,
                stake_multiplier=0.0,
                force_top4_only=True,
                simulation_only=True
            )
        elif level == SafeModeLevel.DEFENSIVE:
            self.current_config = SafeModeConfig(
                level=SafeModeLevel.DEFENSIVE,
                market_features_enabled=False,
                win_overlays_enabled=False,
                stake_multiplier=0.25,
                force_top4_only=True,
                simulation_only=False
            )
        elif level == SafeModeLevel.CONSERVATIVE:
            self.current_config = SafeModeConfig(
                level=SafeModeLevel.CONSERVATIVE,
                market_features_enabled=True,
                win_overlays_enabled=False,
                stake_multiplier=0.50,
                force_top4_only=False,
                simulation_only=False
            )
        
        logger.warning(f"Safe mode activated: {level.value}")
        logger.info(f"Config: {self.current_config.to_dict()}")
    
    def deactivate_safe_mode(self):
        """Return to normal operation."""
        self.current_config = SafeModeConfig(level=SafeModeLevel.NORMAL)
        logger.info("Safe mode deactivated - returning to normal operation")


def check_safe_mode_triggers(
    recent_results: List[Dict],
    error_log: List[Dict],
    data_quality_metrics: Dict
) -> Optional[FailureDiagnostic]:
    """
    Convenience function to check safe mode triggers.
    
    Args:
        recent_results: Recent results
        error_log: Error log
        data_quality_metrics: Data quality metrics
        
    Returns:
        FailureDiagnostic if triggered
    """
    system = SafeModeSystem()
    return system.check_triggers(recent_results, error_log, data_quality_metrics)


if __name__ == "__main__":
    # Example usage
    recent_results = [
        {'win': False},
        {'win': False},
        {'win': False},
        {'win': False},
        {'win': False}
    ]
    
    error_log = [
        {'error': 'Missing field'},
        {'error': 'API timeout'}
    ]
    
    data_quality_metrics = {
        'missing_rate': 0.25,
        'extreme_prob_count': 3,
        'flat_prob_count': 0
    }
    
    diagnostic = check_safe_mode_triggers(recent_results, error_log, data_quality_metrics)
    
    if diagnostic:
        print(f"Safe Mode Diagnostic: {diagnostic.to_dict()}")
    else:
        print("No safe mode triggers detected")
